from __future__ import annotations

import asyncio
import inspect
import json
import logging
import os
import re
import time
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from livekit import agents, rtc
from livekit.agents import llm, stt, vad
from livekit.plugins import deepgram, openai, rime, silero

from backend.fencer import EpochManager, StaleEpochException
from backend.tools.ehr_service import (
    fetch_arterial_blood_gas,
    fetch_electrolyte_panel,
)
from backend.tools.web_search import web_search

load_dotenv()
log = logging.getLogger("scrubsync.agent")

SYSTEM_PROMPT = """
You are ScrubSync AI, a friendly general-purpose voice assistant.
Answer questions about almost anything: health tips, personal life advice,
food recipes, sports, travel, tech, study help, jokes, and everyday tasks.

You MUST remember and reference all details, facts, numbers, and personal context mentioned by the user in previous turns of this session.
Never state that you do not retain or have access to personal information during an ongoing session.


Style:
- Speak naturally for voice: clear, warm, and concise.
- Usually 4 to 8 short sentences unless the user asks for more detail.
- Be practical and specific. Prefer useful next steps over fluff.

Response Speed & Style:
- Respond in direct, crisp sentences without conversational throat-clearing (e.g., do not say 'Sure!', 'Let me see...', or 'I'd be happy to help').
- Deliver the core answer or fact immediately in the first sentence.

Tools:
- Use web_search for live or changing facts: cricket/football scores, news,
  weather, prices, current events, or anything that may be outdated in memory.
- Use check_electrolytes / check_abg only for synthetic DEMO-001 lab requests.
- Call at most one tool per turn. Prefer answering directly when knowledge is enough.

Memory & Continuity:
- Remember all previous context, patient details, and topics discussed earlier in this session.
- Soft pause/resume ("stop", "pause", "continue", "go on", "resume") is handled by the voice runtime without asking you; you will not see those turns.
- If the user interrupts, changes the subject, or says "leave it", immediately abandon the previous topic and address the new request.

CRITICAL SESSION MEMORY RULES:
- You have an active memory of this conversation.
- You MUST recall any detail, name, flight, schedule, or fact the user shared earlier in the chat, even if the user temporarily changed the topic.
- If the user asks about previously provided info (e.g., 'What is my flight time?', 'What is my name?'), check the conversation history and answer directly.
- NEVER say 'I don't have access to personal information' or 'I don't remember' within this active session.

Context & Recall:
- You remember all details, names, flight timings, preferences, and clinical/daily facts shared by the user earlier in this conversation session.
- If the user asks about something they told you previously (e.g. flight time, personal notes), answer them directly using the conversation history. Never claim you lack memory or cannot remember within the active session.

Readback & Verification Protocol:
- If the operator asks to "repeat", "say again", or asks for a specific value just reported (e.g. "what was that pH?"), state the confirmed value immediately without rerunning the tool.

Mid-Utterance Self-Correction:
- If the user changes their mind or self-corrects in a single sentence (e.g., "Tell me X—actually make that Y" or "Check A, wait, no, check B"), completely ignore the first request and directly answer ONLY the corrected target (Y or B).

Procedure Timing & Status:
- If the operator asks to start a timer, count down, or log elapsed time for a procedure (e.g., bone cement, tourniquet, clamp), acknowledge it immediately with: "[Time] timer running."
- If asked for status, elapsed time, or remaining time, give a direct, brief spoken update.
    
Safety:
- You are not a licensed clinician, lawyer, or financial advisor.
- For medical red flags (chest pain, stroke signs, severe breathing trouble,
  suicidal thoughts, anaphylaxis), urge emergency care immediately.
- Do not invent live scores, news, or prices. If unsure, use web_search or say so.
- Do not invent prescription drug regimens with exact dosing as medical orders.
- For cancel with no replacement request, say: "Cancelled."
""".strip()

MAX_SPOKEN_WORDS = int(os.getenv("MAX_SPOKEN_WORDS", "110"))
# Approximate Rime mist/amber conversational rate for mid-sentence resume splits.
TTS_WORDS_PER_SEC = float(os.getenv("TTS_WORDS_PER_SEC", "2.6"))
# AudioSource playout jitter buffer (ms). Large enough that a synthesis or
# event-loop hiccup never drains the queue mid-sentence — an empty queue makes
# LiveKit emit concealment noise (the "whoosh"). Cleared instantly on barge-in.
TTS_QUEUE_MS = int(os.getenv("TTS_QUEUE_MS", "400"))
# Seconds of queued-but-unplayed audio to assume when the live queue depth is
# unavailable; used only as a fallback for the resume cursor.
TTS_QUEUE_TAIL_SEC = TTS_QUEUE_MS / 1000.0

SOFT_PAUSE_PHRASES = frozenset(
    {
        "stop",
        "pause",
        "hold on",
        "hold on a second",
        "hold on a sec",
        "wait",
        "wait a second",
        "wait a sec",
        "one second",
        "hang on",
        "hang on a second",
    }
)
RESUME_PHRASES = frozenset(
    {
        "continue",
        "go on",
        "resume",
        "keep going",
        "go ahead",
        "carry on",
    }
)
HARD_CANCEL_PHRASES = frozenset(
    {
        "cancel",
        "cancel that",
        "abort",
        "leave it",
        "stop that",
        "never mind",
        "nevermind",
    }
)


def required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing environment variable: {name}")
    return value


def normalize_command(text: str) -> str:
    return "".join(
        ch for ch in text.lower().strip() if ch.isalnum() or ch.isspace()
    ).strip()


def _command_match(clean: str, phrases: frozenset[str]) -> bool:
    if not clean:
        return False
    if clean in phrases:
        return True
    # Tolerate STT extras: "please continue", "continue please", "can you continue"
    for prefix in ("please ", "can you ", "could you ", "just "):
        if clean.startswith(prefix) and clean[len(prefix) :] in phrases:
            return True
    for suffix in (" please", " now"):
        if clean.endswith(suffix) and clean[: -len(suffix)] in phrases:
            return True
    return False


def is_soft_pause_command(text: str) -> bool:
    return _command_match(normalize_command(text), SOFT_PAUSE_PHRASES)


def is_resume_command(text: str) -> bool:
    clean = normalize_command(text)
    if _command_match(clean, RESUME_PHRASES):
        return True
    # Tolerate short STT variants: "continue please", "uh continue", "continue that"
    words = clean.split()
    if not words or len(words) > 5:
        return False
    return any(word in RESUME_PHRASES for word in words) and not any(
        word in {"cancel", "stop", "abort", "leave"} for word in words
    )


def is_hard_cancel_command(text: str) -> bool:
    return _command_match(normalize_command(text), HARD_CANCEL_PHRASES)


def split_speakable_units(text: str) -> list[str]:
    """Split into sentence-like units so pause/resume can be exact without an LLM."""
    cleaned = " ".join(text.split()).strip()
    if not cleaned:
        return []
    parts = re.split(r"(?<=[.!?])\s+", cleaned)
    units = [part.strip() for part in parts if part.strip()]
    return units or [cleaned]


class _AudioBuffer:
    """Full synthesized PCM for one utterance, filled ahead of playout.

    Rime streams frames faster than real time, so by the time a user says
    "stop" a few seconds in, the entire utterance is already buffered here.
    "continue" then replays the unspoken frames instantly from memory.
    """

    __slots__ = ("frames", "total_samples", "complete", "failed", "text", "sample_rate")

    def __init__(self, text: str, sample_rate: int = 24000) -> None:
        self.frames: list[rtc.AudioFrame] = []
        self.total_samples = 0
        self.complete = asyncio.Event()
        self.failed = False
        self.text = text
        self.sample_rate = sample_rate


def remaining_speech_from_progress(
    text: str,
    played_samples: int,
    sample_rate: int = 24000,
    started_mono: float | None = None,
) -> str:
    """Estimate unspoken suffix from PCM and/or wall-clock progress."""
    words = text.split()
    if not words:
        return ""
    sample_s = max(0.0, (played_samples / max(sample_rate, 1)) - TTS_QUEUE_TAIL_SEC)
    clock_s = 0.0
    if started_mono is not None:
        clock_s = max(0.0, time.monotonic() - started_mono)
    # Prefer the smaller progress estimate so we keep more leftover text.
    played_s = min(sample_s, clock_s) if started_mono is not None else sample_s
    if started_mono is not None and played_samples <= 0:
        played_s = clock_s
    spoken = int(played_s * TTS_WORDS_PER_SEC)
    spoken = max(0, spoken - 1)
    if spoken >= len(words):
        return ""
    return " ".join(words[spoken:])


class Audit:
    def __init__(self, path: str) -> None:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        self._file = target.open("a", encoding="utf-8")

    def write(self, event: str, **fields: Any) -> None:
        record = {
            "event": event,
            "wall_time_ns": time.time_ns(),
            "monotonic_ns": time.perf_counter_ns(),
            **fields,
        }
        self._file.write(json.dumps(record, ensure_ascii=False) + "\n")
        self._file.flush()

    def close(self) -> None:
        self._file.close()


class VoiceAssistant:
    """
    Explicit LiveKit runtime, not the removed legacy VoiceAssistant class.

    Each synthesized utterance has a distinct epoch-labelled audio track.
    Data messages and RTP are not assumed to be ordered with one another.
    The terminal only connects a track whose name and epoch were authorized.

    Speech recognition is isolated into one Deepgram stream per VAD utterance,
    so a delayed final transcript cannot acquire a newer utterance's epoch.
    """

    def __init__(
        self,
        room: rtc.Room,
        participant_identity: str,
        vad_engine: Any,
        *,
        interrupt_speech_duration: float = 0.15,
    ) -> None:
        self.room = room
        self.participant_identity = participant_identity
        self.interrupt_speech_duration = interrupt_speech_duration
        self.epochs = EpochManager()
        self.audit = Audit(os.getenv("AUDIT_PATH", "artifacts/audit.jsonl"))
        self.vad = vad_engine
        self.stt = deepgram.STT(model="nova-2", language="en-US")
        # Groq free-tier OTPM for qwen/qwen3.6-27b is 1000; the provider
        # default max_tokens (~1024) is rejected before any completion starts.
        # Reasoning must stay off: otherwise <think> burns the whole budget.
        self.llm = openai.LLM(
            model=os.getenv("QWEN_MODEL", "Qwen/Qwen2.5-7B-Instruct"),
            base_url=required("OPENAI_API_BASE"),
            api_key=required("OPENAI_API_KEY"),
            temperature=float(os.getenv("QWEN_TEMPERATURE", "0.4")),
            max_completion_tokens=int(os.getenv("QWEN_MAX_COMPLETION_TOKENS", "512")),
            reasoning_effort="none",
        )
        # The Rime plugin emits rtc.AudioFrame PCM at sample_rate.
        # audio_format="pcm_24000" is a logical configuration label, not an
        # invented keyword argument to the plugin's constructor.
        self.tts = rime.TTS(
            model="mist",
            speaker="amber",
            sample_rate=24000,
            api_key=required("RIME_API_KEY"),
        )

        self.patient_id = os.getenv("PATIENT_ID", "DEMO-001")
        if self.patient_id != "DEMO-001":
            raise RuntimeError("This demonstrator supports synthetic DEMO-001 only.")
        self.ehr_delay = float(os.getenv("EHR_DELAY_SECONDS", "2.5"))
        self.abg_delay = float(os.getenv("ABG_DELAY_SECONDS", "0.5"))
        self._history: list[tuple[str, str]] = []
        self._history_limit = int(os.getenv("CHAT_HISTORY_TURNS", "15"))
        self._events: dict[str, list[Callable[..., None]]] = {}
        self._tasks: set[asyncio.Task[Any]] = set()
        self._closing = False
        self._mic_attached = False
        self._speech_active = False
        self._anticipated_epoch: int | None = None
        self._anticipated_at = 0.0
        self._stt_input: Any | None = None
        self._stt_epoch: int | None = None
        self._sources: dict[str, rtc.AudioSource] = {}
        self._publications: dict[str, rtc.LocalTrackPublication] = {}
        self._seen_interrupt_ids: set[str] = set()
        # Mid-utterance pause/resume: active playout bookkeeping + leftover text.
        self._active_speech: dict[str, Any] | None = None
        self._remaining_speech: str | None = None
        # Instant resume: cached PCM of the current utterance + play cursor.
        # On "stop" we keep the synthesized frames so "continue" replays the
        # unspoken tail straight from memory — no Rime round-trip, no LLM.
        self._pending_buffer: _AudioBuffer | None = None
        self._pending_cursor: int = 0
        self._synth_task: asyncio.Task[Any] | None = None

    def on(self, name: str):
        def register(callback: Callable[..., None]):
            self._events.setdefault(name, []).append(callback)
            return callback
        return register

    def emit(self, name: str, *args: Any) -> None:
        for callback in self._events.get(name, []):
            callback(*args)

    def spawn(self, coro: Any) -> asyncio.Task[Any]:
        task = asyncio.create_task(coro)
        self._tasks.add(task)

        def finished(done: asyncio.Task[Any]) -> None:
            self._tasks.discard(done)
            if done.cancelled():
                return
            exc = done.exception()
            if exc is not None and not isinstance(exc, StaleEpochException):
                log.error(
                    "Background operation failed",
                    exc_info=(type(exc), exc, exc.__traceback__),
                )

        task.add_done_callback(finished)
        return task

    async def publish(self, event: dict[str, Any]) -> None:
        payload = json.dumps(event, separators=(",", ":")).encode()
        await self.room.local_participant.publish_data(
            payload,
            reliable=True,
            topic="scrubsync",
            destination_identities=[self.participant_identity],
        )

    def state(self, epoch: int, state: str, **extra: Any) -> None:
        if not self.epochs.is_current(epoch) or self._closing:
            return
        self.spawn(
            self.publish(
                {"type": "STATE", "epoch": epoch, "state": state, **extra}
            )
        )

    def _has_pending_audio(self) -> bool:
        """True when there is unspoken buffered PCM available for instant resume."""
        buf = self._pending_buffer
        if buf is None:
            return False
        return self._pending_cursor < buf.total_samples or not buf.complete.is_set()

    def _capture_remaining_speech(self) -> None:
        """Snapshot the unspoken PCM cursor the instant playback is cut.

        We keep the whole synthesized buffer and just remember how far playout
        got. "continue" replays frames from that cursor with no re-synthesis.
        A word-estimated text tail is kept only for the HUD / audit and for the
        "already finished" fallback.
        """
        active = self._active_speech
        if not active:
            return

        buf = active.get("buffer")
        played = int(active.get("played_samples") or 0)
        source = active.get("source")
        self._active_speech = None

        if not isinstance(buf, _AudioBuffer):
            return

        # Resume exactly at the acoustic cut. Frames we captured but that were
        # still queued (not yet played) get dropped by clear_queue() and never
        # reach the ear, so subtract the live queue depth rather than a guess.
        queued_s = TTS_QUEUE_TAIL_SEC
        if source is not None:
            try:
                queued_s = max(0.0, float(source.queued_duration))
            except Exception:
                queued_s = TTS_QUEUE_TAIL_SEC
        cursor = max(0, played - int(queued_s * buf.sample_rate))
        self._pending_buffer = buf
        self._pending_cursor = cursor

        remaining_text = remaining_speech_from_progress(
            buf.text, cursor, buf.sample_rate
        ).strip()
        self._remaining_speech = remaining_text or buf.text.strip() or None

        self.audit.write(
            "speech_paused",
            played_samples=played,
            cursor_samples=cursor,
            buffered_samples=buf.total_samples,
            synth_complete=buf.complete.is_set(),
            remaining_words=len(self._remaining_speech.split())
            if self._remaining_speech
            else 0,
            had_remaining=self._has_pending_audio(),
            remaining_preview=(
                self._remaining_speech[:180] if self._remaining_speech else ""
            ),
        )

    def _discard_pending_audio(self) -> None:
        """Drop any paused buffer + stop its synthesis (a new request abandons it)."""
        task = self._synth_task
        self._synth_task = None
        if task is not None and not task.done():
            task.cancel()
        self._pending_buffer = None
        self._pending_cursor = 0
        self._remaining_speech = None

    def interrupt(self, source: str, request_id: str | None = None) -> int:
        self._capture_remaining_speech()
        epoch = self.epochs.advance_epoch()
        self.audit.write(
            "interrupt",
            epoch=epoch,
            source=source,
            request_id=request_id,
            has_remaining=self._has_pending_audio(),
            remaining_words=len(self._remaining_speech.split())
            if self._remaining_speech
            else 0,
        )
        # clear_queue must not prevent interrupt bookkeeping / STT handoff
        try:
            for audio_source in tuple(self._sources.values()):
                try:
                    audio_source.clear_queue()
                except Exception:
                    log.exception("AudioSource.clear_queue failed during interrupt")
        except Exception:
            log.exception("Failed clearing audio sources during interrupt")
        self.spawn(
            self.publish(
                {
                    "type": "INTERRUPT_FLUSH",
                    "epoch": epoch,
                    "request_id": request_id,
                    "source": source,
                }
            )
        )
        self.state(epoch, "user")
        return epoch

    def local_interrupt(self, request_id: str) -> None:
        if request_id in self._seen_interrupt_ids:
            return
        if len(self._seen_interrupt_ids) >= 4096:
            self._seen_interrupt_ids.clear()
        self._seen_interrupt_ids.add(request_id)

        if self._speech_active:
            # VAD already fenced this same speech start.
            epoch = self.epochs.current_epoch
            self.spawn(
                self.publish(
                    {
                        "type": "INTERRUPT_FLUSH",
                        "epoch": epoch,
                        "request_id": request_id,
                        "source": "local-ack",
                    }
                )
            )
            return

        epoch = self.interrupt("browser-vad", request_id)
        self._anticipated_epoch = epoch
        self._anticipated_at = time.monotonic()

    def start(self) -> None:
        @self.on("user_started_speaking")
        def user_started_speaking() -> None:
            anticipated = self._anticipated_epoch
            recent = time.monotonic() - self._anticipated_at < 2.0
            if anticipated is not None and recent and self.epochs.is_current(anticipated):
                self._anticipated_epoch = None
                epoch = anticipated
            else:
                self._anticipated_epoch = None
                epoch = self.interrupt("silero")
            self._speech_active = True
            self._stt_epoch = epoch
            self.state(epoch, "user")

        @self.room.on("data_received")
        def on_data(packet: rtc.DataPacket) -> None:
            if packet.topic != "scrubsync":
                return
            if packet.participant is None:
                return
            if packet.participant.identity != self.participant_identity:
                return
            if len(packet.data) > 8192:
                return
            try:
                event = json.loads(packet.data)
                if not isinstance(event, dict):
                    return
                kind = event.get("type")
                if kind == "LOCAL_INTERRUPT":
                    request_id = event.get("request_id")
                    if isinstance(request_id, str) and 0 < len(request_id) <= 80:
                        self.local_interrupt(request_id)
                elif kind == "PLAYBACK_REPORT":
                    self.audit.write(
                        "client_playback",
                        epoch=event.get("epoch"),
                        segment_id=event.get("segment_id"),
                        disposition=event.get("disposition"),
                        rendered_non_silent_ms=event.get("rendered_non_silent_ms"),
                        local_cutoff_ms=event.get("local_cutoff_ms"),
                        # Receipt means rendered at the browser graph, not
                        # proven acoustic perception or word-level alignment.
                        measurement_boundary="browser_audio_graph",
                    )
            except (ValueError, TypeError):
                log.warning("Rejected malformed terminal data message")

        @self.room.on("track_subscribed")
        def track_subscribed(
            track: rtc.Track,
            publication: rtc.RemoteTrackPublication,
            participant: rtc.RemoteParticipant,
        ) -> None:
            if (
                participant.identity == self.participant_identity
                and track.kind == rtc.TrackKind.KIND_AUDIO
                and not self._mic_attached
            ):
                self._mic_attached = True
                self.spawn(self.ingest(track))

        participant = self.room.remote_participants.get(self.participant_identity)
        if participant is not None:
            for publication in participant.track_publications.values():
                if publication.track is not None:
                    track_subscribed(publication.track, publication, participant)
        self.state(self.epochs.current_epoch, "listening")

    async def ingest(self, track: rtc.Track) -> None:
        audio = rtc.AudioStream(track, sample_rate=16000, num_channels=1)
        vad_stream = self.vad.stream()

        async def feed() -> None:
            async for item in audio:
                frame = item.frame
                # Feed the currently active, epoch-bound recognition stream.
                current_input = self._stt_input
                if current_input is not None:
                    try:
                        current_input.push_frame(frame)
                    except RuntimeError:
                        if self._stt_input is current_input:
                            self._stt_input = None
                vad_stream.push_frame(frame)
            vad_stream.end_input()

        async def consume_vad() -> None:
            async for event in vad_stream:
                if event.type == vad.VADEventType.START_OF_SPEECH:
                    self.emit("user_started_speaking")
                    epoch = self._stt_epoch
                    if epoch is None:
                        continue
                    recognition = self.stt.stream()
                    self._stt_input = recognition
                    # VAD supplies leading context captured before the event.
                    for frame in event.frames:
                        recognition.push_frame(frame)
                    self.audit.write(
                        "vad_start",
                        epoch=epoch,
                        speech_duration=event.speech_duration,
                    )
                    self.spawn(self.collect_transcript(recognition, epoch))
                elif event.type == vad.VADEventType.END_OF_SPEECH:
                    self._speech_active = False
                    recognition = self._stt_input
                    self._stt_input = None
                    if recognition is not None:
                        try:
                            recognition.end_input()
                        except RuntimeError:
                            pass
                    epoch = self._stt_epoch
                    if epoch is not None:
                        self.audit.write("vad_end", epoch=epoch)

        feeder = asyncio.create_task(feed())
        consumer = asyncio.create_task(consume_vad())
        try:
            await asyncio.gather(feeder, consumer)
        finally:
            for task in (feeder, consumer):
                task.cancel()
            await asyncio.gather(feeder, consumer, return_exceptions=True)
            recognition = self._stt_input
            self._stt_input = None
            if recognition is not None:
                try:
                    recognition.end_input()
                except RuntimeError:
                    pass
            await vad_stream.aclose()
            await audio.aclose()
            self._mic_attached = False

    async def collect_transcript(self, recognition: Any, epoch: int) -> None:
        pieces: list[str] = []
        try:
            async def consume_recognition() -> None:
                async for event in recognition:
                    if event.type == stt.SpeechEventType.FINAL_TRANSCRIPT:
                        if event.alternatives:
                            text = event.alternatives[0].text.strip()
                            if text:
                                pieces.append(text)
                    elif event.type == stt.SpeechEventType.INTERIM_TRANSCRIPT:
                        if event.alternatives and self.epochs.is_current(epoch):
                            self.state(
                                epoch,
                                "user",
                                transcript=event.alternatives[0].text[:1000],
                            )
            await asyncio.wait_for(consume_recognition(), timeout=45)
            text = " ".join(pieces).strip()
            if text and self.epochs.is_current(epoch):
                self.audit.write("transcript", epoch=epoch, text=text)

                # Soft pause: barge-in already stopped audio and saved remaining text.
                if is_soft_pause_command(text):
                    self.audit.write(
                        "command_route",
                        epoch=epoch,
                        route="soft_pause",
                        has_remaining=bool(self._remaining_speech),
                    )
                    self.state(epoch, "listening")
                    return

                # Instant resume: replay buffered PCM — no LLM, no re-synthesis.
                if is_resume_command(text):
                    await self._resume_playback(epoch, route="resume")
                    return

                # TC-2: Instant fast-abort on cancel/abort phrases (<100ms)
                if is_hard_cancel_command(text):
                    self._discard_pending_audio()
                    self.audit.write(
                        "command_route",
                        epoch=epoch,
                        route="hard_cancel",
                    )
                    # Advance epoch to invalidate any pending tasks
                    new_epoch = self.epochs.advance_epoch()
                    # Purana transcript aur audio chunks ka queue turant drain karo
                    if hasattr(self, "_transcript_queue"):
                        while not self._transcript_queue.empty():
                            try:
                                self._transcript_queue.get_nowait()
                            except Exception:
                                break
                    self.audit.write("instant_cancel_triggered", epoch=new_epoch)
                    await self.speak(new_epoch, "Cancelled.")
                    self._remember(text, "Cancelled.")
                    return

                # New request abandons any paused leftover.
                self._discard_pending_audio()
                self.audit.write(
                    "command_route",
                    epoch=epoch,
                    route="respond",
                )
                await self.epochs.run_fenced_task(epoch, self.respond(epoch, text))
            elif text:
                self.audit.write("stale_transcript_rejected", epoch=epoch)
        except (StaleEpochException, asyncio.CancelledError):
            self.audit.write("utterance_revoked", epoch=epoch)
        except Exception:
            log.exception("Recognition/orchestration failed for epoch %s", epoch)
            self.state(epoch, "error", error="Voice request failed. Please repeat.")
        finally:
            if self._stt_input is recognition:
                self._stt_input = None
            await recognition.aclose()

    async def respond(self, epoch: int, transcript: str) -> None:
        self.epochs.assert_current(epoch)

        # Defense in depth: never LLM-plan pause/resume even if routing missed.
        if is_soft_pause_command(transcript):
            self.audit.write(
                "command_route",
                epoch=epoch,
                route="soft_pause_respond_guard",
                has_remaining=bool(self._remaining_speech),
            )
            self.state(epoch, "listening")
            return
        if is_resume_command(transcript):
            await self._resume_playback(epoch, route="resume_respond_guard")
            return

        self.state(epoch, "tool", tool="Planning response")

        @llm.function_tool
        async def check_electrolytes() -> dict[str, Any]:
            """Read the synthetic DEMO-001 electrolyte panel and potassium."""
            return await self.epochs.run_fenced_task(
                epoch,
                fetch_electrolyte_panel(self.patient_id, self.ehr_delay),
            )

        @llm.function_tool
        async def check_abg() -> dict[str, Any]:
            """Read the synthetic DEMO-001 arterial blood gas, pH, and pCO2."""
            return await self.epochs.run_fenced_task(
                epoch,
                fetch_arterial_blood_gas(self.patient_id, self.abg_delay),
            )

        @llm.function_tool
        async def search_web(query: str) -> dict[str, Any]:
            """Search the public web for live or current information such as sports scores, news, weather, or recent facts."""
            return await self.epochs.run_fenced_task(epoch, web_search(query))

        tools = [search_web, check_electrolytes, check_abg]
        context = llm.ChatContext()
        context.add_message(role="system", content=SYSTEM_PROMPT)
        for role, content in self._history[-(self._history_limit *2) :]:
            context.add_message(role=role, content=content)
        context.add_message(role="user", content=transcript[:4000])

        text_parts: list[str] = []
        calls: dict[str, tuple[str, str]] = {}
        first_token = True
        started = time.perf_counter_ns()

        async with asyncio.timeout(25):
            stream = self.llm.chat(chat_ctx=context, tools=tools)
            async with stream:
                async for chunk in stream:
                    self.epochs.assert_current(epoch)
                    delta = chunk.delta
                    if delta is None:
                        continue
                    if first_token and (delta.content or delta.tool_calls):
                        first_token = False
                        self.audit.write(
                            "qwen_first_delta",
                            epoch=epoch,
                            elapsed_ms=(time.perf_counter_ns() - started) / 1e6,
                        )
                    if delta.content:
                        text_parts.append(delta.content)
                    for call in delta.tool_calls or []:
                        calls[call.call_id] = (call.name, call.arguments)

        self.epochs.assert_current(epoch)
        if len(calls) > 1:
            spoken = "Please ask one thing at a time so I can answer clearly."
            await self.speak(epoch, spoken)
            self._remember(transcript, spoken)
            return

        if calls:
            name, arguments = next(iter(calls.values()))
            try:
                decoded = json.loads(arguments or "{}")
            except json.JSONDecodeError:
                spoken = "I could not interpret that request. Please repeat."
                await self.speak(epoch, spoken)
                self._remember(transcript, spoken)
                return

            self.state(epoch, "tool", tool=name)
            self.audit.write("tool_started", epoch=epoch, tool=name, arguments=decoded)

            async with asyncio.timeout(32):
                if name == "check_electrolytes":
                    if decoded != {}:
                        spoken = "Only the synthetic DEMO-001 chart is available for labs."
                        await self.speak(epoch, spoken)
                        self._remember(transcript, spoken)
                        return
                    result = await check_electrolytes()
                    spoken = (
                        "DEMO-001 electrolytes show potassium 3.1 milliequivalents "
                        "per liter, critically low. This needs prompt clinical review."
                    )
                    await self.publish({"type": "METRIC", "epoch": epoch, "result": result})
                elif name == "check_abg":
                    if decoded != {}:
                        spoken = "Only the synthetic DEMO-001 chart is available for labs."
                        await self.speak(epoch, spoken)
                        self._remember(transcript, spoken)
                        return
                    result = await check_abg()
                    spoken = (
                        "DEMO-001 blood gas shows pH 7.26 with acidosis, and carbon "
                        "dioxide 48 millimeters mercury. This needs prompt clinical review."
                    )
                    await self.publish({"type": "METRIC", "epoch": epoch, "result": result})
                elif name == "search_web":
                    query = str(decoded.get("query") or transcript).strip()[:200]
                    await self.speak(epoch, "Looking that up...")
                    result = await search_web(query)
                    self.epochs.assert_current(epoch)
                    self.audit.write("tool_committed", epoch=epoch, tool=name, result=result)
                    spoken = await self._speakable_from_search(epoch, transcript, result)
                    if spoken:
                        self._remember(transcript, spoken)
                else:
                    spoken = "That tool is unavailable right now."
                    await self.speak(epoch, spoken)
                    self._remember(transcript, spoken)
                    return

            self.epochs.assert_current(epoch)
            if name != "search_web":
                self.audit.write("tool_committed", epoch=epoch, tool=name, result=result)
            await self.speak(epoch, spoken)
            self._remember(transcript, spoken)
        else:
            response = " ".join("".join(text_parts).split()[:MAX_SPOKEN_WORDS]).strip()
            spoken = response or "Happy to help. What would you like to know?"
            await self.speak(epoch, spoken)
            self._remember(transcript, spoken)

    async def _speakable_from_search(
        self,
        epoch: int,
        transcript: str,
        result: dict[str, Any],
    ) -> str:
        """Turn web search payload into a short spoken answer."""
        self.epochs.assert_current(epoch)
        if not result.get("ok"):
            return (
                "I could not find reliable live info just now. "
                "Ask another way, or try again in a moment."
            )

        snippets: list[str] = []
        summary = str(result.get("summary") or "").strip()
        if summary:
            snippets.append(summary)
        for item in result.get("results") or []:
            title = str(item.get("title") or "").strip()
            if title:
                snippets.append(title)
        evidence = " | ".join(snippets)[:1800]

        context = llm.ChatContext()
        context.add_message(
            role="system",
            content=(
                "Convert the web evidence into a brief spoken answer for the user. "
                "Stay faithful to the evidence. Do not invent scores or facts. "
                f"Use at most {MAX_SPOKEN_WORDS} words."
            ),
        )
        context.add_message(
            role="user",
            content=(
                f"User asked: {transcript[:1000]}\n"
                f"Web evidence: {evidence}"
            ),
        )

        text_parts: list[str] = []
        async with asyncio.timeout(20):
            stream = self.llm.chat(chat_ctx=context, tools=[])
            async with stream:
                async for chunk in stream:
                    self.epochs.assert_current(epoch)
                    delta = chunk.delta
                    if delta is None or not delta.content:
                        continue
                    text_parts.append(delta.content)

        spoken = " ".join("".join(text_parts).split()[:MAX_SPOKEN_WORDS]).strip()
        return spoken or (
            summary[:400]
            if summary
            else "I found some results, but could not summarize them clearly."
        )

    def _remember(self, user_text: str, assistant_text: str) -> None:
        self._history.append(("user", user_text[:4000]))
        self._history.append(("assistant", assistant_text[:4000]))
        overflow = len(self._history) - self._history_limit * 2
        if overflow > 0:
            self._history = self._history[overflow:]

    def _start_synthesis(self, text: str) -> _AudioBuffer:
        """Synthesize the whole utterance into a buffer, ahead of playout.

        Rime streams faster than real time, so the buffer typically holds the
        entire answer within a couple of seconds — long before a "stop" lands —
        which is what makes "continue" resume instantly from memory. Filling is
        deliberately NOT epoch-fenced: it keeps running through a pause so the
        unspoken tail is available to replay.
        """
        self._discard_pending_audio()
        buf = _AudioBuffer(text)
        started_ns = time.perf_counter_ns()

        async def fill() -> None:
            first = True
            try:
                async with asyncio.timeout(60):
                    async with self.tts.synthesize(text) as synthesis:
                        async for event in synthesis:
                            frame = event.frame
                            if (
                                frame.sample_rate != buf.sample_rate
                                or frame.num_channels != 1
                            ):
                                raise RuntimeError(
                                    "Rime returned an unexpected PCM configuration."
                                )
                            if first:
                                first = False
                                self.audit.write(
                                    "rime_first_pcm",
                                    text_preview=text[:80],
                                    elapsed_ms=(
                                        time.perf_counter_ns() - started_ns
                                    ) / 1e6,
                                )
                            buf.frames.append(frame)
                            buf.total_samples += frame.samples_per_channel
            except asyncio.CancelledError:
                buf.failed = True
                raise
            except Exception:
                buf.failed = True
                log.exception("Rime synthesis failed")
            finally:
                buf.complete.set()

        self._synth_task = self.spawn(fill())
        return buf

    async def speak(self, epoch: int, text: str) -> None:
        """Speak a fresh answer, buffering PCM so stop/continue can replay it."""
        self.epochs.assert_current(epoch)
        units = split_speakable_units(text)
        if not units:
            return

        self.audit.write(
            "speech_intended",
            epoch=epoch,
            text=text,
            unit_count=len(units),
        )
        buf = self._start_synthesis(text)
        await self._play_buffer(epoch, buf, 0)

    async def _resume_playback(self, epoch: int, *, route: str) -> None:
        """Replay the unspoken buffered PCM from the pause cursor — no LLM/TTS."""
        buf = self._pending_buffer
        cursor = self._pending_cursor
        remaining_words = (
            len(self._remaining_speech.split()) if self._remaining_speech else 0
        )
        has_pending = self._has_pending_audio()
        self.audit.write(
            "command_route",
            epoch=epoch,
            route=route,
            has_remaining=has_pending,
            remaining_words=remaining_words,
        )
        if buf is not None and has_pending:
            self.audit.write(
                "speech_resume",
                epoch=epoch,
                cursor_samples=cursor,
                buffered_samples=buf.total_samples,
                remaining_words=remaining_words,
            )
            # Keep the buffer/synth alive; _play_buffer owns it now.
            self._pending_buffer = None
            self._pending_cursor = 0
            self._remaining_speech = None
            await self.epochs.run_fenced_task(
                epoch, self._play_buffer(epoch, buf, cursor)
            )
        else:
            self._discard_pending_audio()
            await self.epochs.run_fenced_task(
                epoch,
                self.speak(
                    epoch,
                    "I had already finished. What would you like next?",
                ),
            )

    async def _play_buffer(
        self, epoch: int, buf: _AudioBuffer, start_samples: int
    ) -> None:
        """Stream buffered PCM from ``start_samples`` at real-time pace.

        On interrupt we record how far playout got (``played_samples``) so the
        next "continue" resumes from exactly there. Frames already in ``buf``
        play with zero latency; if synthesis is still in flight we simply wait
        for the next frame — still no LLM and no second Rime request.
        """
        self.epochs.assert_current(epoch)
        segment_id = uuid.uuid4().hex
        track_name = f"rime.e{epoch}.s{segment_id}"
        # A generous jitter buffer keeps playout continuous even if synthesis or
        # the event loop hiccups mid-sentence — an empty queue makes LiveKit
        # emit concealment noise (the "whoosh"). Barge-in still cuts instantly
        # because interrupt() calls clear_queue(), and the resume cursor is
        # corrected by the live queue depth, so a larger queue is safe here.
        source = rtc.AudioSource(buf.sample_rate, 1, queue_size_ms=TTS_QUEUE_MS)
        track = rtc.LocalAudioTrack.create_audio_track(track_name, source)
        publication: rtc.LocalTrackPublication | None = None
        played_samples = start_samples
        interrupted = True
        hud_text = (
            remaining_speech_from_progress(buf.text, start_samples, buf.sample_rate)
            or buf.text
        )
        self._active_speech = {
            "buffer": buf,
            "played_samples": start_samples,
            "segment_id": segment_id,
            "source": source,
        }

        try:
            self._sources[segment_id] = source
            publication = await self.room.local_participant.publish_track(
                track,
                rtc.TrackPublishOptions(source=rtc.TrackSource.SOURCE_MICROPHONE),
            )
            self._publications[segment_id] = publication
            self.epochs.assert_current(epoch)
            await self.publish(
                {
                    "type": "AUDIO_READY",
                    "epoch": epoch,
                    "segment_id": segment_id,
                    "track_name": track_name,
                    "text": hud_text,
                    "engine": "Rime",
                    "model": "mist",
                    "speaker": "amber",
                    "audio_format": "pcm_24000",
                }
            )
            self.epochs.assert_current(epoch)
            self.state(epoch, "speaking")

            # Find the first frame at/after the resume cursor. We start on a
            # frame boundary at or before the cursor, so at most a few ms are
            # re-heard rather than dropped.
            index = 0
            consumed = 0
            while index < len(buf.frames) and (
                consumed + buf.frames[index].samples_per_channel <= start_samples
            ):
                consumed += buf.frames[index].samples_per_channel
                index += 1

            async with asyncio.timeout(120):
                while True:
                    self.epochs.assert_current(epoch)
                    if index < len(buf.frames):
                        frame = buf.frames[index]
                        index += 1
                        await source.capture_frame(frame)
                        self.epochs.assert_current(epoch)
                        played_samples += frame.samples_per_channel
                        if self._active_speech is not None:
                            self._active_speech["played_samples"] = played_samples
                    elif buf.complete.is_set():
                        if buf.failed and played_samples == start_samples:
                            raise RuntimeError("Rime synthesis produced no audio.")
                        break
                    else:
                        # Synthesis still streaming; wait for the next frame.
                        await asyncio.sleep(0.01)
                await source.wait_for_playout()
                self.epochs.assert_current(epoch)

            interrupted = False
            self._active_speech = None
            self._discard_pending_audio()
            await self.publish(
                {
                    "type": "AUDIO_END",
                    "epoch": epoch,
                    "segment_id": segment_id,
                    "generated_samples": played_samples,
                }
            )
            await asyncio.sleep(0.05)
            self.epochs.assert_current(epoch)
            self.state(epoch, "listening")
        except (StaleEpochException, asyncio.CancelledError):
            if (
                self._active_speech is not None
                and self._active_speech.get("segment_id") == segment_id
            ):
                self._active_speech["played_samples"] = played_samples
                self._capture_remaining_speech()
            raise
        finally:
            source.clear_queue()
            self._sources.pop(segment_id, None)
            self._publications.pop(segment_id, None)
            self.audit.write(
                "speech_closed",
                epoch=epoch,
                segment_id=segment_id,
                generated_samples=played_samples,
                interrupted=interrupted,
            )
            if publication is not None:
                try:
                    await self.room.local_participant.unpublish_track(publication.sid)
                except Exception:
                    log.exception("Failed to unpublish audio track")
            await source.aclose()

    async def close(self) -> None:
        if self._closing:
            return
        self._closing = True
        self.epochs.advance_epoch()
        for source in tuple(self._sources.values()):
            source.clear_queue()

        current = asyncio.current_task()
        remaining = tuple(task for task in self._tasks if task is not current)
        for task in remaining:
            task.cancel()
        await asyncio.gather(*remaining, return_exceptions=True)

        for client in (self.stt, self.tts, self.llm):
            close = getattr(client, "aclose", None)
            if close is not None:
                result = close()
                if inspect.isawaitable(result):
                    await result
        self.audit.close()


def prewarm(proc: agents.JobProcess) -> None:
    proc.userdata["vad"] = silero.VAD.load(
        min_speech_duration=0.10,      # Elevated from 0.15 to filter brief transient coughs
        min_silence_duration=0.35,
        prefix_padding_duration=0.25,
    )


async def entrypoint(ctx: agents.JobContext) -> None:
    required("DEEPGRAM_API_KEY")
    required("RIME_API_KEY")
    await ctx.connect(auto_subscribe=agents.AutoSubscribe.AUDIO_ONLY)
    participant = await ctx.wait_for_participant()
    assistant = VoiceAssistant(
        ctx.room,
        participant.identity,
        ctx.proc.userdata["vad"],
        interrupt_speech_duration=0.15,
    )
    ctx.add_shutdown_callback(assistant.close)
    assistant.start()

    @ctx.room.on("participant_disconnected")
    def participant_disconnected(remote: rtc.RemoteParticipant) -> None:
        if remote.identity == participant.identity:
            assistant.spawn(assistant.close())

    log.info("ScrubSync attached to terminal %s", participant.identity)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    agents.cli.run_app(
        agents.WorkerOptions(
            agent_name="scrubsync",
            entrypoint_fnc=entrypoint,
            prewarm_fnc=prewarm,
        )
    )
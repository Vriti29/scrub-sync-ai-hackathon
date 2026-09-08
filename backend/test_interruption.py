from __future__ import annotations

import asyncio
import json
import statistics
import time
import types
from pathlib import Path

import pytest

from backend.fencer import EpochManager, StaleEpochException
from backend.tools.ehr_service import (
    fetch_arterial_blood_gas,
    fetch_electrolyte_panel,
)


@pytest.mark.asyncio
async def test_exact_mid_tool_interruption_ten_trials() -> None:
    """
    Real elapsed measurements of coroutine cancellation, not acoustic cutoff.

    Every trial starts a 2.5-second EHR request, waits 500 ms, then advances
    from epoch 1 to epoch 2. No provider credentials are needed.
    """
    records = []

    for trial in range(1, 11):
        manager = EpochManager()
        assert manager.advance_epoch() == 1
        audio_queue: asyncio.Queue[dict] = asyncio.Queue()

        async def query_and_commit() -> None:
            result = await manager.run_fenced_task(
                1, fetch_electrolyte_panel("DEMO-001", 2.5)
            )
            manager.commit(1, lambda: audio_queue.put_nowait(result))

        task = asyncio.create_task(query_and_commit())
        await asyncio.sleep(0.5)

        started = time.perf_counter_ns()
        assert manager.advance_epoch() == 2
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, timeout=0.15)
        cancellation_ms = (time.perf_counter_ns() - started) / 1e6

        assert cancellation_ms < 150
        assert task.cancelled()
        assert audio_queue.empty()

        stale_rejected = False
        try:
            manager.commit(1, lambda: audio_queue.put_nowait({"stale": True}))
        except StaleEpochException:
            stale_rejected = True
        assert stale_rejected
        assert audio_queue.empty()

        records.append(
            {
                "trial": trial,
                "tool_delay_ms": 2500,
                "interrupt_after_ms": 500,
                "cancellation_ms": cancellation_ms,
                "stale_commit_rejected": stale_rejected,
                "stale_audio_queue_items": audio_queue.qsize(),
                "rime_ttfa_ms": None,
                "vad_acoustic_latency_ms": None,
                "acoustic_cutoff_ms": None,
            }
        )

    artifact = {
        "measurement_boundary": "Python task cancellation and fenced queue commit",
        "clock": "time.perf_counter_ns",
        "trial_count": len(records),
        "cancellation_p50_ms": statistics.median(
            record["cancellation_ms"] for record in records
        ),
        "cancellation_max_ms": max(record["cancellation_ms"] for record in records),
        "trials": records,
    }
    directory = Path("artifacts")
    directory.mkdir(exist_ok=True)
    (directory / "interruption-benchmark.json").write_text(
        json.dumps(artifact, indent=2), encoding="utf-8"
    )


@pytest.mark.asyncio
async def test_cancellation_resistant_tool_cannot_commit() -> None:
    manager = EpochManager(initial_epoch=1)
    started = asyncio.Event()
    cancellation_seen = asyncio.Event()
    audio_queue: asyncio.Queue[dict] = asyncio.Queue()

    async def cancellation_resistant_database() -> dict:
        started.set()
        try:
            await asyncio.sleep(2.5)
        except asyncio.CancelledError:
            cancellation_seen.set()
            # Reproduce an external operation that resolves after cancellation.
            await asyncio.sleep(0.02)
        return {"potassium": 3.1, "origin": "late database result"}

    async def run() -> None:
        result = await manager.run_fenced_task(
            1, cancellation_resistant_database()
        )
        manager.commit(1, lambda: audio_queue.put_nowait(result))

    task = asyncio.create_task(run())
    await started.wait()
    manager.advance_epoch()

    with pytest.raises(StaleEpochException):
        await asyncio.wait_for(task, timeout=1)

    assert cancellation_seen.is_set()
    assert manager.stale_rejections >= 1
    assert audio_queue.empty()


@pytest.mark.asyncio
async def test_new_epoch_abg_survives_old_epoch_cancellation() -> None:
    manager = EpochManager(initial_epoch=1)
    old = asyncio.create_task(
        manager.run_fenced_task(
            1, fetch_electrolyte_panel("DEMO-001", 2.5)
        )
    )
    await asyncio.sleep(0.01)
    manager.advance_epoch()
    result = await manager.run_fenced_task(
        2, fetch_arterial_blood_gas("DEMO-001", 0.01)
    )
    with pytest.raises(asyncio.CancelledError):
        await old
    assert result["panel"] == "abg"
    assert result["ph"]["value"] == 7.26
    assert result["pco2"]["value"] == 48


@pytest.mark.asyncio
async def test_already_stale_coroutine_is_closed() -> None:
    manager = EpochManager(initial_epoch=2)
    with pytest.raises(StaleEpochException):
        await manager.run_fenced_task(
            1, fetch_electrolyte_panel("DEMO-001", 0)
        )


@pytest.mark.asyncio
async def test_thread_originated_advance_cancels_owned_loop_task() -> None:
    manager = EpochManager(initial_epoch=1)
    task = asyncio.create_task(
        manager.run_fenced_task(
            1, fetch_electrolyte_panel("DEMO-001", 2.5)
        )
    )
    await asyncio.sleep(0.01)
    epoch = await asyncio.to_thread(manager.advance_epoch)
    assert epoch == 2
    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(task, 0.15)


@pytest.mark.asyncio
async def test_stale_result_cannot_cross_commit_race() -> None:
    manager = EpochManager(initial_epoch=1)
    result = await manager.run_fenced_task(
        1, fetch_electrolyte_panel("DEMO-001", 0)
    )
    manager.advance_epoch()
    committed: list[dict] = []
    with pytest.raises(StaleEpochException):
        manager.commit(1, lambda: committed.append(result))
    assert committed == []


@pytest.mark.asyncio
async def test_only_synthetic_patient_is_available() -> None:
    with pytest.raises(ValueError):
        await fetch_electrolyte_panel("REAL-PATIENT", 0)


class _Frame:
    def __init__(self, spc: int) -> None:
        self.samples_per_channel = spc
        self.sample_rate = 24000
        self.num_channels = 1


class _Source:
    def __init__(self, *_a, **_k) -> None:
        self.captured = 0

    async def capture_frame(self, _frame) -> None:
        self.captured += 1
        await asyncio.sleep(0.002)  # throttle so an interrupt can land mid-play

    def clear_queue(self) -> None:
        pass

    async def wait_for_playout(self) -> None:
        pass

    async def aclose(self) -> None:
        pass


def _build_assistant(monkeypatch, synth_counter: dict[str, int]):
    from backend import agent as agent_module

    class _Track:
        pass

    class _Pub:
        sid = "sid"

    class _LocalTrack:
        @staticmethod
        def create_audio_track(_name, _src):
            return _Track()

    class _Synth:
        def __init__(self, frames: int = 60, spc: int = 2400) -> None:
            self._frames = [_Frame(spc) for _ in range(frames)]

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_a):
            return False

        def __aiter__(self):
            async def gen():
                for frame in self._frames:
                    await asyncio.sleep(0)
                    yield types.SimpleNamespace(frame=frame)

            return gen()

    class _TTS:
        def synthesize(self, _text):
            synth_counter["n"] += 1
            return _Synth()

    monkeypatch.setattr(agent_module.rtc, "AudioSource", _Source)
    monkeypatch.setattr(agent_module.rtc, "LocalAudioTrack", _LocalTrack)
    monkeypatch.setattr(
        agent_module.rtc, "TrackPublishOptions", lambda **_k: None
    )
    monkeypatch.setattr(
        agent_module.rtc,
        "TrackSource",
        types.SimpleNamespace(SOURCE_MICROPHONE=0),
    )

    class _AuditStub:
        def write(self, *_a, **_k) -> None:
            pass

        def close(self) -> None:
            pass

    class _LP:
        async def publish_track(self, _t, _o):
            return _Pub()

        async def unpublish_track(self, _sid):
            pass

    assistant = object.__new__(agent_module.VoiceAssistant)
    assistant.epochs = EpochManager(initial_epoch=1)
    assistant.audit = _AuditStub()
    assistant._active_speech = None
    assistant._remaining_speech = None
    assistant._pending_buffer = None
    assistant._pending_cursor = 0
    assistant._synth_task = None
    assistant._sources = {}
    assistant._publications = {}
    assistant._tasks = set()
    assistant._closing = False
    assistant.tts = _TTS()
    assistant.room = types.SimpleNamespace(local_participant=_LP())
    assistant.state = lambda *_a, **_k: None

    async def _publish(_event) -> None:
        return None

    assistant.publish = _publish

    def _spawn(coro):
        task = asyncio.create_task(coro)
        assistant._tasks.add(task)
        task.add_done_callback(assistant._tasks.discard)
        return task

    assistant.spawn = _spawn
    return assistant


@pytest.mark.asyncio
async def test_continue_replays_cached_pcm_without_resynthesis(monkeypatch) -> None:
    """Stop then continue must replay buffered audio — no second TTS, no LLM."""
    synth_counter = {"n": 0}
    assistant = _build_assistant(monkeypatch, synth_counter)

    text = "Line one here. Line two here. Line three. Line four. Line five here."
    speak_task = asyncio.create_task(assistant.speak(1, text))

    # Let a few sentences play, then barge in with "stop".
    for _ in range(500):
        await asyncio.sleep(0.002)
        source = next(iter(assistant._sources.values()), None)
        if source is not None and source.captured >= 12:
            break

    assistant.interrupt("browser-vad", "stop-1")
    with pytest.raises(StaleEpochException):
        await asyncio.wait_for(speak_task, 1)

    assert synth_counter["n"] == 1
    assert assistant._pending_buffer is not None
    cursor = assistant._pending_cursor
    assert cursor > 0
    assert assistant._has_pending_audio()

    # Resume under a new epoch: replay from the cursor, no re-synthesis.
    resume_epoch = assistant.interrupt("browser-vad", "continue-1")
    assert assistant._pending_buffer is not None  # preserved across the interrupt
    await asyncio.wait_for(
        assistant._resume_playback(resume_epoch, route="resume"), 5
    )

    assert synth_counter["n"] == 1  # Rime was never called a second time
    assert assistant._pending_buffer is None
    assert assistant._active_speech is None
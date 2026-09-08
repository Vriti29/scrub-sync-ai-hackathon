import { useCallback, useEffect, useRef, useState } from "react";
import {
  Room,
  RoomEvent,
  Track,
  createLocalAudioTrack
} from "livekit-client";
import type {
  LocalAudioTrack,
  RemoteParticipant,
  RemoteTrack,
  RemoteTrackPublication
} from "livekit-client";

export type VoiceState =
  | "offline"
  | "listening"
  | "user"
  | "tool"
  | "speaking"
  | "error";

export interface ClinicalMetric {
  value: number;
  unit: string;
  flag: string;
}

export interface ClinicalResult {
  patient_id: string;
  synthetic: boolean;
  panel: "electrolytes" | "abg";
  potassium?: ClinicalMetric;
  ph?: ClinicalMetric;
  pco2?: ClinicalMetric;
}

interface AudioReady {
  epoch: number;
  segment_id: string;
  track_name: string;
  text: string;
}

interface MountedTrack {
  element: HTMLMediaElement;
  track: RemoteTrack;
}

interface Runtime {
  room: Room;
  context: AudioContext;
  gate: AudioWorkletNode;
  microphone: LocalAudioTrack;
  microphoneSource: MediaStreamAudioSourceNode;
  tracks: Map<string, MountedTrack>;
  ready: Map<string, AudioReady>;
  epoch: number;
  pendingInterrupt: string | null;
  allowedTrack: string | null;
  agentIdentity: string | null;
  timers: Set<ReturnType<typeof setTimeout>>;
  closed: boolean;
}

export interface TerminalView {
  connected: boolean;
  connecting: boolean;
  state: VoiceState;
  epoch: number;
  cutoffMs: number | null;
  transcript: string;
  intendedSpeech: string;
  tool: string;
  error: string;
  result: ClinicalResult | null;
  renderedMs: number;
}

const initialView: TerminalView = {
  connected: false,
  connecting: false,
  state: "offline",
  epoch: 0,
  cutoffMs: null,
  transcript: "",
  intendedSpeech: "",
  tool: "",
  error: "",
  result: null,
  renderedMs: 0
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isVoiceState(value: unknown): value is VoiceState {
  return [
    "offline",
    "listening",
    "user",
    "tool",
    "speaking",
    "error"
  ].includes(String(value));
}

function isMetric(value: unknown): value is ClinicalMetric {
  return (
    isRecord(value) &&
    typeof value.value === "number" &&
    Number.isFinite(value.value) &&
    typeof value.unit === "string" &&
    typeof value.flag === "string"
  );
}

function parseClinicalResult(value: unknown): ClinicalResult | null {
  if (
    !isRecord(value) ||
    value.synthetic !== true ||
    value.patient_id !== "DEMO-001"
  ) {
    return null;
  }
  if (value.panel === "electrolytes" && isMetric(value.potassium)) {
    return {
      patient_id: value.patient_id,
      synthetic: true,
      panel: "electrolytes",
      potassium: value.potassium
    };
  }
  if (value.panel === "abg" && isMetric(value.ph) && isMetric(value.pco2)) {
    return {
      patient_id: value.patient_id,
      synthetic: true,
      panel: "abg",
      ph: value.ph,
      pco2: value.pco2
    };
  }
  return null;
}

function mute(runtime: Runtime, disposition = "interrupted"): void {
  for (const mounted of runtime.tracks.values()) {
    mounted.element.volume = 0;
  }
  runtime.allowedTrack = null;
  runtime.gate.port.postMessage({ type: "mute", disposition });
}

function authorize(runtime: Runtime): void {
  if (runtime.closed || runtime.pendingInterrupt !== null) return;
  for (const [name, ready] of runtime.ready) {
    if (ready.epoch !== runtime.epoch) continue;
    const mounted = runtime.tracks.get(name);
    if (!mounted || runtime.allowedTrack === name) continue;
    mute(runtime, "replaced");
    runtime.allowedTrack = name;
    // Play through the attached element. Web-Audio taps on LiveKit remote
    // tracks were staying silent in Chromium (rendered_non_silent_ms=0).
    mounted.element.volume = 1;
    void mounted.element.play().catch(() => undefined);
    runtime.gate.port.postMessage({
      type: "allow",
      epoch: ready.epoch,
      segment_id: ready.segment_id
    });
    return;
  }
}

async function dispose(runtime: Runtime): Promise<void> {
  if (runtime.closed) return;
  runtime.closed = true;
  mute(runtime, "disconnected");
  for (const timer of runtime.timers) clearTimeout(timer);
  runtime.timers.clear();
  runtime.microphone.stop();
  runtime.microphoneSource.disconnect();
  for (const mounted of runtime.tracks.values()) {
    mounted.track.detach(mounted.element);
    mounted.element.remove();
  }
  runtime.tracks.clear();
  runtime.gate.disconnect();
  runtime.gate.port.close();
  await runtime.room.disconnect();
  if (runtime.context.state !== "closed") {
    await runtime.context.close();
  }
}

export function useLiveKitAudio() {
  const runtimeRef = useRef<Runtime | null>(null);
  const connectingRef = useRef(false);
  const generationRef = useRef(0);
  const aliveRef = useRef(true);
  const [view, setView] = useState<TerminalView>(initialView);

  const patch = useCallback((fields: Partial<TerminalView>) => {
    if (aliveRef.current) {
      setView((previous) => ({ ...previous, ...fields }));
    }
  }, []);

  const disconnect = useCallback(async () => {
    generationRef.current++;
    const runtime = runtimeRef.current;
    runtimeRef.current = null;
    if (runtime) await dispose(runtime);
    // Wipes conversation history when operator disarms/disconnects terminal
    localStorage.removeItem("scrubsync_conversation_history");
    sessionStorage.removeItem("scrubsync_conversation_history");
    window.dispatchEvent(new Event("storage_conversation_update"));
    patch({ ...initialView });
  }, [patch]);

  const connect = useCallback(
    async (accessSecret: string) => {
      if (connectingRef.current || runtimeRef.current) return;
      connectingRef.current = true;
      const generation = ++generationRef.current;
      patch({ ...initialView, connecting: true });

      let context: AudioContext | null = null;
      let microphone: LocalAudioTrack | null = null;
      let provisionalRuntime: Runtime | null = null;

      try {
        if (!window.isSecureContext || !navigator.mediaDevices) {
          throw new Error("Microphone access requires HTTPS or localhost.");
        }
        if (!accessSecret.trim()) {
          throw new Error("Enter the terminal provisioning secret.");
        }

        // Resume in the user activation handler, before network work.
        context = new AudioContext({
          sampleRate: 24000,
          latencyHint: "interactive"
        });
        await context.resume();
        await context.audioWorklet.addModule("/duplex-gate.js");

        const tokenResponse = await fetch(
          import.meta.env.VITE_TOKEN_URL || "http://localhost:8080/token",
          {
            method: "POST",
            headers: {
              Authorization: `Bearer ${accessSecret.trim()}`
            },
            signal: AbortSignal.timeout(10000)
          }
        );
        const tokenData: unknown = await tokenResponse.json();
        if (!tokenResponse.ok) {
          throw new Error(
            isRecord(tokenData) && typeof tokenData.error === "string"
              ? tokenData.error
              : "Terminal authorization failed."
          );
        }
        if (
          !isRecord(tokenData) ||
          typeof tokenData.url !== "string" ||
          typeof tokenData.token !== "string"
        ) {
          throw new Error("Invalid token-service response.");
        }

        microphone = await createLocalAudioTrack({
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: false,
          channelCount: 1
        });

        const gate = new AudioWorkletNode(context, "duplex-gate", {
          numberOfInputs: 1,
          numberOfOutputs: 1,
          outputChannelCount: [1],
          channelCount: 1,
          channelCountMode: "explicit",
          processorOptions: {
            threshold: Number(
              import.meta.env.VITE_MIC_RMS_THRESHOLD || "0.05"
            )
          }
        });
        // Mic energy only — remote Rime audio plays via HTMLMediaElement.
        gate.connect(context.destination);

        const microphoneSource = context.createMediaStreamSource(
          new MediaStream([microphone.mediaStreamTrack])
        );
        microphoneSource.connect(gate, 0, 0);

        const room = new Room({
          adaptiveStream: false,
          dynacast: false
        });

        const runtime: Runtime = {
          room,
          context,
          gate,
          microphone,
          microphoneSource,
          tracks: new Map(),
          ready: new Map(),
          epoch: 0,
          pendingInterrupt: null,
          allowedTrack: null,
          agentIdentity: null,
          timers: new Set(),
          closed: false
        };
        provisionalRuntime = runtime;

        const send = (message: Record<string, unknown>) => {
          if (runtime.closed) return;
          void room.localParticipant
            .publishData(new TextEncoder().encode(JSON.stringify(message)), {
              reliable: true,
              topic: "scrubsync"
            })
            .catch(() => {
              mute(runtime);
              patch({
                state: "error",
                error: "Control channel failed; audio remains muted."
              });
            });
        };

        gate.port.onmessage = (message: MessageEvent<unknown>) => {
          const data = message.data;
          if (!isRecord(data) || runtime.closed) return;
          if (data.type === "speech_start") {
            const requestId = crypto.randomUUID();
            runtime.pendingInterrupt = requestId;
            mute(runtime);
            
            // Purane audio chunks ko turant clear karo
            runtime.ready.clear();

            patch({
              state: "user",
              result: null,
              intendedSpeech: "",
              cutoffMs:
                typeof data.local_cutoff_ms === "number"
                  ? data.local_cutoff_ms
                  : null
            });
            
            send({
              type: "LOCAL_INTERRUPT",
              request_id: requestId
            });

            // 150ms fallback: Agar server ACK thoda late ho, tab bhi naya speech sunna block na ho
            const fallbackTimer = setTimeout(() => {
              if (runtime.pendingInterrupt === requestId) {
                runtime.pendingInterrupt = null;
              }
              runtime.timers.delete(fallbackTimer);
            }, 150);
            runtime.timers.add(fallbackTimer);
          }
        };

        const mount = (
          track: RemoteTrack,
          publication: RemoteTrackPublication,
          participant: RemoteParticipant
        ) => {
          if (track.kind !== Track.Kind.Audio || !participant.isAgent) return;
          if (
            runtime.agentIdentity !== null &&
            runtime.agentIdentity !== participant.identity
          ) {
            return;
          }
          runtime.agentIdentity = participant.identity;
          const name = publication.trackName;
          if (!/^rime\.e\d+\.s[a-f0-9]+$/.test(name)) return;
          if (runtime.tracks.has(name)) return;

          const element = track.attach();
          element.autoplay = true;
          element.setAttribute("playsinline", "true");
          element.volume = 0;
          element.style.display = "none";
          document.body.appendChild(element);
          void element.play().catch(() => undefined);
          runtime.tracks.set(name, { element, track });
          authorize(runtime);
        };

        room.on(RoomEvent.TrackSubscribed, mount);

        room.on(
          RoomEvent.TrackUnsubscribed,
          (_track: RemoteTrack, publication: RemoteTrackPublication) => {
            const name = publication.trackName;
            const mounted = runtime.tracks.get(name);
            if (mounted) {
              mounted.element.volume = 0;
              mounted.track.detach(mounted.element);
              mounted.element.remove();
              runtime.tracks.delete(name);
            }
            runtime.ready.delete(name);
            if (runtime.allowedTrack === name) {
              mute(runtime, "track-ended");
            }
          }
        );

        room.on(
          RoomEvent.DataReceived,
          (
            payload: Uint8Array,
            participant?: RemoteParticipant,
            _kind?: unknown,
            topic?: string
          ) => {
            if (
              topic !== "scrubsync" ||
              !participant?.isAgent ||
              payload.byteLength > 16384
            ) {
              return;
            }
            if (
              runtime.agentIdentity !== null &&
              runtime.agentIdentity !== participant.identity
            ) {
              return;
            }
            runtime.agentIdentity = participant.identity;

            let data: unknown;
            try {
              data = JSON.parse(new TextDecoder().decode(payload));
            } catch {
              return;
            }
            if (
              !isRecord(data) ||
              typeof data.epoch !== "number" ||
              !Number.isSafeInteger(data.epoch) ||
              data.epoch < runtime.epoch
            ) {
              return;
            }

            if (data.type === "INTERRUPT_FLUSH") {
              runtime.epoch = data.epoch;
              mute(runtime);
              for (const [name, ready] of runtime.ready) {
                if (ready.epoch < runtime.epoch) runtime.ready.delete(name);
              }
              if (data.request_id === runtime.pendingInterrupt) {
                runtime.pendingInterrupt = null;
              }
              patch({
                epoch: runtime.epoch,
                state: "user",
                result: null,
                intendedSpeech: ""
              });
              authorize(runtime);
              return;
            }

            // A new epoch may arrive before its reliable flush event.
            // Advance fail-closed, but keep the local request ACK requirement.
            if (data.epoch > runtime.epoch) {
              runtime.epoch = data.epoch;
              mute(runtime);
              for (const [name, ready] of runtime.ready) {
                if (ready.epoch < runtime.epoch) runtime.ready.delete(name);
              }
              patch({
                epoch: runtime.epoch,
                result: null,
                intendedSpeech: ""
              });
            }
            if (data.type === "STATE" && isVoiceState(data.state)) {
              if (runtime.pendingInterrupt === null) {
                patch({
                  state: data.state,
                  transcript:
                    typeof data.transcript === "string"
                      ? data.transcript
                      : "",
                  tool: typeof data.tool === "string" ? data.tool : "",
                  error: typeof data.error === "string" ? data.error : ""
                });

                // === CAPTURE USER TRANSCRIPT TURN ===
                if (data.state === "user" && typeof data.transcript === "string" && data.transcript.trim()) {
                  try {
                    const key = "scrubsync_conversation_history";
                    const saved = JSON.parse(localStorage.getItem(key) || "[]");
                    saved.push({
                      id: crypto.randomUUID(),
                      sender: "user",
                      text: data.transcript.trim(),
                      timestamp: Date.now(),
                      epoch: data.epoch
                    });
                    localStorage.setItem(key, JSON.stringify(saved));
                    window.dispatchEvent(new Event("storage_conversation_update"));
                  } catch (e) {
                    console.error("Failed to store user turn", e);
                  }
                }
                // =====================================
              }
            } else if (data.type === "AUDIO_READY") {
              if (
                typeof data.segment_id !== "string" ||
                typeof data.track_name !== "string" ||
                typeof data.text !== "string" ||
                data.track_name !==
                  `rime.e${data.epoch}.s${data.segment_id}` ||
                data.engine !== "Rime" ||
                data.model !== "mist" ||
                data.speaker !== "amber" ||
                data.audio_format !== "pcm_24000"
              ) {
                return;
              }

              // === CAPTURE ASSISTANT SPOKEN TURN ===
              try {
                const key = "scrubsync_conversation_history";
                const saved = JSON.parse(localStorage.getItem(key) || "[]");
                saved.push({
                  id: crypto.randomUUID(),
                  sender: "assistant",
                  text: data.text.trim(),
                  timestamp: Date.now(),
                  epoch: data.epoch
                });
                localStorage.setItem(key, JSON.stringify(saved));
                window.dispatchEvent(new Event("storage_conversation_update"));
              } catch (e) {
                console.error("Failed to store assistant turn", e);
              }
              // =====================================
              runtime.ready.set(data.track_name, {
                epoch: data.epoch,
                segment_id: data.segment_id,
                track_name: data.track_name,
                text: data.text
              });
              if (runtime.pendingInterrupt === null) {
                patch({ intendedSpeech: data.text });
              }
              authorize(runtime);
            } else if (data.type === "AUDIO_END") {
              const endingEpoch = data.epoch;
              const segmentId = data.segment_id;
              const timer = setTimeout(() => {
                runtime.timers.delete(timer);
                if (
                  runtime.epoch === endingEpoch &&
                  runtime.allowedTrack?.endsWith(`.s${String(segmentId)}`)
                ) {
                  runtime.gate.port.postMessage({
                    type: "report",
                    disposition: "server-completed"
                  });
                }
              }, 200);
              runtime.timers.add(timer);
            } else if (
              data.type === "METRIC" &&
              runtime.pendingInterrupt === null
            ) {
              const result = parseClinicalResult(data.result);
              if (result) patch({ result });
            }
          }
        );

        room.on(RoomEvent.Reconnecting, () => {
          mute(runtime);
          patch({
            state: "error",
            error: "Reconnecting. Audio is fail-closed."
          });
        });

        room.on(RoomEvent.Reconnected, () => {
          runtime.ready.clear();
          runtime.pendingInterrupt = null;
          mute(runtime);
          patch({
            state: "listening",
            error: "Connection restored. Repeat your request."
          });
        });

        room.on(RoomEvent.Disconnected, () => {
          if (!runtime.closed) {
            mute(runtime);
            patch({
              connected: false,
              state: "error",
              error: "Transport disconnected. Re-arm the terminal."
            });
            if (runtimeRef.current === runtime) {
              runtimeRef.current = null;
            }
            void dispose(runtime);
          }
        });

        await room.connect(tokenData.url, tokenData.token);
        await room.localParticipant.publishTrack(microphone, {
          source: Track.Source.Microphone
        });

        if (
          generation !== generationRef.current ||
          !aliveRef.current
        ) {
          await dispose(runtime);
          return;
        }

        runtimeRef.current = runtime;
        patch({
          connected: true,
          connecting: false,
          state: "listening"
        });
      } catch (error) {
        if (provisionalRuntime) {
          await dispose(provisionalRuntime).catch(() => undefined);
        } else {
          microphone?.stop();
          if (context && context.state !== "closed") {
            await context.close().catch(() => undefined);
          }
        }
        patch({
          connected: false,
          connecting: false,
          state: "error",
          error:
            error instanceof Error
              ? error.message
              : "Terminal connection failed."
        });
      } finally {
        connectingRef.current = false;
        patch({ connecting: false });
      }
    },
    [patch]
  );

  useEffect(() => {
    aliveRef.current = true;
    return () => {
      aliveRef.current = false;
      generationRef.current++;
      const runtime = runtimeRef.current;
      runtimeRef.current = null;
      if (runtime) void dispose(runtime);
    };
  }, []);

  return { ...view, connect, disconnect };
}
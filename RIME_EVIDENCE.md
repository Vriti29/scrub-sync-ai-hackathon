# ScrubSync AI — Rime Track Evidence

Team: HTTP200  
Event: DataForge Hackathon, IIT Kharagpur  
Status: runnable synthetic-data demonstrator; deployment measurements pending

## 1. Hard Voice Claim

ScrubSync addresses full-duplex interruption and asynchronous state fencing
during latent clinical-data lookup.

In a sterile field, gloves cannot operate ordinary input devices without
breaking workflow, and visual attention belongs on the patient, instruments,
and monitors. After pre-sterile provisioning, clinical requests and cancellation
require no buttons, text entry, or screen reading.

Removing speech removes the operational interaction channel. The HUD is
observability for a wall monitor and judges, not the primary interface.

This is a demonstration with synthetic patient DEMO-001. It is not a medical
device, treatment recommender, validated diagnostic system, or emergency
fallback.

## 2. Active Configuration

| Component | Configuration |
|---|---|
| Primary and only spoken output | Rime |
| Rime model | mist |
| Rime speaker | amber |
| Agent audio format | pcm_24000: mono signed PCM frames at 24,000 Hz |
| Transport | LiveKit WebRTC media and reliable data messages |
| WebRTC codec | Negotiated by LiveKit; normally Opus |
| Browser render graph | AudioContext requested at 24,000 Hz |
| Speech recognition | Deepgram nova-2 |
| Server VAD | Silero |
| Server speech-start threshold | 150 ms minimum speech duration |
| Local emergency gate | AudioWorklet energy detector, 30 ms attack |
| Orchestration | Qwen 2.5 via OpenAI-compatible streaming endpoint |
| Tools | Synthetic electrolyte and arterial blood gas services |
| Authority boundary | Monotonic epoch plus epoch-labelled playback track |

There is no browser speechSynthesis fallback, prerecorded response fallback,
or secondary TTS provider.

The Rime plugin receives model="mist", speaker="amber", sample_rate=24000.
The logical pcm_24000 label is not passed as an unsupported plugin keyword.

Provider access to this exact model and voice must be checked before recording.
An unavailable Rime configuration causes a visible failure, not substitution.

## 3. Interruption and Fencing Protocol

1. Local microphone speech crosses the AudioWorklet energy threshold.
2. The rendering thread closes its output gate without a server round trip.
3. The browser sends LOCAL_INTERRUPT with a unique request ID.
4. The worker advances the epoch and cancels registered asynchronous work.
5. The worker clears its local audio-source queue.
6. The worker sends INTERRUPT_FLUSH with the epoch and request acknowledgment.
7. Server Silero segments the utterance. Its independent speech-start path also
   fences work if the local detector did not trigger.
8. Each Deepgram stream belongs to the epoch of its own VAD utterance.
9. Tool completion is checked against the current epoch.
10. Every spoken segment uses a new audio track named with its epoch.
11. The browser requires a matching AUDIO_READY event and track name.
12. Stale control messages and old-epoch tracks remain unauthorized.

Cancellation is an optimization. Epoch validation is the correctness mechanism.

RTP and data-channel messages are not assumed to arrive in matching order.

## 4. Acceptance Tests

### A. Cooperative delayed tool

Run:

    python -m pytest backend/test_interruption.py -q

For each of ten trials:

1. Advance to epoch 1.
2. Start fetch_electrolyte_panel with a 2.5-second delay.
3. Wait 500 milliseconds.
4. Advance to epoch 2.
5. Await cancellation with a 150-millisecond timeout.
6. Assert cancellation elapsed time is below 150 milliseconds.
7. Assert no old result was inserted into the downstream queue.
8. Attempt a stale commit explicitly and assert rejection.

Artifact:

    artifacts/interruption-benchmark.json

This measures Python cancellation and queue fencing, not acoustic audio cutoff.

### B. Cancellation-resistant completion

The test tool catches CancelledError and deliberately resolves afterward.

Acceptance:

- run_fenced_task raises StaleEpochException;
- no result reaches the authorized queue.

This reproduces an external request whose completion cannot be cancelled.

### C. Live mid-query replacement

1. Arm the terminal before entering the sterile workflow.
2. Say: "Check electrolytes."
3. Confirm the tool-active state.
4. Approximately 500 milliseconds later say:
   "Wait, cancel that. Check arterial blood gas pH instead."
5. Confirm an epoch advance.
6. Confirm the pH 7.26 and pCO2 48 fixture is returned.
7. Confirm potassium is never spoken for the cancelled epoch.
8. Inspect audit events and playback receipts.

Repeat ten times.

Acceptance:

- zero stale-epoch authorized playback segments;
- zero stale electrolyte responses after replacement;
- ABG response belongs to the replacement epoch.

### D. Acoustic cutoff

This requires physical or virtual audio loopback. The Python test cannot prove it.

Capture, on a common sample clock:

- the microphone speech onset signal;
- actual terminal speaker output.

For each trial:

1. Make Rime speak.
2. Interrupt while speech is audible.
3. Mark acoustic user-speech onset.
4. Mark the end of the interrupted Rime signal at the output.
5. Compute the elapsed time.
6. Save the recording and annotations.

Acceptance target:

    acoustic cutoff <= 150 ms in every recorded trial

Report maximum as well as median and p95. Do not subtract network or output
device latency from the acoustic measurement.

The HUD's local cutoff measurement excludes device buffering and acoustic
propagation. It must not be presented as the acoustic acceptance result.

## 5. Benchmark Measurement Definitions

- Rime first PCM: synthesis invocation to first PCM frame in the worker.
- End-to-end TTFA: acoustic end of user request to first audible response.
- VAD latency: acoustic speech onset to observed server VAD event.
- Local gate cutoff: sustained local energy onset to render-graph mute.
- Acoustic cutoff: acoustic interruption onset to last old-response audio.
- Tool cancellation: epoch advancement to cancelled coroutine completion.
- Stale leakage: stale authorized outputs divided by interruption attempts.

Sub-50 ms Qwen generation is a deployment target, not a guaranteed property
of the model or this code.

## 6. Ten-Trial Deployment Table

No deployment or acoustic measurements have been executed by the code author.
"Not measured" is intentional and is not a fabricated benchmark.

| Trial | End-to-end TTFA ms | Server VAD latency ms | Acoustic cutoff ms |
|---:|---:|---:|---:|
| 1 | Not measured | Not measured | Not measured |
| 2 | Not measured | Not measured | Not measured |
| 3 | Not measured | Not measured | Not measured |
| 4 | Not measured | Not measured | Not measured |
| 5 | Not measured | Not measured | Not measured |
| 6 | Not measured | Not measured | Not measured |
| 7 | Not measured | Not measured | Not measured |
| 8 | Not measured | Not measured | Not measured |
| 9 | Not measured | Not measured | Not measured |
| 10 | Not measured | Not measured | Not measured |

Populate this table only from saved recordings and timestamped artifacts.

The automated ten-trial cancellation measurements are generated separately in
artifacts/interruption-benchmark.json when pytest runs.

## 7. What Was Intended, Rendered, and Interrupted

The audit records:

- intended speech text and segment ID;
- epoch and Rime generation timing;
- generated PCM sample count;
- server completion or interruption;
- browser non-silent rendered sample duration;
- browser interruption receipts.

These categories are intentionally distinct.

Browser rendering does not prove that a human heard the audio. Output devices
may buffer samples, be muted, or be disconnected.

Rime word-alignment timestamps are not available through this implementation.
Therefore an interrupted segment is not falsely presented as an exact
word-level "heard transcript."

For exact audible-prefix evaluation, retain loopback recordings and align
them offline. The current audit supports segment-level reconciliation.

## 8. Known Limitations

- Not validated for clinical use, emergency response, or patient care.
- No real EHR integration or patient authentication.
- The potassium critical flag is an explicit competition fixture, not a
  universal laboratory threshold.
- Operating-room noise, particularly above 85 dB, can compromise recognition.
  No 85 dB performance certification is claimed.
- The local detector is an energy gate. It can falsely trigger on noise or
  miss very quiet speech.
- Echo cancellation is browser/device dependent. Use a close-talk headset.
- A 150 ms server VAD threshold alone cannot guarantee 150 ms acoustic cutoff.
  The independent local rendering gate is necessary.
- Browser output buffers and Bluetooth devices can exceed the cutoff budget.
- Per-segment WebRTC track publication adds overhead and may increase TTFA.
- The leading-context handoff from VAD to STT may contain a small overlap.
- Reconnection is fail-closed; the operator must repeat the request.
- One terminal per demonstration room is supported.
- Epoch authority is process-local. Multi-worker active/active authority would
  require a shared fencing lease and worker-incarnation identifier.
- A worker restart requires re-arming the terminal.
- No HIPAA, regulatory, penetration-test, or formal safety certification exists.

## 9. Evidence Checklist

Before submission, retain:

- source commit hash;
- Python and Node dependency lock snapshots;
- Rime account configuration evidence;
- ten-trial cancellation JSON;
- ten acoustic loopback recordings with annotations;
- audit JSONL;
- deployment machine, browser, microphone, and output-device specifications;
- a video showing normal operation and deliberate interruption.

Do not submit pending measurements as passed acceptance criteria.
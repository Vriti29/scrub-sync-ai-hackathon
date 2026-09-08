# ScrubSync AI

**Team HTTP200 · DataForge Hackathon · IIT Kharagpur · Rime Track**

A voice-native sterile-field demonstrator for full-duplex interruption and
epoch-fenced asynchronous tools.

**Synthetic data only. Not for clinical use.**

## Why voice is necessary

A sterile operator cannot use ordinary input devices without disrupting the
workflow. Attention belongs on the patient field, not a conversational UI.

A non-sterile assistant provisions the terminal before use. After that,
requests, replacement requests, and cancellation are spoken.

The screen is a wall-mounted status and judging display. It is not a required
interaction channel.

## Architecture

    Microphone
       |
       +--> Browser AudioWorklet emergency gate
       |         |
       |         +--> Immediate local output mute
       |         +--> LOCAL_INTERRUPT data message
       |
       +--> LiveKit WebRTC
                 |
                 +--> Silero VAD
                 +--> Per-utterance Deepgram nova-2 stream
                 +--> Qwen 2.5 streaming tool planner
                 +--> Epoch-fenced synthetic EHR tool
                 +--> Rime mist / amber / 24 kHz PCM
                 +--> Epoch-labelled WebRTC audio track
                               |
                               +--> Browser authorization gate
                               +--> Speaker

There are two independent interruption boundaries:

1. The browser rendering thread mutes locally, without a network round trip.
2. The worker revokes old work through monotonic epoch fencing.

Cancellation is best-effort. A late result still cannot pass the epoch check.

Each Rime utterance uses a distinct track name containing its epoch. This
avoids assuming RTP audio and data messages share an ordering boundary.

## Important API and transport details

This project uses the LiveKit Agents 1.2 release family.

The old framework VoiceAssistant API and newer AgentSession APIs are not mixed.
backend.agent.VoiceAssistant is this project's explicit orchestration runtime,
hosted by a LiveKit worker.

Rime is configured with:

    model="mist"
    speaker="amber"
    sample_rate=24000

The corresponding logical audio format is pcm_24000.

The Rime plugin emits PCM audio frames. LiveKit transports WebRTC audio,
normally encoded as Opus. Raw 24 kHz PCM is not the WebRTC wire codec.

No alternative TTS engine is configured.

## Requirements

- Python 3.11 or 3.12
- Node.js 20.19+ or 22.12+
- LiveKit Cloud or a reachable LiveKit server
- Rime account authorized for mist and amber
- Deepgram API key
- A Qwen 2.5 Instruct endpoint with compatible streaming tool calling
- Chromium-based desktop browser recommended
- A close-talk headset strongly recommended

Use localhost for local development. Remote microphone access requires HTTPS.

## Quickstart

### 1. Environment

    cp .env.example .env
    python -m venv .venv
    source .venv/bin/activate
    python -m pip install --upgrade pip
    pip install -r requirements.txt

On Windows PowerShell:

    .venv\Scripts\Activate.ps1

Set provider credentials and generate TERMINAL_ACCESS_SECRET:

    python -c "import secrets; print(secrets.token_urlsafe(32))"

Use this generated value only for terminal provisioning. Provider credentials
never enter the frontend bundle.

### 2. Download Silero assets

From the repository root:

    python -m backend.agent download-files

### 3. Start the token service

    python -m backend.token_server

Default endpoint:

    http://localhost:8080/token

The endpoint requires:

    Authorization: Bearer <TERMINAL_ACCESS_SECRET>

It issues short-lived room-scoped LiveKit credentials, not provider keys.

### 4. Start the LiveKit worker

In another activated Python shell:

    python -m backend.agent dev

For a hosted worker process:

    python -m backend.agent start

The worker uses automatic room dispatch. Run only this worker type against the
demonstration deployment, or configure dispatch explicitly in your infrastructure.

### 5. Start the frontend

    cd frontend
    npm install
    npm run dev

Open:

    http://localhost:5173

Enter the terminal provisioning secret and choose “Arm hands-free terminal.”
Grant microphone permission.

After arming, use voice.

### 6. Speak

Normal flow:

    "Check electrolytes."

Expected synthetic response:

    "Synthetic potassium 3.1 milliequivalents per liter. Critical low flag."

Interruption flow:

    "Check electrolytes."

Approximately half a second later:

    "Wait, cancel that. Check arterial blood gas pH instead."

Expected replacement response:

    "Synthetic pH 7.26, acidosis. Carbon dioxide 48 millimeters mercury."

The cancelled potassium response must not play.

If the Qwen endpoint does not support tool calling, the request fails visibly.
The application does not silently substitute a rule-based fake planner.

## Qwen endpoint configuration

OPENAI_API_BASE must identify an OpenAI-compatible endpoint.

Examples include a local vLLM deployment or a provider exposing the exact Qwen
model through its compatible API.

Configure QWEN_MODEL with the endpoint's actual model identifier.

For vLLM, enable the tool parser and automatic tool-choice options appropriate
to the installed vLLM version and Qwen model. Validate native tool calling
before the demonstration.

The code streams planner deltas and records the first delta timestamp.

It buffers the short final answer before synthesis rather than speaking an
uncommitted tool preamble. This trades some TTFA for deterministic interruption
and factual clinical readout.

A sub-50 ms token-generation target depends on hardware, batching, routing,
and endpoint load. It is not guaranteed.

## Environment variables

| Variable | Purpose |
|---|---|
| LIVEKIT_URL | LiveKit WebSocket URL |
| LIVEKIT_API_KEY | Server-side LiveKit signing key |
| LIVEKIT_API_SECRET | Server-side LiveKit signing secret |
| RIME_API_KEY | Rime authentication |
| DEEPGRAM_API_KEY | Deepgram authentication |
| OPENAI_API_BASE | Qwen-compatible API base |
| OPENAI_API_KEY | Qwen endpoint authentication |
| QWEN_MODEL | Endpoint model identifier |
| ROOM_NAME | Single demonstration room |
| TERMINAL_ACCESS_SECRET | Pre-sterile terminal provisioning credential |
| TOKEN_HOST | Token service bind address |
| TOKEN_PORT | Token service port |
| FRONTEND_ORIGIN | Exact browser origin allowed by token service |
| PATIENT_ID | Must remain DEMO-001 |
| EHR_DELAY_SECONDS | Cooperative electrolyte lookup latency |
| ABG_DELAY_SECONDS | Cooperative blood-gas lookup latency |
| AUDIT_PATH | Operational audit file |
| VITE_TOKEN_URL | Public token endpoint URL |
| VITE_MIC_RMS_THRESHOLD | Local energy-gate threshold |

Vite exposes only VITE-prefixed variables.

Never put provider credentials in VITE-prefixed variables.

## Automated tests

From the repository root:

    python -m pytest backend/test_interruption.py -q

Coverage includes:

- ten exact 2.5-second query / 500-millisecond interruption trials;
- cancellation latency below 150 milliseconds;
- explicit stale queue-commit rejection;
- cancellation-resistant late completion;
- new-epoch ABG execution;
- thread-originated epoch advancement;
- completion-to-commit race fencing;
- synthetic-patient enforcement.

The benchmark file is generated at:

    artifacts/interruption-benchmark.json

These tests validate Python scheduling and fencing. They do not establish
acoustic playback latency.

## Frontend build

    cd frontend
    npm run build
    npm run preview

Serve production assets through HTTPS.

The AudioWorklet file must remain accessible at:

    /duplex-gate.js

For a non-root deployment, update that URL and the Vite base configuration
consistently.

## Auditing and heard-versus-interrupted reconciliation

The worker records JSONL events for:

- epoch advances;
- VAD boundaries;
- final transcripts;
- Qwen first delta;
- tool start and commit;
- intended speech;
- first Rime PCM;
- generated sample counts;
- segment interruption or completion;
- browser playback receipts.

Browser receipts count non-silent samples rendered through the authorized
audio graph. They are not proof of human perception.

This implementation does not invent word-level timestamps. An interrupted
segment is represented by its intended text, segment ID, rendered duration,
and interruption status.

For an exact audible-prefix transcript, record speaker loopback and align
the recording separately.

Do not confuse:

- Rime first PCM;
- browser graph rendering;
- acoustic speaker output;
- human hearing.

## Security and deployment boundaries

- Use synthetic data only.
- Keep .env and artifacts outside source control.
- Run the token service behind HTTPS and a proper identity-aware gateway.
- The included shared-secret provisioning flow is suitable for a controlled
  demonstration, not multi-tenant hospital identity management.
- The in-memory token rate limiter is single-process.
- Restrict room creation and worker access.
- Operate one terminal per demonstration room.
- Protect audit files and set a retention policy.
- Do not log real patient transcripts into this demonstration.
- Dependency ranges are provided for installation compatibility; freeze the
  resolved versions after validation:

      pip freeze > artifacts/python-freeze.txt

  Retain frontend/package-lock.json after npm install for reproducibility.
- Validate Rime model availability before recording.
- There is no silent TTS fallback.

## Failure behavior

- Local speech detection immediately closes the browser audio gate.
- Lost control transport leaves audio muted.
- Stale events cannot lower the browser's epoch.
- A pending local interruption requires its matching server acknowledgment.
- Reconnection clears playback authorization.
- Provider failures surface as a HUD error.
- Old tools cannot commit after losing their epoch.
- Worker restart requires terminal re-arming.

The local energy gate can false-trigger on noise. Adjust the RMS threshold
only after testing the intended headset and environment.

Server Silero remains the segmentation authority.

## Acceptance and evidence

Read RIME_EVIDENCE.md before claiming performance.

The submission must include real ten-trial measurements from the intended
deployment.

A 150 ms Python cancellation result does not establish a 150 ms acoustic cutoff.

The HUD's local cutoff excludes output-device latency.

Avoid Bluetooth audio for latency-sensitive testing.

## Four-to-five-minute video outline

### 0:00–0:40 — Necessity

Show sterile gloves and eyes-busy context.

Explain why a chatbot with a play button is insufficient.

Show pre-sterile arming, then stop touching the terminal.

### 0:40–1:25 — Normal voice flow

Request electrolytes.

Show the amber tool state, followed by violet Rime speech.

Show the synthetic K+ readout and Rime configuration badge.

### 1:25–2:40 — Deliberate interruption

Request electrolytes again.

Interrupt during the 2.5-second tool delay:

    "Wait, cancel that. Check arterial blood gas pH instead."

Show the epoch advance.

Demonstrate that potassium does not play.

Receive the replacement ABG response.

Repeat while Rime is already speaking to demonstrate local audio cutoff.

### 2:40–3:40 — Failure reproduction

Run pytest.

Show the cancellation-resistant tool test.

Explain why cancellation alone is insufficient and why a late result still
fails the epoch check.

### 3:40–4:35 — Evidence

Show the generated benchmark JSON, audit records, and loopback annotations.

Distinguish cancellation latency from acoustic cutoff.

Display actual ten-trial results, including maximum latency and stale-leak count.

### 4:35–5:00 — Honest boundaries

State that this is synthetic data and not clinically validated.

Mention ambient-noise, device-buffering, and single-worker limitations.

End with:

    "Hands busy. Eyes busy. Voice required. Old epochs cannot speak."
# Local Voice Assistant on Raspberry Pi 5 — Implementation Plan

> **Target device:** Raspberry Pi 5, 16 GB RAM, headless, USB microphone, USB/3.5 mm speaker.
> **Goal:** A user speaks, the audio is transcribed locally, sent to a locally-running LLM with configurable instructions, the response is synthesised to speech locally, and played back through the speaker. Everything is controlled from a web dashboard reachable on the LAN. No cloud services, no paid APIs.

---

## 1. Guiding Principles

1. **Edge-first.** Every component must run on a Pi 5 without GPU. Memory budget assumes the LLM is the dominant consumer (≤ 10 GB), leaving room for STT/TTS/OS.
2. **Modular.** STT, LLM, TTS, audio I/O, and orchestration are independent services with narrow interfaces. Any one can be swapped without touching the others.
3. **Configurable at runtime.** All tunables (model name, temperature, system prompt, voice, VAD sensitivity, etc.) are exposed through the dashboard and persisted to disk. No restart should be required for parameter changes.
4. **Headless-ready.** The device must boot, auto-start the service, and be fully operable from another machine via the dashboard only.
5. **Free and open source only.** No subscriptions, no API keys to external providers.

---

## 2. Technology Stack

| Layer | Choice | Why for Pi 5 |
|---|---|---|
| OS | Raspberry Pi OS (64-bit, Bookworm) | Official, ARM64, kernel tuned for Pi |
| LLM runtime | **Ollama** (wraps llama.cpp) | ARM64 build, hot-swap GGUF models via HTTP API, handles quantisation and KV-cache cleanly |
| Default LLMs | `llama3.2:3b`, `qwen2.5:3b`, `phi3:mini`, `gemma2:2b` (Q4_K_M) | All fit comfortably in RAM; user can pull any GGUF |
| STT | **faster-whisper** (CTranslate2 backend) with `base.en` / `small.en` int8 | 3–5× faster than vanilla Whisper on CPU; streaming-friendly |
| VAD | **Silero VAD** (ONNX, ~2 MB) | Detects end-of-speech reliably; tiny CPU cost |
| TTS | **Piper** | Built for Pi; ONNX voices; ~0.3× real-time on Pi 5 |
| Audio I/O | `sounddevice` + ALSA | Stable on Linux; device enumeration over USB |
| Backend | **FastAPI** + **uvicorn** + **websockets** | Async, low memory, mature |
| State store | SQLite (conversations, settings snapshots) + JSON file (live config) | Zero-config, file-based |
| Frontend | **React 18 + Vite + TypeScript + Tailwind + shadcn/ui** | Built off-device, served as static bundle |
| Process supervision | **systemd** | Native, restart policies, logs via `journalctl` |
| Packaging | `uv` (Python) + `pnpm` (JS) | Fast, deterministic |

---

## 3. System Architecture

```
                ┌────────────────────────────────────────────────────────┐
                │                  Raspberry Pi 5 (headless)             │
                │                                                        │
   USB Mic ─────┤ AudioCaptureService ──► VAD ──► STTService             │
                │                                    │                   │
                │                                    ▼                   │
                │                            PipelineOrchestrator        │
                │                                    │                   │
                │                                    ▼                   │
                │                            LLMService ──► Ollama :11434│
                │                                    │                   │
                │                                    ▼                   │
   Speaker ◄────┤ AudioPlaybackService ◄── TTSService                    │
                │                                                        │
                │              ┌────────────────┴────────────────┐       │
                │              │     FastAPI app (port 8080)     │       │
                │              │  • REST  /api/...               │       │
                │              │  • WS    /ws/state              │       │
                │              │  • static /  (React bundle)     │       │
                │              └────────────────┬────────────────┘       │
                └───────────────────────────────┼────────────────────────┘
                                                │ LAN
                                                ▼
                                    Browser on phone / laptop
                                       (Dashboard UI)
```

**Pipeline states** (single source of truth, broadcast over WS):
`IDLE → LISTENING → TRANSCRIBING → THINKING → SPEAKING → IDLE`
Plus `ERROR` and `PAUSED`.

**Two interaction modes** (toggle in dashboard):
- **Continuous (VAD-gated):** mic always open, VAD decides utterance boundaries.
- **Push-to-talk:** dashboard button or GPIO button starts/stops capture.

---

## 4. Repository Structure

```
voice-assistant/
├── README.md
├── pyproject.toml            # uv-managed
├── .python-version
├── docker-compose.yml        # optional, for dev
├── configs/
│   ├── default.yaml          # shipped defaults
│   └── runtime.json          # live config, written by API
├── data/
│   ├── conversations.sqlite
│   ├── models/               # whisper/piper model cache
│   └── logs/
├── scripts/
│   ├── install_pi.sh         # one-shot Pi installer
│   ├── pull_default_models.sh
│   └── systemd/
│       ├── voice-assistant.service
│       └── ollama.service.override
├── src/voice_assistant/
│   ├── __init__.py
│   ├── main.py               # FastAPI entrypoint
│   ├── config.py             # pydantic settings
│   ├── state.py              # pipeline state machine
│   ├── audio/
│   │   ├── capture.py
│   │   ├── playback.py
│   │   ├── devices.py
│   │   └── vad.py
│   ├── stt/
│   │   ├── base.py           # abstract STTBackend
│   │   └── faster_whisper.py
│   ├── llm/
│   │   ├── base.py           # abstract LLMBackend
│   │   └── ollama.py
│   ├── tts/
│   │   ├── base.py           # abstract TTSBackend
│   │   └── piper.py
│   ├── orchestrator.py
│   ├── conversation.py       # history, context windowing
│   ├── api/
│   │   ├── routes_config.py
│   │   ├── routes_models.py
│   │   ├── routes_conversation.py
│   │   ├── routes_audio.py
│   │   └── ws.py
│   └── utils/
│       ├── logging.py
│       └── events.py
├── tests/
│   ├── unit/
│   └── integration/
└── frontend/
    ├── package.json
    ├── vite.config.ts
    ├── tailwind.config.ts
    ├── index.html
    └── src/
        ├── main.tsx
        ├── App.tsx
        ├── api/client.ts
        ├── api/ws.ts
        ├── components/
        │   ├── StatusPanel.tsx
        │   ├── ConversationLog.tsx
        │   ├── ModelPicker.tsx
        │   ├── LLMSettings.tsx
        │   ├── STTSettings.tsx
        │   ├── TTSSettings.tsx
        │   ├── AudioSettings.tsx
        │   └── SystemPromptEditor.tsx
        └── pages/
            ├── Dashboard.tsx
            ├── Settings.tsx
            └── Conversations.tsx
```

---

## 5. Configuration Schema (single source of truth)

```yaml
# configs/default.yaml — every field is overridable via API and persisted to runtime.json
mode: continuous            # continuous | push_to_talk
audio:
  input_device: null        # null = system default; else ALSA name
  output_device: null
  sample_rate: 16000
  channels: 1
vad:
  enabled: true
  threshold: 0.5            # 0.0–1.0, Silero score
  min_speech_ms: 250
  silence_timeout_ms: 800   # how long of silence ends an utterance
stt:
  backend: faster_whisper
  model: base.en            # tiny.en|base.en|small.en|medium.en|distil-small.en
  compute_type: int8
  language: en
  beam_size: 1
llm:
  backend: ollama
  base_url: http://127.0.0.1:11434
  model: llama3.2:3b
  temperature: 0.7
  top_p: 0.9
  top_k: 40
  num_ctx: 4096
  num_predict: 512
  repeat_penalty: 1.1
  system_prompt: |
    You are a concise, friendly voice assistant. Answer in 1–3 sentences
    unless the user asks for more detail. Avoid markdown and lists.
  keep_alive: 10m
tts:
  backend: piper
  voice: en_US-lessac-medium
  speed: 1.0
  noise_scale: 0.667
  length_scale: 1.0
conversation:
  history_turns: 6          # how many turns to send with each request
  store_to_disk: true
server:
  host: 0.0.0.0
  port: 8080
```

---

## 6. Milestones & Tickets

Each ticket has: **Goal · Scope · Acceptance Criteria (AC) · Files · Depends on · Effort** (S ≤ 0.5 day, M ≤ 1.5 days, L > 1.5 days).

### Milestone 1 — Foundation

#### T-001 · Repository scaffolding
- **Goal:** Empty repo → working Python project skeleton.
- **Scope:** Initialise `uv` project, set Python 3.11, add `pyproject.toml` with pinned deps (`fastapi`, `uvicorn[standard]`, `pydantic`, `pydantic-settings`, `PyYAML`, `sounddevice`, `numpy`, `aiohttp`). Create folder tree from §4. Add `README.md` stub, `.gitignore`, `.env.example`, MIT `LICENSE`.
- **AC:** `uv sync` succeeds on a clean Pi 5. `python -c "import voice_assistant"` works.
- **Files:** `pyproject.toml`, `.python-version`, repo skeleton.
- **Depends on:** —
- **Effort:** S

#### T-002 · Configuration system
- **Goal:** Load `configs/default.yaml`, overlay `configs/runtime.json`, expose typed config object.
- **Scope:** Pydantic models mirroring §5. `ConfigStore` class with `get()`, `update(patch)`, `reload()`, atomic write to `runtime.json`. Emits a `config_changed` event on update. Validation errors return a structured diff.
- **AC:** Unit tests cover load, partial update, invalid value rejection, persistence across restart.
- **Files:** `src/voice_assistant/config.py`, `configs/default.yaml`, `tests/unit/test_config.py`.
- **Depends on:** T-001
- **Effort:** M

#### T-003 · Logging & event bus
- **Goal:** Structured logging + in-process pub/sub for pipeline events.
- **Scope:** `structlog` JSON logs to `data/logs/app.log` and stdout. `EventBus` with `subscribe(topic, async_handler)` and `publish(topic, payload)`. Topics: `state.changed`, `stt.partial`, `stt.final`, `llm.token`, `llm.final`, `tts.started`, `tts.ended`, `error`, `config.changed`.
- **AC:** Two subscribers receive the same event; back-pressure does not crash the bus; logs rotate at 10 MB.
- **Files:** `src/voice_assistant/utils/logging.py`, `src/voice_assistant/utils/events.py`, tests.
- **Depends on:** T-001
- **Effort:** M

#### T-004 · Pipeline state machine
- **Goal:** Authoritative state machine for the conversation loop.
- **Scope:** `PipelineState` enum (`IDLE`, `LISTENING`, `TRANSCRIBING`, `THINKING`, `SPEAKING`, `PAUSED`, `ERROR`). `StateMachine` class with allowed transitions, hooks, and event emission on every change. Reject illegal transitions explicitly.
- **AC:** Table-driven tests cover every valid transition and at least 5 invalid ones. Every state change publishes `state.changed` exactly once.
- **Files:** `src/voice_assistant/state.py`, `tests/unit/test_state.py`.
- **Depends on:** T-003
- **Effort:** S

---

### Milestone 2 — Audio I/O

#### T-005 · Device enumeration
- **Goal:** List input and output devices.
- **Scope:** Wrap `sounddevice.query_devices()`. Return `{index, name, max_input_channels, max_output_channels, default_samplerate}`. Filter for ALSA hostapi. Provide `pick_default_input()` / `pick_default_output()` helpers that prefer a USB device when present.
- **AC:** On a Pi with one USB mic and 3.5 mm jack, function returns both and identifies the USB mic as the preferred input.
- **Files:** `src/voice_assistant/audio/devices.py`.
- **Depends on:** T-001
- **Effort:** S

#### T-006 · Audio capture service
- **Goal:** Async ring-buffered mic capture producing 20 ms PCM frames.
- **Scope:** `AudioCapture` class. Opens stream at 16 kHz mono int16. Pushes frames to an `asyncio.Queue`. Start/stop/pause. Recover from `XRUN`. Configurable device.
- **AC:** Captures continuously for 10 minutes without dropouts (log XRUN count ≤ 1). Stops cleanly when state machine leaves `LISTENING`.
- **Files:** `src/voice_assistant/audio/capture.py`, integration test with a short recording.
- **Depends on:** T-002, T-005
- **Effort:** M

#### T-007 · Voice Activity Detection (Silero)
- **Goal:** Detect utterance start / end from streaming PCM.
- **Scope:** Lazy-load Silero VAD ONNX model into `onnxruntime` (CPU). `VADProcessor.feed(frame) -> VADEvent` returning one of `{NONE, SPEECH_START, SPEECH_END}`. Honours `threshold`, `min_speech_ms`, `silence_timeout_ms` from config.
- **AC:** On a 10-utterance fixture, detects all utterance boundaries within ±150 ms. Memory footprint < 30 MB.
- **Files:** `src/voice_assistant/audio/vad.py`, fixture audio, tests.
- **Depends on:** T-006
- **Effort:** M

#### T-008 · Audio playback service
- **Goal:** Play 22 kHz mono int16 PCM streamed from TTS.
- **Scope:** `AudioPlayback` class. Accepts an async iterator of PCM chunks, writes to `sounddevice.OutputStream`. Supports interrupt (`barge-in`): if state transitions to `LISTENING`, playback halts within 100 ms.
- **AC:** Plays a 30 s Piper sample without artefacts. Barge-in halts playback in < 100 ms.
- **Files:** `src/voice_assistant/audio/playback.py`, tests.
- **Depends on:** T-004, T-005
- **Effort:** M

---

### Milestone 3 — STT Service

#### T-009 · STT backend interface
- **Goal:** Define `STTBackend` ABC.
- **Scope:** Methods: `async transcribe(pcm: bytes, sample_rate: int) -> Transcript`, `available_models() -> list[str]`, `load(model_name)`, `unload()`. `Transcript` includes text, language, confidence, segments, latency_ms.
- **AC:** Two stub implementations (real + fake) satisfy the same tests via parametrisation.
- **Files:** `src/voice_assistant/stt/base.py`.
- **Depends on:** T-002
- **Effort:** S

#### T-010 · faster-whisper backend
- **Goal:** Concrete STT using faster-whisper.
- **Scope:** Lazy model load to `data/models/whisper/`. Configurable `model`, `compute_type=int8`, `language`, `beam_size`. Warm-up on first load (1 s of silence) to avoid first-call latency spike. Expose downloadable model list.
- **AC:** `base.en` transcribes a 5 s clip in < 2 s on Pi 5. Switching model at runtime succeeds without leaking RAM (verified via `psutil` before/after).
- **Files:** `src/voice_assistant/stt/faster_whisper.py`, tests with sample WAV.
- **Depends on:** T-009
- **Effort:** L

#### T-011 · STT service worker
- **Goal:** Glue VAD output → STT backend.
- **Scope:** Buffer frames between `SPEECH_START` and `SPEECH_END`, hand off to backend, publish `stt.final`. Drop utterances shorter than `min_speech_ms`. Emit `stt.partial` if backend supports it (future-proof).
- **AC:** End-to-end: speak into mic, see `stt.final` event with text. Reject 100 ms cough.
- **Files:** `src/voice_assistant/stt/service.py`, integration test.
- **Depends on:** T-007, T-010
- **Effort:** M

---

### Milestone 4 — LLM Service

#### T-012 · LLM backend interface
- **Goal:** Define `LLMBackend` ABC.
- **Scope:** Methods: `async stream(messages, params) -> AsyncIterator[str]`, `async list_models() -> list[ModelInfo]`, `async pull_model(name) -> AsyncIterator[PullProgress]`, `async delete_model(name)`, `async model_info(name)`. `ModelInfo` includes name, size_bytes, family, quantisation, modified_at.
- **AC:** Interface documented; fake backend used in tests streams pre-canned tokens.
- **Files:** `src/voice_assistant/llm/base.py`.
- **Depends on:** T-002
- **Effort:** S

#### T-013 · Ollama backend
- **Goal:** Concrete LLM via Ollama HTTP API.
- **Scope:** Async client against `http://127.0.0.1:11434`. Use `/api/chat` with `stream=true`. Pass full params (`temperature`, `top_p`, `top_k`, `num_ctx`, `num_predict`, `repeat_penalty`, `keep_alive`). Implement `/api/tags`, `/api/pull` (streamed progress), `/api/delete`, `/api/show`. Robust to Ollama restart (auto-reconnect with backoff).
- **AC:** Streams tokens for `llama3.2:3b` in < 600 ms TTFT on Pi 5. Pull progress events surface to event bus. Killing Ollama mid-stream raises a typed error, not a crash.
- **Files:** `src/voice_assistant/llm/ollama.py`, mocked HTTP tests + one live integration test.
- **Depends on:** T-012, T-003
- **Effort:** L

#### T-014 · Conversation/context manager
- **Goal:** Manage chat history with windowing.
- **Scope:** `Conversation` class persisted to SQLite. Stores turns with role, text, timestamp, audio_duration_ms, latency_ms. `build_messages(system_prompt, history_turns)` returns the message list to send. Provide `new_conversation()`, `reset()`, `list_conversations()`, `export(id) -> JSON`.
- **AC:** History truncated to `history_turns`. System prompt always first. Schema migrations handled by simple version table.
- **Files:** `src/voice_assistant/conversation.py`, `tests/unit/test_conversation.py`.
- **Depends on:** T-002
- **Effort:** M

---

### Milestone 5 — TTS Service

#### T-015 · TTS backend interface
- **Goal:** Define `TTSBackend` ABC.
- **Scope:** `async synthesise(text, params) -> AsyncIterator[bytes]` yielding 22050 Hz mono int16 chunks. `available_voices()`, `load_voice(name)`, `unload()`. Voice metadata: name, language, sample_rate, size_mb.
- **AC:** Interface documented; fake backend yields silent chunks for tests.
- **Files:** `src/voice_assistant/tts/base.py`.
- **Depends on:** T-002
- **Effort:** S

#### T-016 · Piper backend
- **Goal:** Concrete TTS using Piper.
- **Scope:** Invoke Piper as a subprocess (preferred — avoids Python binding issues on ARM) or via `piper-tts` Python package, whichever benchmarks faster on Pi 5. Voices live in `data/models/piper/<voice>.onnx` + `.onnx.json`. Stream stdout as int16 chunks. Configurable `speed` (mapped to `length_scale`), `noise_scale`.
- **AC:** Synthesises 100 characters in < 1.5 s on Pi 5. Streaming chunks arrive while audio is still being generated (first chunk < 500 ms after request). Falls back gracefully if a voice file is missing.
- **Files:** `src/voice_assistant/tts/piper.py`, voice download helper.
- **Depends on:** T-015
- **Effort:** L

#### T-017 · TTS service worker
- **Goal:** Consume LLM token stream → produce sentence-batched TTS → playback.
- **Scope:** Buffer LLM tokens, flush to TTS at sentence boundaries (regex on `.!?` + min length) so the user hears the response while the LLM is still generating. Pipe TTS chunks straight to `AudioPlayback`. Publish `tts.started` / `tts.ended` with per-sentence latency.
- **AC:** For a 4-sentence response, the user hears sentence 1 before the LLM has finished generating sentence 4. Verified by timestamping events.
- **Files:** `src/voice_assistant/tts/service.py`, integration test.
- **Depends on:** T-016, T-013, T-008
- **Effort:** M

---

### Milestone 6 — Pipeline Orchestrator

#### T-018 · Orchestrator
- **Goal:** Wire mic → VAD → STT → LLM → TTS → speaker, driven by state machine.
- **Scope:** `Orchestrator` runs an async loop subscribed to events:
  - `SPEECH_START` → state `LISTENING`
  - `SPEECH_END` → state `TRANSCRIBING` → call STT
  - `stt.final` → state `THINKING` → call LLM
  - `llm.token`s → state `SPEAKING` → feed sentence-batched to TTS
  - `tts.ended` (final sentence) → state `IDLE`
  Handles errors at every step with retries (configurable) and falls back to `IDLE`. Supports push-to-talk via API call that injects `SPEECH_START`/`SPEECH_END`.
- **AC:** End-to-end live test on Pi: ask "What is 2 plus 2?" — get spoken answer in < 6 s total. Killing Ollama mid-response moves state to `ERROR` and recovers on next turn.
- **Files:** `src/voice_assistant/orchestrator.py`, integration test.
- **Depends on:** T-004, T-011, T-013, T-014, T-017
- **Effort:** L

#### T-019 · Wake-word toggle & barge-in
- **Goal:** Allow the user to interrupt the assistant by speaking.
- **Scope:** While in `SPEAKING`, keep VAD running on the mic. On a confirmed `SPEECH_START`, halt playback (T-008 barge-in), discard remaining LLM tokens, transition to `LISTENING`. Configurable on/off.
- **AC:** Speaking over the assistant stops playback within 200 ms and starts a new turn.
- **Files:** updates to `orchestrator.py`, `audio/playback.py`.
- **Depends on:** T-018
- **Effort:** M

---

### Milestone 7 — API Layer

#### T-020 · FastAPI app skeleton
- **Goal:** Single ASGI app hosting REST, WS, and static frontend.
- **Scope:** `main.py` builds the app, wires lifespan startup (load config, start orchestrator) and shutdown. Mounts `/api`, `/ws`, `/` (static). Health check at `/healthz`. CORS for dev only.
- **AC:** `uvicorn voice_assistant.main:app` boots in < 3 s; `/healthz` returns 200; orchestrator started.
- **Files:** `src/voice_assistant/main.py`.
- **Depends on:** T-018
- **Effort:** S

#### T-021 · Config REST routes
- **Goal:** Expose the full config tree.
- **Scope:** `GET /api/config` returns current. `PATCH /api/config` accepts a JSON patch (deep-merge), validates via Pydantic, persists, emits `config.changed`. Per-section convenience: `PATCH /api/config/llm`, `/stt`, `/tts`, `/audio`, `/vad`. Return validation errors as 422 with field paths.
- **AC:** Round-trip via `curl`; invalid value rejected with field-level error; change reflected without restart for hot-reloadable fields.
- **Files:** `src/voice_assistant/api/routes_config.py`, tests.
- **Depends on:** T-020
- **Effort:** M

#### T-022 · Models management routes
- **Goal:** Manage local LLM/STT/TTS models.
- **Scope:**
  - `GET /api/models/llm` → Ollama-installed models with size, family, quantisation.
  - `POST /api/models/llm/pull {name}` → streams pull progress over the response (NDJSON) and over WS.
  - `DELETE /api/models/llm/{name}`.
  - `GET /api/models/stt` → whisper models present + downloadable list.
  - `POST /api/models/stt/download {name}`.
  - `GET /api/models/tts` → Piper voices present + downloadable list (Hugging Face URLs hardcoded).
  - `POST /api/models/tts/download {voice}`.
- **AC:** Can pull `qwen2.5:3b` end-to-end from the dashboard; progress visible.
- **Files:** `src/voice_assistant/api/routes_models.py`, tests.
- **Depends on:** T-021, T-013
- **Effort:** L

#### T-023 · Conversation routes
- **Goal:** Inspect, reset, and replay conversations.
- **Scope:**
  - `GET /api/conversations?limit=` → list.
  - `GET /api/conversations/{id}` → full turns.
  - `POST /api/conversations` → start new.
  - `DELETE /api/conversations/{id}`.
  - `POST /api/conversations/{id}/export` → JSON file.
- **AC:** All endpoints round-trip; deleting the active conversation safely starts a new one.
- **Files:** `src/voice_assistant/api/routes_conversation.py`, tests.
- **Depends on:** T-014
- **Effort:** M

#### T-024 · Audio control & device routes
- **Goal:** Pick devices, test mic/speaker, push-to-talk.
- **Scope:**
  - `GET /api/audio/devices` → enumerated inputs/outputs.
  - `POST /api/audio/test/speaker` → plays a 1 s tone.
  - `POST /api/audio/test/mic` → records 3 s and returns RMS level + WAV.
  - `POST /api/control/ptt/start`, `POST /api/control/ptt/stop` → push-to-talk.
  - `POST /api/control/pause`, `POST /api/control/resume`.
- **AC:** Mic test shows expected RMS; speaker test audible; PTT triggers a full turn.
- **Files:** `src/voice_assistant/api/routes_audio.py`, tests.
- **Depends on:** T-005, T-018
- **Effort:** M

#### T-025 · WebSocket /ws/state
- **Goal:** Real-time push of state, transcripts, tokens, and meters.
- **Scope:** Subscribe to all event-bus topics, fan out to connected clients as JSON. Throttle high-frequency events (`audio.level` at 10 Hz, `llm.token` un-throttled). Send a snapshot of current state on connect. Heartbeat ping/pong every 15 s.
- **AC:** Two browsers connected simultaneously see identical, in-order events. Disconnect doesn't leak.
- **Files:** `src/voice_assistant/api/ws.py`, tests.
- **Depends on:** T-020, T-003
- **Effort:** M

#### T-026 · Audio level meter
- **Goal:** Stream input RMS for UI VU meter.
- **Scope:** Compute RMS over 100 ms windows in `AudioCapture`. Publish `audio.level` event with dBFS value. Cheap (< 0.5 % CPU).
- **AC:** UI shows responsive meter when speaking.
- **Files:** updates to `audio/capture.py`.
- **Depends on:** T-006, T-025
- **Effort:** S

---

### Milestone 8 — Dashboard Frontend

#### T-027 · Frontend scaffolding
- **Goal:** Vite + React + TS + Tailwind + shadcn/ui project.
- **Scope:** Set up project under `frontend/`. Configure proxy to backend in dev. Add ESLint + Prettier. Build output to `frontend/dist`, served by FastAPI at `/`.
- **AC:** `pnpm dev` shows blank dashboard. `pnpm build` produces a bundle served correctly by FastAPI.
- **Files:** entire `frontend/` skeleton.
- **Depends on:** T-020
- **Effort:** M

#### T-028 · API client + WS hook
- **Goal:** Typed client and `useWebSocketState()` hook.
- **Scope:** Generate types from a hand-written `api/types.ts` mirroring backend Pydantic models. Thin `fetch` wrapper. `useWebSocketState` reconnects with exponential backoff, exposes current state, last events, and connection status.
- **AC:** Dashboard shows live state on page load; survives backend restart.
- **Files:** `frontend/src/api/{client.ts,types.ts,ws.ts}`, `frontend/src/hooks/useWebSocketState.ts`.
- **Depends on:** T-025, T-027
- **Effort:** M

#### T-029 · Dashboard / Status page
- **Goal:** At-a-glance status of the assistant.
- **Scope:** Big state pill (`IDLE`/`LISTENING`/...). Live VU meter. Live partial+final transcript. Streaming LLM response. Currently-loaded models. Pause/Resume, Push-to-talk button, "New conversation" button. Mic and speaker test buttons.
- **AC:** Talking to the device, the dashboard mirrors every state change within 200 ms.
- **Files:** `frontend/src/pages/Dashboard.tsx`, components.
- **Depends on:** T-028, T-024
- **Effort:** L

#### T-030 · LLM settings panel
- **Goal:** Edit every LLM parameter from §5.
- **Scope:** Sliders for temperature/top_p/top_k/repeat_penalty/num_predict/num_ctx; model dropdown populated from `/api/models/llm`; system prompt textarea with character count and "reset to default"; `keep_alive` input. Changes patch via `/api/config/llm` on blur (debounced). "Pull model" dialog with progress bar (NDJSON or WS).
- **AC:** Changing temperature is reflected in the next LLM call (verify via a deterministic prompt + temperature 0 vs 1).
- **Files:** `frontend/src/components/LLMSettings.tsx`, `ModelPicker.tsx`, `SystemPromptEditor.tsx`.
- **Depends on:** T-021, T-022, T-028
- **Effort:** L

#### T-031 · STT settings panel
- **Goal:** Edit STT params + download models.
- **Scope:** Whisper model dropdown (downloaded ✓, downloadable ↓), language picker, beam_size, compute_type. Download button with progress.
- **AC:** Switching from `base.en` to `small.en` works without restart; first transcription after switch is correct.
- **Files:** `frontend/src/components/STTSettings.tsx`.
- **Depends on:** T-022, T-028
- **Effort:** M

#### T-032 · TTS settings panel
- **Goal:** Edit TTS params + manage voices.
- **Scope:** Voice dropdown with sample-play button (calls `/api/audio/test/speaker?voice=...&text=...`), speed slider, noise scale. Download voice dialog.
- **AC:** "Play sample" speaks the supplied text in the chosen voice through the device speaker.
- **Files:** `frontend/src/components/TTSSettings.tsx`.
- **Depends on:** T-022, T-024, T-028
- **Effort:** M

#### T-033 · Audio & VAD settings panel
- **Goal:** Choose input/output device, tune VAD.
- **Scope:** Device dropdowns from `/api/audio/devices`. VAD threshold/min_speech/silence_timeout sliders with live preview (current VAD score graph from WS). Mode toggle: continuous / push-to-talk.
- **AC:** Switching from continuous to PTT immediately stops auto-listening.
- **Files:** `frontend/src/components/AudioSettings.tsx`.
- **Depends on:** T-024, T-026, T-028
- **Effort:** M

#### T-034 · Conversations page
- **Goal:** Browse, replay, delete past conversations.
- **Scope:** Sidebar list of conversations. Selected conversation shows turns with timestamps and latency per stage (STT ms, LLM ms, TTS ms). Export and delete buttons. Live conversation auto-scrolls.
- **AC:** Past conversations persist across service restart; export is a valid JSON file.
- **Files:** `frontend/src/pages/Conversations.tsx`, `ConversationLog.tsx`.
- **Depends on:** T-023, T-028
- **Effort:** M

---

### Milestone 9 — Headless Operation & Deployment

#### T-035 · Pi installer script
- **Goal:** One-shot bootstrap on a fresh Pi OS install.
- **Scope:** `scripts/install_pi.sh`:
  1. `apt install` system deps (`libportaudio2`, `libsndfile1`, `ffmpeg`, `alsa-utils`, `python3.11-venv`, `git`, `curl`).
  2. Install `uv`.
  3. Install Ollama via official `curl … | sh` (verify checksum). Enable systemd service.
  4. Clone repo, `uv sync`, `pnpm install && pnpm build` (or pull pre-built frontend artefact).
  5. Download default models (whisper `base.en`, piper `en_US-lessac-medium`, ollama `llama3.2:3b`).
  6. Install and enable `voice-assistant.service`.
  7. Print dashboard URL (`http://<pi-ip>:8080`).
- **AC:** Fresh Pi 5 reaches working dashboard in one command + a reboot. Idempotent on re-run.
- **Files:** `scripts/install_pi.sh`, `scripts/pull_default_models.sh`.
- **Depends on:** all backend + T-027
- **Effort:** L

#### T-036 · systemd units
- **Goal:** Robust auto-start and supervision.
- **Scope:**
  - `voice-assistant.service`: starts uvicorn, `Restart=always`, `After=network-online.target ollama.service`, `User=voice`, resource limits (`MemoryHigh=12G`).
  - Ollama service override to pin `OLLAMA_KEEP_ALIVE=10m` and bind to `127.0.0.1:11434` only.
  - Journald log integration.
- **AC:** Killing the Python process triggers restart in < 5 s. Reboot brings service up automatically. Logs visible via `journalctl -u voice-assistant`.
- **Files:** `scripts/systemd/*.service`, install script integration.
- **Depends on:** T-035
- **Effort:** M

#### T-037 · GPIO push-to-talk (optional hardware)
- **Goal:** Use a GPIO button as PTT.
- **Scope:** Optional module using `gpiozero`. Configurable pin. On press, calls the PTT API. On release, stops PTT. Disabled by default; enable via config.
- **AC:** Pressing a wired button starts a turn even when no browser is open.
- **Files:** `src/voice_assistant/audio/gpio_ptt.py`.
- **Depends on:** T-024
- **Effort:** S

#### T-038 · LED status indicator (optional hardware)
- **Goal:** GPIO LED reflects pipeline state.
- **Scope:** Map each state to a colour/pattern (e.g. `IDLE` off, `LISTENING` solid green, `THINKING` pulsing blue, `SPEAKING` solid blue, `ERROR` blinking red). Single-LED fallback (brightness pattern).
- **AC:** LED tracks state changes within 200 ms; degrades silently if `gpiozero` unavailable.
- **Files:** `src/voice_assistant/utils/led.py`.
- **Depends on:** T-004, T-025
- **Effort:** S

#### T-039 · Resource & health monitoring
- **Goal:** Surface CPU, RAM, temperature, throttle status on the dashboard.
- **Scope:** Background task samples `psutil` + `vcgencmd measure_temp` + `vcgencmd get_throttled` every 5 s, publishes `system.health` events. Endpoint `GET /api/system/health` for snapshot.
- **AC:** Dashboard shows live CPU/RAM/temp; warning badge when Pi reports thermal throttling.
- **Files:** `src/voice_assistant/utils/health.py`, `routes_system.py`, frontend widget.
- **Depends on:** T-025, T-029
- **Effort:** M

---

### Milestone 10 — Quality, Docs, Polish

#### T-040 · Integration test harness
- **Goal:** End-to-end test without real audio hardware.
- **Scope:** Pytest fixtures that swap real backends for fakes (replay WAV through `AudioCapture` mock, fake LLM streaming canned tokens, TTS writes to a buffer). One full-pipeline test asserts a known utterance produces the expected `tts.ended` event with the expected text.
- **AC:** `pytest -m integration` passes in CI and on a Pi.
- **Files:** `tests/integration/test_pipeline.py`, fixtures.
- **Depends on:** all backend tickets
- **Effort:** L

#### T-041 · Performance benchmark suite
- **Goal:** Reproducible Pi-5 benchmarks.
- **Scope:** Script that records: STT latency for 1/3/5 s clips × {tiny, base, small}; LLM TTFT and tokens/sec for each default model; TTS time-to-first-audio. Writes Markdown report to `docs/benchmarks.md`.
- **AC:** `python scripts/bench.py` runs on Pi 5 and produces a stable report (3-run median).
- **Files:** `scripts/bench.py`, `docs/benchmarks.md` template.
- **Depends on:** T-018
- **Effort:** M

#### T-042 · Error UX & recovery
- **Goal:** Every failure mode is named, surfaced, and recoverable.
- **Scope:** Typed exception hierarchy (`STTError`, `LLMError`, `TTSError`, `AudioError`). Each is caught in the orchestrator, published as `error` event with code + message, surfaced in dashboard as a dismissible toast. Auto-retry with backoff for transient errors (Ollama not ready, model loading). Manual "Reset pipeline" button in dashboard.
- **AC:** Pulling the USB mic during a turn shows a clear toast, state goes to `ERROR`, reconnecting the mic recovers automatically.
- **Files:** updates across orchestrator + frontend.
- **Depends on:** T-018, T-029
- **Effort:** M

#### T-043 · Documentation
- **Goal:** README + operator guide + developer guide.
- **Scope:**
  - `README.md`: what it is, hardware list, quickstart.
  - `docs/operator.md`: dashboard tour, choosing models, troubleshooting (mic not detected, slow responses, etc.), suggested model presets for 4/8/16 GB Pis.
  - `docs/developer.md`: architecture, adding a new STT/LLM/TTS backend, running tests, code style.
  - `docs/hardware.md`: tested mics/speakers/USB-DACs.
- **AC:** A user with a Pi 5 and a USB mic can install and have a conversation following only the README.
- **Files:** `README.md`, `docs/*.md`.
- **Depends on:** T-035
- **Effort:** M

#### T-044 · CI pipeline
- **Goal:** GitHub Actions running tests on x86 and ARM.
- **Scope:** Lint (`ruff`, `mypy`), unit tests on x86, frontend build, ARM64 build via QEMU for smoke. Cache `uv` and `pnpm`.
- **AC:** PRs blocked on failing tests.
- **Files:** `.github/workflows/ci.yml`.
- **Depends on:** T-040
- **Effort:** M

#### T-045 · Release & versioning
- **Goal:** Tagged releases with installer URL.
- **Scope:** `CHANGELOG.md`, SemVer tags, GitHub Releases publishing the install script and pre-built frontend bundle. Installer can pin a release tag.
- **AC:** `bash <(curl -sL https://…/install.sh)` installs a fixed version reproducibly.
- **Depends on:** T-035, T-043
- **Effort:** S

---

## 7. Cross-Cutting Acceptance Criteria

These must hold across all tickets at release:

- **Cold-boot to first answer** on Pi 5 with `llama3.2:3b` + `base.en` + `lessac-medium`: ≤ 8 s after speaking.
- **Steady-state turn latency** (end of user speech → start of audio reply): ≤ 3.5 s median.
- **RAM headroom:** at least 2 GB free with the largest default model loaded.
- **Headless reboot:** assistant is operable from the dashboard within 60 s of power-on.
- **Hot-reload:** changing temperature / system prompt / voice in the dashboard affects the very next turn without any restart.
- **Failure visibility:** every error path shown in the dashboard as a toast and in the logs as structured JSON.
- **No subscription services:** repository contains zero references to paid APIs; install script downloads only from official Ollama, Hugging Face, GitHub releases.

---

## 8. Risks & Mitigations

| Risk | Likelihood | Mitigation |
|---|---|---|
| Larger LLMs (7B Q4) too slow on Pi 5 | High | Default to 3B; document expected tokens/sec per model in `benchmarks.md`; let user pick |
| USB mic noise / poor SNR | Medium | Recommend tested mics in `hardware.md`; expose VAD threshold; consider optional noise-suppression backend (rnnoise) as future ticket |
| Thermal throttling under sustained load | Medium | Surface throttle status (T-039); recommend a heatsink/fan in hardware doc |
| Whisper hallucinations on silence | Medium | VAD-gated capture (T-007); enforce `min_speech_ms`; drop transcripts with low confidence + only filler tokens |
| Ollama API changes | Low | Pin Ollama version in installer; integration tests catch regressions |
| Piper voice quality varies | Low | Default to a known-good voice; allow easy switching |

---

## 9. Future Enhancements (out of scope, listed for completeness)

- Wake-word ("Hey Pi") via `openWakeWord`.
- Multi-language switching detected from transcript.
- Tool-use / function-calling (web search, smart-home control) via Ollama function-calling.
- RAG over a local document folder (LanceDB or sqlite-vec).
- Multi-user voice profiles via speaker embedding.
- Remote dashboard over Tailscale for off-LAN access.
- Hardware-accelerated inference via Hailo-8 AI HAT for Pi 5.

---

## 10. Ticket Dependency Graph (summary)

```
T-001 ─┬─ T-002 ─┬─ T-005 ─ T-006 ─ T-007 ─ T-011 ─┐
       │         │                                  │
       │         ├─ T-008 ─────────────────────┐    │
       │         │                              │   │
       │         ├─ T-009 ─ T-010 ──────────────┼── T-018 ─ T-019
       │         ├─ T-012 ─ T-013 ──────────────┤
       │         ├─ T-014 ──────────────────────┤
       │         └─ T-015 ─ T-016 ─ T-017 ──────┘
       │
       └─ T-003 ─ T-004 ─────────────────────────── T-018
                                                      │
                          T-020 ── T-021..T-026 ──────┤
                                                      │
                          T-027 ── T-028 ── T-029..T-034
                                                      │
                                          T-035 ── T-036 ── T-037/T-038/T-039
                                                      │
                                  T-040..T-045 (quality/release)
```

---

## 11. Recommended Build Order for the Coding Agent

1. **Vertical slice first** (T-001 → T-002 → T-003 → T-004 → T-006 → T-010 → T-013 → T-016 → T-018) — get a working voice-in/voice-out loop on the Pi before touching the dashboard. This proves the hard parts work on the target hardware.
2. **API + minimal dashboard** (T-020 → T-025 → T-027 → T-028 → T-029) — get observability of the live pipeline.
3. **Settings UI** (T-021/T-022 → T-030/T-031/T-032/T-033) — make it configurable end-to-end.
4. **Headless deployment** (T-035 → T-036) — prove it boots autonomously.
5. **Polish** (T-039, T-040, T-042, T-043) — make it production-grade.
6. **Optional hardware & nice-to-haves** (T-037, T-038, T-019, T-041, T-044, T-045).

This order delivers a usable product after step 1, a controllable product after step 3, and a deployable product after step 4 — minimising the risk of late integration surprises on the Pi.

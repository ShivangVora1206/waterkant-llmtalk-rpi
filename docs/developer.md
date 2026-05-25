# Developer Guide

## Architecture

```
AudioCapture → VADProcessor → STTService → Orchestrator → LLMBackend
                                                        ↓
                                               TTSService → AudioPlayback
                                                        ↓
                                               EventBus → WebSocket → Browser
```

The `Orchestrator` drives state transitions through the `StateMachine` and coordinates all services. Everything communicates via the `EventBus` (async pub/sub). The FastAPI app exposes REST endpoints and a WebSocket that fans out all bus events to connected browsers.

## Adding a New STT Backend

1. Create `src/voice_assistant/stt/mybackend.py`
2. Implement `STTBackend` ABC from `stt/base.py`:
   - `async transcribe(pcm: bytes, sample_rate: int) -> Transcript`
   - `available_models() -> list[str]`
   - `async load(model_name: str)`
   - `async unload()`
3. Wire it in `main.py` based on `cfg.stt.backend` value

## Adding a New LLM Backend

1. Create `src/voice_assistant/llm/mybackend.py`
2. Implement `LLMBackend` ABC from `llm/base.py`:
   - `async stream(messages, params) -> AsyncIterator[str]`
   - `async list_models() -> list[ModelInfo]`
   - `async pull_model(name) -> AsyncIterator[PullProgress]`
   - `async delete_model(name)`
   - `async model_info(name) -> ModelInfo | None`
3. Wire it in `main.py`

## Adding a New TTS Backend

1. Create `src/voice_assistant/tts/mybackend.py`
2. Implement `TTSBackend` ABC from `tts/base.py`:
   - `async synthesise(text, params) -> AsyncIterator[bytes]` — must yield 22050 Hz mono int16 chunks
   - `available_voices() -> list[VoiceInfo]`
   - `async load_voice(name)`
   - `async unload()`

## Running Tests

```bash
# Unit tests (no hardware)
uv run pytest tests/unit/ -v

# Integration test (fake backends, no hardware)
uv run pytest tests/integration/ -m integration -v

# All with coverage
uv run pytest --cov=voice_assistant --cov-report=term-missing
```

## Linting / Type checking

```bash
uv run ruff check src/
uv run mypy src/
```

## Frontend Development

```bash
cd frontend
pnpm install
pnpm dev        # starts Vite dev server at :5173, proxies /api → :8080
pnpm build      # outputs to frontend/dist/, served by FastAPI
```

## Event Bus Topics

| Topic | Payload | Description |
|---|---|---|
| `state.changed` | `{from, to}` | Pipeline state transition |
| `stt.final` | `{text, language, confidence, latency_ms}` | Transcription complete |
| `llm.token` | `{token}` | Single LLM output token |
| `llm.final` | `{done: true}` | LLM generation complete |
| `tts.started` | `{sentence, text}` | TTS synthesis started |
| `tts.ended` | `{sentence, text, latency_ms}` | TTS synthesis done |
| `audio.level` | `{dbfs}` | Mic RMS level (10 Hz) |
| `system.health` | `{cpu_percent, ram_free_mb, temp_c, throttled}` | System metrics (5 s) |
| `error` | `{component, message}` | Any pipeline error |
| `config.changed` | `AppConfig` | Config was updated |

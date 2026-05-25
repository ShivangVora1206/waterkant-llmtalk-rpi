# Voice Assistant for Raspberry Pi 5

A fully local, open-source voice assistant running on a Raspberry Pi 5. Speak into a USB microphone, get a response from a local LLM, and hear it back through your speaker — all without any cloud services or API keys.

## Hardware Requirements

- Raspberry Pi 5 (8 GB or 16 GB recommended)
- USB microphone (any ALSA-compatible mic)
- Speaker (USB, 3.5 mm jack, or HDMI)
- MicroSD card (64 GB+ recommended)
- Ethernet or Wi-Fi for initial setup

## Stack

| Layer | Technology |
|---|---|
| LLM runtime | Ollama (llama.cpp wrapper, ARM64 native) |
| Default models | `llama3.2:3b`, `qwen2.5:3b`, `phi3:mini` |
| STT | faster-whisper (`base.en` int8, ~1.5 s/5 s clip) |
| VAD | Silero VAD (ONNX, 2 MB) |
| TTS | Piper (`en_US-lessac-medium`, ~0.3× real-time) |
| Audio I/O | sounddevice + ALSA |
| API | FastAPI + uvicorn + WebSockets |
| Frontend | React 18 + Vite + TypeScript + Tailwind |
| Database | SQLite (conversations) + JSON (config) |
| Supervision | systemd |

## Quick Start

```bash
# 1. Flash Raspberry Pi OS (64-bit, Bookworm) and SSH in

# 2. Clone the repo
git clone https://github.com/yourname/voice-assistant.git
cd voice-assistant

# 3. Run the installer (takes ~10-20 min on first run)
bash scripts/install_pi.sh

# 4. Reboot and open the dashboard
#    Dashboard: http://<pi-ip>:8080
```

That's it. The assistant starts listening automatically after boot.

## Development (on any machine)

```bash
# Install Python deps
uv sync

# Build frontend
cd frontend && pnpm install && pnpm build && cd ..

# Run locally (needs Ollama running separately)
uv run python -m uvicorn voice_assistant.main:app --reload --port 8080

# Run frontend dev server with hot-reload
cd frontend && pnpm dev
```

## Configuration

All settings are editable live from the dashboard at `http://<pi-ip>:8080`:

- **LLM**: model, temperature, system prompt, context window, etc.
- **STT**: Whisper model size, language, compute type
- **TTS**: Voice, speed, noise scale
- **Audio/VAD**: Input/output device, VAD threshold and timing
- **Mode**: Continuous (always listening) or Push-to-Talk

Changes take effect immediately on the next turn — no restart needed.

## Tests

```bash
uv run pytest tests/unit/          # unit tests (no hardware needed)
uv run pytest tests/integration/ -m integration  # full pipeline
```

## Project Structure

```
src/voice_assistant/
  main.py            # FastAPI app entrypoint
  config.py          # Pydantic settings + ConfigStore
  state.py           # Pipeline state machine
  orchestrator.py    # Wires all services together
  conversation.py    # SQLite-persisted chat history
  audio/             # Capture, playback, VAD, devices
  stt/               # STT backends (faster-whisper)
  llm/               # LLM backends (Ollama)
  tts/               # TTS backends (Piper)
  api/               # FastAPI routes + WebSocket
  utils/             # Logging, event bus, health, LED

frontend/src/
  App.tsx            # Root layout + nav
  pages/             # Dashboard, Settings, Conversations
  components/        # Status panel, settings panels, chat log
  hooks/             # useWebSocketState
  api/               # REST client + WS client + types
```

## Documentation

- [docs/operator.md](docs/operator.md) — dashboard tour, model selection, troubleshooting
- [docs/developer.md](docs/developer.md) — architecture, adding backends, running tests
- [docs/hardware.md](docs/hardware.md) — tested mics, speakers, DACs

## License

MIT

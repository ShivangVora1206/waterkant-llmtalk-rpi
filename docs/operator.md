# Operator Guide

## Dashboard Tour

Open `http://<pi-ip>:8080` in any browser on your LAN.

### Dashboard Tab
- **State pill** — shows current pipeline state: IDLE / LISTENING / TRANSCRIBING / THINKING / SPEAKING / PAUSED / ERROR
- **VU meter** — live mic level in dBFS; should respond when you speak
- **System health** — CPU%, free RAM, CPU temperature, throttle warning
- **Conversation log** — live transcript (user + assistant turns)
- **Controls**:
  - Push-to-Talk button (hold to speak)
  - Pause / Resume toggle
  - New Conversation (clears history context)

### Settings Tab
- **LLM** — model, temperature, top-p, top-k, repeat penalty, max tokens, context window, system prompt, keep-alive
- **STT** — Whisper model (download new models in-place), language, compute type, beam size
- **TTS** — Voice selection, speed, noise scale; preview button
- **Audio & VAD** — input/output device, VAD threshold, min speech duration, silence timeout, mode (continuous vs PTT)

### Conversations Tab
- Browse past conversations with timestamps
- Export to JSON
- Delete individual conversations

---

## Choosing a Model

| Model | RAM use | Tokens/s (Pi 5) | Best for |
|---|---|---|---|
| `llama3.2:3b` (Q4_K_M) | ~2.5 GB | ~12–15 | Default; good quality |
| `phi3:mini` (Q4_K_M) | ~2.2 GB | ~15–18 | Fastest; concise answers |
| `qwen2.5:3b` (Q4_K_M) | ~2.5 GB | ~12–14 | Multilingual |
| `gemma2:2b` (Q4_K_M) | ~2 GB | ~16–20 | Smallest footprint |
| `llama3.1:8b` (Q4_K_M) | ~6 GB | ~5–7 | Best quality, slower |

Pull any model from the LLM settings panel or via CLI: `ollama pull <model>`.

---

## Troubleshooting

### Mic not detected
```bash
aplay -l   # list output devices
arecord -l # list input devices
```
Go to Settings → Audio and select your device explicitly.

### "Cannot connect to Ollama"
```bash
sudo systemctl status ollama
sudo systemctl start ollama
```

### Slow first response
The first turn after a model is loaded takes longer (model load). Subsequent turns are faster. Use `keep_alive: 10m` (default) to keep the model hot.

### Thermal throttling warning
- Fit a heatsink and fan (recommended for sustained use)
- Throttling badge appears when Pi reports current throttling (`get_throttled` bit 0–3 non-zero)
- Reduce the LLM to a smaller model to lower CPU load

### Audio distortion / clicks
- Try `compute_type: float16` in STT settings (more accurate but slower on Pi)
- Lower `noise_scale` in TTS settings for cleaner speech
- Use a powered USB hub if the mic is power-starved

---

## Suggested Presets

### 4 GB Pi 5 — Fast & light
```yaml
llm.model: phi3:mini
stt.model: tiny.en
tts.voice: en_US-amy-medium
```

### 8 GB Pi 5 — Balanced (default)
```yaml
llm.model: llama3.2:3b
stt.model: base.en
tts.voice: en_US-lessac-medium
```

### 16 GB Pi 5 — High quality
```yaml
llm.model: llama3.1:8b
stt.model: small.en
tts.voice: en_US-ryan-high
```

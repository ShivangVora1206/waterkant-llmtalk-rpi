#!/usr/bin/env bash
# Download default models for voice-assistant.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DATA_DIR="$REPO_DIR/data/models"

info() { echo "[INFO]  $*"; }

mkdir -p "$DATA_DIR/whisper" "$DATA_DIR/piper"

# Whisper STT (faster-whisper base.en, ~145 MB)
WHISPER_MODEL="base.en"
WHISPER_DIR="$DATA_DIR/whisper"
if [ ! -d "$WHISPER_DIR/models--Systran--faster-whisper-base.en" ] && \
   [ ! -d "$WHISPER_DIR/models--guillaumekln--faster-whisper-base.en" ]; then
    info "Downloading faster-whisper model: $WHISPER_MODEL"
    uv run python -c "
from faster_whisper import WhisperModel
import sys
print('Downloading faster-whisper $WHISPER_MODEL …', flush=True)
WhisperModel('$WHISPER_MODEL', device='cpu', compute_type='int8', download_root='$WHISPER_DIR')
print('Done.', flush=True)
" || info "faster-whisper download failed — will retry on first use"
else
    info "faster-whisper model already present: $WHISPER_MODEL"
fi

# Ollama — pull default LLM
info "Pulling Ollama model llama3.2:3b (this may take a while)…"
ollama pull llama3.2:3b || info "Ollama pull failed or already present"

# Piper — lessac-medium voice
VOICE="en_US-lessac-medium"
VOICE_ONNX="$DATA_DIR/piper/${VOICE}.onnx"
if [ ! -f "$VOICE_ONNX" ]; then
    info "Downloading Piper voice: $VOICE"
    BASE_URL="https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium"
    wget -q "${BASE_URL}/${VOICE}.onnx"          -O "$VOICE_ONNX"
    wget -q "${BASE_URL}/${VOICE}.onnx.json"     -O "${VOICE_ONNX}.json"
else
    info "Piper voice already present: $VOICE"
fi

# Silero VAD — downloaded on first use by the app itself, but we can preload
SILERO_PATH="$DATA_DIR/silero_vad.onnx"
if [ ! -f "$SILERO_PATH" ]; then
    info "Downloading Silero VAD model…"
    wget -q "https://huggingface.co/onnx-community/silero-vad/resolve/main/onnx/model.onnx" \
        -O "$SILERO_PATH"
else
    info "Silero VAD already present"
fi

info "All default models ready."

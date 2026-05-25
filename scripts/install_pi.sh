#!/usr/bin/env bash
# One-shot Pi 5 installer for voice-assistant.
# Usage: bash scripts/install_pi.sh
# Idempotent — safe to re-run.

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SERVICE_USER="${SERVICE_USER:-voice}"
PORT="${PORT:-8080}"

info()  { echo "[INFO]  $*"; }
warn()  { echo "[WARN]  $*"; }
die()   { echo "[ERROR] $*" >&2; exit 1; }

# --------------------------------------------------------------------
# 1. System packages
# --------------------------------------------------------------------
info "Installing system dependencies…"
sudo apt-get update -qq
sudo apt-get install -y --no-install-recommends \
    libportaudio2 libsndfile1 ffmpeg alsa-utils \
    python3 python3-venv python3-pip \
    git curl wget ca-certificates \
    build-essential

# Verify Python >= 3.11
PY_VER=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
PY_MAJOR=$(echo "$PY_VER" | cut -d. -f1)
PY_MINOR=$(echo "$PY_VER" | cut -d. -f2)
if [ "$PY_MAJOR" -lt 3 ] || { [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 11 ]; }; then
    die "Python 3.11+ required, found $PY_VER. Upgrade your OS or install Python manually."
fi
info "Python $PY_VER OK"

# --------------------------------------------------------------------
# 2. uv (Python package manager)
# --------------------------------------------------------------------
if ! command -v uv &>/dev/null; then
    info "Installing uv…"
    curl -LsSf https://astral.sh/uv/install.sh | sh
    # uv installs to ~/.local/bin on Linux
    export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
fi
# Ensure uv is on PATH for the rest of this script
export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
info "uv version: $(uv --version)"

# --------------------------------------------------------------------
# 3. Ollama
# --------------------------------------------------------------------
if ! command -v ollama &>/dev/null; then
    info "Installing Ollama…"
    curl -fsSL https://ollama.com/install.sh | sh
fi
info "Ollama version: $(ollama --version 2>/dev/null || echo 'unknown')"

# Ensure Ollama systemd service is running
sudo systemctl enable ollama 2>/dev/null || true
sudo systemctl start  ollama 2>/dev/null || true

# --------------------------------------------------------------------
# 4. piper TTS binary
# --------------------------------------------------------------------
PIPER_BIN="/usr/local/bin/piper"
if [ ! -f "$PIPER_BIN" ]; then
    info "Installing Piper TTS…"
    ARCH="$(uname -m)"
    case "$ARCH" in
        aarch64) PIPER_ARCH="aarch64" ;;
        x86_64)  PIPER_ARCH="x86_64" ;;
        *) die "Unsupported arch: $ARCH" ;;
    esac
    PIPER_VERSION="2023.11.14-2"
    PIPER_TAR="piper_${PIPER_ARCH}.tar.gz"
    PIPER_URL="https://github.com/rhasspy/piper/releases/download/${PIPER_VERSION}/${PIPER_TAR}"
    wget -q "$PIPER_URL" -O /tmp/piper.tar.gz
    tar -xzf /tmp/piper.tar.gz -C /tmp
    sudo cp /tmp/piper/piper "$PIPER_BIN"
    sudo chmod +x "$PIPER_BIN"
    rm -rf /tmp/piper /tmp/piper.tar.gz
fi
info "Piper: $PIPER_BIN"

# --------------------------------------------------------------------
# 5. Python dependencies
# --------------------------------------------------------------------
info "Installing Python dependencies…"
cd "$REPO_DIR"
uv sync --frozen 2>/dev/null || uv sync

# --------------------------------------------------------------------
# 6. Frontend build (pnpm)
# --------------------------------------------------------------------
FRONTEND_DIR="$REPO_DIR/frontend"
if [ -d "$FRONTEND_DIR" ]; then
    # Install Node.js if missing (needed for pnpm)
    if ! command -v node &>/dev/null; then
        info "Installing Node.js via NodeSource…"
        curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
        sudo apt-get install -y nodejs
    fi
    info "Node: $(node --version), npm: $(npm --version)"

    # Install pnpm
    if ! command -v pnpm &>/dev/null; then
        info "Installing pnpm…"
        npm install -g pnpm
    fi
    info "pnpm: $(pnpm --version)"

    info "Building frontend…"
    cd "$FRONTEND_DIR"
    pnpm install
    pnpm build
    cd "$REPO_DIR"
fi

# --------------------------------------------------------------------
# 7. Default model downloads
# --------------------------------------------------------------------
info "Downloading default models…"
bash "$REPO_DIR/scripts/pull_default_models.sh"

# --------------------------------------------------------------------
# 8. Service user
# --------------------------------------------------------------------
if ! id "$SERVICE_USER" &>/dev/null; then
    info "Creating service user: $SERVICE_USER"
    sudo useradd -r -m -s /bin/false "$SERVICE_USER"
    sudo usermod -aG audio "$SERVICE_USER"
fi
# Give the service user read access to the repo and write access to data/
sudo chown -R "$SERVICE_USER:$SERVICE_USER" "$REPO_DIR/data" 2>/dev/null || true
sudo chmod -R a+rX "$REPO_DIR"

# --------------------------------------------------------------------
# 9. systemd service
# --------------------------------------------------------------------
SYSTEMD_SRC="$REPO_DIR/scripts/systemd/voice-assistant.service"
SYSTEMD_DEST="/etc/systemd/system/voice-assistant.service"

if [ -f "$SYSTEMD_SRC" ]; then
    info "Installing systemd service…"
    # Substitute real paths
    sed \
        -e "s|__REPO_DIR__|$REPO_DIR|g" \
        -e "s|__SERVICE_USER__|$SERVICE_USER|g" \
        -e "s|__PORT__|$PORT|g" \
        "$SYSTEMD_SRC" | sudo tee "$SYSTEMD_DEST" > /dev/null
    sudo systemctl daemon-reload
    sudo systemctl enable voice-assistant
    sudo systemctl restart voice-assistant
fi

# --------------------------------------------------------------------
# Done
# --------------------------------------------------------------------
IP=$(hostname -I | awk '{print $1}')
echo ""
echo "╔══════════════════════════════════════════╗"
echo "║  Voice Assistant installed successfully! ║"
echo "╚══════════════════════════════════════════╝"
echo ""
echo "  Dashboard: http://${IP}:${PORT}"
echo "  Logs:      journalctl -u voice-assistant -f"
echo ""

"""Configuration system — loads default.yaml, overlays runtime.json, exposes typed models."""

from __future__ import annotations

import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Any, Optional

import yaml
from pydantic import BaseModel, Field, model_validator

logger = logging.getLogger(__name__)

_CONFIG_DIR = Path(__file__).parent.parent.parent / "configs"
DEFAULT_YAML = _CONFIG_DIR / "default.yaml"
RUNTIME_JSON = _CONFIG_DIR / "runtime.json"


# ---------------------------------------------------------------------------
# Sub-models
# ---------------------------------------------------------------------------

class AudioConfig(BaseModel):
    input_device: Optional[str | int] = None
    output_device: Optional[str | int] = None
    sample_rate: int = 16000
    channels: int = 1


class VADConfig(BaseModel):
    enabled: bool = True
    threshold: float = Field(0.5, ge=0.0, le=1.0)
    min_speech_ms: int = Field(250, ge=0)
    silence_timeout_ms: int = Field(800, ge=0)


class STTConfig(BaseModel):
    backend: str = "faster_whisper"
    model: str = "base.en"
    compute_type: str = "int8"
    language: str = "en"
    beam_size: int = Field(1, ge=1)


class LLMConfig(BaseModel):
    backend: str = "ollama"
    base_url: str = "http://127.0.0.1:11434"
    model: str = "llama3.2:3b"
    temperature: float = Field(0.7, ge=0.0, le=2.0)
    top_p: float = Field(0.9, ge=0.0, le=1.0)
    top_k: int = Field(40, ge=0)
    num_ctx: int = Field(4096, ge=512)
    num_predict: int = Field(512, ge=1)
    repeat_penalty: float = Field(1.1, ge=0.0)
    system_prompt: str = (
        "You are a concise, friendly voice assistant. Answer in 1–3 sentences "
        "unless the user asks for more detail. Avoid markdown and lists."
    )
    keep_alive: str = "10m"


class TTSConfig(BaseModel):
    backend: str = "piper"
    voice: str = "en_US-lessac-medium"
    speed: float = Field(1.0, ge=0.1, le=3.0)
    noise_scale: float = Field(0.667, ge=0.0, le=1.0)
    length_scale: float = Field(1.0, ge=0.1, le=3.0)


class ConversationConfig(BaseModel):
    history_turns: int = Field(6, ge=1)
    store_to_disk: bool = True


class ServerConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = Field(8080, ge=1, le=65535)


class AppConfig(BaseModel):
    mode: str = "continuous"  # continuous | push_to_talk
    audio: AudioConfig = Field(default_factory=AudioConfig)
    vad: VADConfig = Field(default_factory=VADConfig)
    stt: STTConfig = Field(default_factory=STTConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    tts: TTSConfig = Field(default_factory=TTSConfig)
    conversation: ConversationConfig = Field(default_factory=ConversationConfig)
    server: ServerConfig = Field(default_factory=ServerConfig)

    @model_validator(mode="after")
    def validate_mode(self) -> "AppConfig":
        if self.mode not in ("continuous", "push_to_talk"):
            raise ValueError("mode must be 'continuous' or 'push_to_talk'")
        return self


# ---------------------------------------------------------------------------
# ConfigStore
# ---------------------------------------------------------------------------

def _deep_merge(base: dict, overlay: dict) -> dict:
    result = dict(base)
    for key, value in overlay.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


class ConfigStore:
    """Manages loading, merging, updating, and persisting configuration."""

    def __init__(
        self,
        default_path: Path = DEFAULT_YAML,
        runtime_path: Path = RUNTIME_JSON,
    ) -> None:
        self._default_path = default_path
        self._runtime_path = runtime_path
        self._config: AppConfig = AppConfig()
        self._lock = asyncio.Lock()
        self._listeners: list[Any] = []
        self.reload()

    # ------------------------------------------------------------------
    def reload(self) -> None:
        raw: dict[str, Any] = {}
        if self._default_path.exists():
            with open(self._default_path) as f:
                raw = yaml.safe_load(f) or {}

        if self._runtime_path.exists():
            try:
                with open(self._runtime_path) as f:
                    runtime = json.load(f)
                raw = _deep_merge(raw, runtime)
            except Exception as exc:
                logger.warning("Could not load runtime config: %s", exc)

        self._config = AppConfig.model_validate(raw)

    # ------------------------------------------------------------------
    def get(self) -> AppConfig:
        return self._config

    # ------------------------------------------------------------------
    async def update(self, patch: dict[str, Any]) -> AppConfig:
        async with self._lock:
            current_dict = self._config.model_dump()
            merged = _deep_merge(current_dict, patch)
            new_config = AppConfig.model_validate(merged)
            self._config = new_config
            self._persist(merged)
            await self._emit_changed()
        return self._config

    # ------------------------------------------------------------------
    def _persist(self, data: dict[str, Any]) -> None:
        self._runtime_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._runtime_path.with_suffix(".tmp")
        with open(tmp, "w") as f:
            json.dump(data, f, indent=2)
        tmp.replace(self._runtime_path)

    # ------------------------------------------------------------------
    def subscribe(self, handler: Any) -> None:
        self._listeners.append(handler)

    def unsubscribe(self, handler: Any) -> None:
        self._listeners.discard(handler) if hasattr(self._listeners, "discard") else None
        if handler in self._listeners:
            self._listeners.remove(handler)

    async def _emit_changed(self) -> None:
        for handler in list(self._listeners):
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(self._config)
                else:
                    handler(self._config)
            except Exception as exc:
                logger.error("Config change handler error: %s", exc)


# Singleton
_store: Optional[ConfigStore] = None


def get_config_store() -> ConfigStore:
    global _store
    if _store is None:
        _store = ConfigStore()
    return _store

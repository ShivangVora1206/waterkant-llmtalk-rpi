"""Piper TTS backend — invokes piper as a subprocess, streams stdout."""

from __future__ import annotations

import asyncio
import json
import logging
import shutil
import urllib.request
from pathlib import Path
from typing import AsyncIterator, Optional

from .base import TTSBackend, VoiceInfo

logger = logging.getLogger(__name__)

VOICE_DIR = Path(__file__).parent.parent.parent.parent / "data" / "models" / "piper"

# Curated voice list with HF download URLs
KNOWN_VOICES: dict[str, dict] = {
    "en_US-lessac-medium": {
        "language": "en",
        "sample_rate": 22050,
        "size_mb": 63.0,
        "onnx_url": "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx",
        "json_url": "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx.json",
    },
    "en_US-amy-medium": {
        "language": "en",
        "sample_rate": 22050,
        "size_mb": 63.0,
        "onnx_url": "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/amy/medium/en_US-amy-medium.onnx",
        "json_url": "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/amy/medium/en_US-amy-medium.onnx.json",
    },
    "en_GB-alan-medium": {
        "language": "en",
        "sample_rate": 22050,
        "size_mb": 62.0,
        "onnx_url": "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_GB/alan/medium/en_GB-alan-medium.onnx",
        "json_url": "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_GB/alan/medium/en_GB-alan-medium.onnx.json",
    },
    "en_US-ryan-high": {
        "language": "en",
        "sample_rate": 22050,
        "size_mb": 116.0,
        "onnx_url": "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/ryan/high/en_US-ryan-high.onnx",
        "json_url": "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/ryan/high/en_US-ryan-high.onnx.json",
    },
}


class PiperBackend(TTSBackend):
    def __init__(
        self,
        voice: str = "en_US-lessac-medium",
        speed: float = 1.0,
        noise_scale: float = 0.667,
        length_scale: float = 1.0,
    ) -> None:
        self.voice = voice
        self.speed = speed
        self.noise_scale = noise_scale
        self.length_scale = length_scale
        self._piper_bin: Optional[str] = None

    def _find_piper(self) -> str:
        if self._piper_bin:
            return self._piper_bin
        # Prefer the Python package — it's in the venv and works on ARM64
        try:
            from piper.voice import PiperVoice  # type: ignore  # noqa: F401
            self._piper_bin = "__piper_python__"
            return "__piper_python__"
        except ImportError:
            pass
        # Fall back to system binary
        candidate = shutil.which("piper")
        if candidate:
            self._piper_bin = candidate
            return candidate
        raise FileNotFoundError(
            "Piper TTS not found. Run: uv pip install piper-tts"
        )

    def _voice_path(self, voice: Optional[str] = None) -> Path:
        return VOICE_DIR / f"{voice or self.voice}.onnx"

    def available_voices(self) -> list[VoiceInfo]:
        voices = []
        for name, meta in KNOWN_VOICES.items():
            voices.append(
                VoiceInfo(
                    name=name,
                    language=meta["language"],
                    sample_rate=meta["sample_rate"],
                    size_mb=meta["size_mb"],
                )
            )
        return voices

    def downloaded_voices(self) -> list[str]:
        if not VOICE_DIR.exists():
            return []
        return [p.stem for p in VOICE_DIR.glob("*.onnx")]

    async def load_voice(self, name: str) -> None:
        self.voice = name
        onnx_path = self._voice_path(name)
        if not onnx_path.exists():
            await self.download_voice(name)

    async def unload(self) -> None:
        pass

    async def download_voice(self, name: str) -> None:
        if name not in KNOWN_VOICES:
            raise ValueError(f"Unknown voice: {name}")
        meta = KNOWN_VOICES[name]
        VOICE_DIR.mkdir(parents=True, exist_ok=True)
        onnx_path = VOICE_DIR / f"{name}.onnx"
        json_path = VOICE_DIR / f"{name}.onnx.json"
        logger.info("Downloading voice %s...", name)
        if not onnx_path.exists():
            urllib.request.urlretrieve(meta["onnx_url"], onnx_path)
        if not json_path.exists():
            urllib.request.urlretrieve(meta["json_url"], json_path)
        logger.info("Voice %s downloaded to %s", name, VOICE_DIR)

    async def synthesise(self, text: str, params: dict | None = None) -> AsyncIterator[bytes]:
        if params is None:
            params = {}
        voice = params.get("voice", self.voice)
        noise_scale = params.get("noise_scale", self.noise_scale)
        length_scale = params.get("length_scale", self.length_scale)
        speed = params.get("speed", self.speed)
        actual_length = length_scale / speed  # speed mapped to length_scale

        onnx_path = self._voice_path(voice)
        if not onnx_path.exists():
            await self.download_voice(voice)

        piper_bin = self._find_piper()

        if piper_bin == "__piper_python__":
            async for chunk in self._synthesise_python(text, voice, noise_scale, actual_length):
                yield chunk
        else:
            async for chunk in self._synthesise_subprocess(
                text, piper_bin, onnx_path, noise_scale, actual_length
            ):
                yield chunk

    async def _synthesise_subprocess(
        self,
        text: str,
        piper_bin: str,
        onnx_path: Path,
        noise_scale: float,
        length_scale: float,
    ) -> AsyncIterator[bytes]:
        json_path = onnx_path.with_suffix(".onnx.json")
        cmd = [
            piper_bin,
            "--model", str(onnx_path),
            "--config", str(json_path),
            "--noise_scale", str(noise_scale),
            "--length_scale", str(length_scale),
            "--output-raw",
        ]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        proc.stdin.write(text.encode())
        await proc.stdin.drain()
        proc.stdin.close()

        chunk_size = 4096
        while True:
            chunk = await proc.stdout.read(chunk_size)
            if not chunk:
                break
            yield chunk

        await proc.wait()

    async def _synthesise_python(
        self,
        text: str,
        voice: str,
        noise_scale: float,
        length_scale: float,
    ) -> AsyncIterator[bytes]:
        import io
        # piper-tts package uses piper.voice.PiperVoice
        try:
            from piper.voice import PiperVoice  # type: ignore
        except ImportError:
            from piper import PiperVoice  # type: ignore  # older package layout

        onnx_path = self._voice_path(voice)
        loop = asyncio.get_event_loop()
        # Run in executor so it doesn't block the event loop
        piper_voice = await loop.run_in_executor(None, PiperVoice.load, str(onnx_path))

        # Patch synthesis config if the voice config object exposes these fields
        if hasattr(piper_voice, "config"):
            cfg = piper_voice.config
            if hasattr(cfg, "noise_scale"):
                cfg.noise_scale = noise_scale
            if hasattr(cfg, "length_scale"):
                cfg.length_scale = length_scale

        buf = io.BytesIO()

        # synthesize() signature varies by piper-tts version — try with kwargs first
        import inspect
        sig = inspect.signature(piper_voice.synthesize)
        extra = {}
        if "noise_scale" in sig.parameters:
            extra["noise_scale"] = noise_scale
        if "length_scale" in sig.parameters:
            extra["length_scale"] = length_scale

        await loop.run_in_executor(
            None,
            lambda: piper_voice.synthesize(text, buf, **extra),
        )
        data = buf.getvalue()
        chunk_size = 4096
        for i in range(0, len(data), chunk_size):
            yield data[i : i + chunk_size]

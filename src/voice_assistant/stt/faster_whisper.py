"""faster-whisper STT backend."""

from __future__ import annotations

import io
import logging
import time
from pathlib import Path
from typing import Optional

import numpy as np

from .base import STTBackend, Transcript, TranscriptSegment

logger = logging.getLogger(__name__)

MODEL_CACHE = Path(__file__).parent.parent.parent.parent / "data" / "models" / "whisper"

AVAILABLE_MODELS = [
    "tiny.en",
    "base.en",
    "small.en",
    "medium.en",
    "large-v3",
    "distil-small.en",
    "distil-medium.en",
]


class FasterWhisperBackend(STTBackend):
    def __init__(
        self,
        model_name: str = "base.en",
        compute_type: str = "int8",
        language: str = "en",
        beam_size: int = 1,
    ) -> None:
        self.model_name = model_name
        self.compute_type = compute_type
        self.language = language
        self.beam_size = beam_size
        self._model = None

    # ------------------------------------------------------------------
    def available_models(self) -> list[str]:
        return AVAILABLE_MODELS

    def downloaded_models(self) -> list[str]:
        if not MODEL_CACHE.exists():
            return []
        return [d.name for d in MODEL_CACHE.iterdir() if d.is_dir()]

    # ------------------------------------------------------------------
    async def load(self, model_name: Optional[str] = None) -> None:
        import psutil
        from faster_whisper import WhisperModel

        if model_name:
            self.model_name = model_name

        mem_before = psutil.Process().memory_info().rss
        await self.unload()

        MODEL_CACHE.mkdir(parents=True, exist_ok=True)
        logger.info("Loading Whisper model %s (compute_type=%s)", self.model_name, self.compute_type)
        self._model = WhisperModel(
            self.model_name,
            device="cpu",
            compute_type=self.compute_type,
            download_root=str(MODEL_CACHE),
        )

        # Warm-up: 1 s of silence avoids first-call spike
        silence = np.zeros(16000, dtype=np.int16).tobytes()
        await self.transcribe(silence, 16000)

        mem_after = psutil.Process().memory_info().rss
        logger.info(
            "Whisper %s loaded (Δ RAM %.1f MB)",
            self.model_name,
            (mem_after - mem_before) / 1024**2,
        )

    async def unload(self) -> None:
        if self._model is not None:
            del self._model
            self._model = None
            import gc
            gc.collect()
            logger.info("Whisper model unloaded")

    # ------------------------------------------------------------------
    async def transcribe(self, pcm: bytes, sample_rate: int) -> Transcript:
        if self._model is None:
            await self.load()

        t0 = time.monotonic()
        audio = np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768.0

        segments_iter, info = self._model.transcribe(
            audio,
            language=self.language if self.language != "auto" else None,
            beam_size=self.beam_size,
            vad_filter=False,  # we do VAD ourselves
        )

        segments = []
        text_parts = []
        for seg in segments_iter:
            segments.append(TranscriptSegment(seg.start, seg.end, seg.text.strip()))
            text_parts.append(seg.text.strip())

        latency_ms = (time.monotonic() - t0) * 1000
        text = " ".join(text_parts).strip()

        return Transcript(
            text=text,
            language=info.language,
            confidence=float(info.language_probability) if hasattr(info, "language_probability") else 1.0,
            segments=segments,
            latency_ms=latency_ms,
        )

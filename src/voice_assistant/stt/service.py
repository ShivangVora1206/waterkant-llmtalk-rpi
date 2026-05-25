"""STT service: glues VAD output → STT backend → event bus."""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

from ..audio.vad import VADEvent, VADProcessor
from ..utils.events import EventBus
from .base import STTBackend

logger = logging.getLogger(__name__)


class STTService:
    def __init__(
        self,
        backend: STTBackend,
        vad: VADProcessor,
        event_bus: EventBus,
        sample_rate: int = 16000,
        min_speech_ms: int = 250,
    ) -> None:
        self._backend = backend
        self._vad = vad
        self._bus = event_bus
        self._sample_rate = sample_rate
        self._min_speech_ms = min_speech_ms
        self._buffer: list[bytes] = []
        self._capturing = False

    async def process_frame(self, pcm: bytes) -> None:
        """Feed a PCM frame through VAD and buffer speech."""
        event = self._vad.feed(pcm)

        if event == VADEvent.SPEECH_START:
            self._buffer.clear()
            self._capturing = True
            logger.debug("Speech started")

        if self._capturing:
            self._buffer.append(pcm)

        if event == VADEvent.SPEECH_END and self._capturing:
            self._capturing = False
            audio = b"".join(self._buffer)
            self._buffer.clear()

            # Check minimum duration
            duration_ms = len(audio) / 2 / self._sample_rate * 1000
            if duration_ms < self._min_speech_ms:
                logger.debug("Utterance too short (%.0f ms) — dropped", duration_ms)
                return

            transcript = await self._backend.transcribe(audio, self._sample_rate)
            if transcript.text.strip():
                await self._bus.publish("stt.final", {
                    "text": transcript.text,
                    "language": transcript.language,
                    "confidence": transcript.confidence,
                    "latency_ms": transcript.latency_ms,
                    "duration_ms": duration_ms,
                })

    def start_capture(self) -> None:
        self._vad.reset()
        self._capturing = False
        self._buffer.clear()

    def stop_capture(self) -> None:
        self._capturing = False
        self._buffer.clear()

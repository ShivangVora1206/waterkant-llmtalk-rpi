"""TTS service: buffers LLM tokens → sentence-batched TTS → playback."""

from __future__ import annotations

import asyncio
import logging
import re
import time
from typing import AsyncIterator, Optional

from ..audio.playback import AudioPlayback
from ..utils.events import EventBus
from .base import TTSBackend

logger = logging.getLogger(__name__)

SENTENCE_END_RE = re.compile(r"(?<=[.!?])\s+|(?<=[.!?])$")
MIN_FLUSH_CHARS = 20


class TTSService:
    def __init__(
        self,
        backend: TTSBackend,
        playback: AudioPlayback,
        event_bus: EventBus,
    ) -> None:
        self._backend = backend
        self._playback = playback
        self._bus = event_bus
        self._current_task: Optional[asyncio.Task] = None

    async def speak_stream(self, token_stream: AsyncIterator[str]) -> None:
        """Consume an async token stream, TTS each sentence, play immediately."""
        buffer = ""
        sentence_index = 0

        async for token in token_stream:
            buffer += token
            sentences = self._split_sentences(buffer)
            if len(sentences) > 1:
                for sentence in sentences[:-1]:
                    sentence = sentence.strip()
                    if sentence:
                        await self._synthesise_and_play(sentence, sentence_index)
                        sentence_index += 1
                buffer = sentences[-1]

        # Flush remaining
        if buffer.strip():
            await self._synthesise_and_play(buffer.strip(), sentence_index)

    def _split_sentences(self, text: str) -> list[str]:
        parts = SENTENCE_END_RE.split(text)
        return parts if parts else [text]

    async def _synthesise_and_play(self, text: str, index: int) -> None:
        t0 = time.monotonic()
        await self._bus.publish("tts.started", {"sentence": index, "text": text})

        chunks = self._backend.synthesise(text, {})
        await self._playback.play(chunks)

        latency_ms = (time.monotonic() - t0) * 1000
        await self._bus.publish("tts.ended", {
            "sentence": index,
            "text": text,
            "latency_ms": latency_ms,
        })

    async def speak_text(self, text: str) -> None:
        """Synthesise and play a single text string."""
        await self._synthesise_and_play(text, 0)

    def interrupt(self) -> None:
        """Immediately stop any ongoing playback."""
        self._playback.interrupt()

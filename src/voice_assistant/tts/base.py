"""Abstract TTS backend interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import AsyncIterator, Optional


@dataclass
class VoiceInfo:
    name: str
    language: str
    sample_rate: int
    size_mb: float


class TTSBackend(ABC):
    @abstractmethod
    async def synthesise(self, text: str, params: dict) -> AsyncIterator[bytes]:
        """Yield 22050 Hz mono int16 PCM chunks."""
        ...

    @abstractmethod
    def available_voices(self) -> list[VoiceInfo]:
        ...

    @abstractmethod
    async def load_voice(self, name: str) -> None:
        ...

    @abstractmethod
    async def unload(self) -> None:
        ...

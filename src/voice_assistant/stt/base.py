"""Abstract STT backend interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class TranscriptSegment:
    start: float
    end: float
    text: str


@dataclass
class Transcript:
    text: str
    language: str = "en"
    confidence: float = 1.0
    segments: list[TranscriptSegment] = field(default_factory=list)
    latency_ms: float = 0.0


class STTBackend(ABC):
    @abstractmethod
    async def transcribe(self, pcm: bytes, sample_rate: int) -> Transcript:
        ...

    @abstractmethod
    def available_models(self) -> list[str]:
        ...

    @abstractmethod
    async def load(self, model_name: str) -> None:
        ...

    @abstractmethod
    async def unload(self) -> None:
        ...

"""Abstract LLM backend interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Optional


@dataclass
class ModelInfo:
    name: str
    size_bytes: int = 0
    family: str = ""
    quantisation: str = ""
    modified_at: str = ""


@dataclass
class PullProgress:
    status: str
    total: int = 0
    completed: int = 0
    digest: str = ""


class LLMBackend(ABC):
    @abstractmethod
    async def stream(
        self,
        messages: list[dict[str, str]],
        params: dict[str, Any],
    ) -> AsyncIterator[str]:
        ...

    @abstractmethod
    async def list_models(self) -> list[ModelInfo]:
        ...

    @abstractmethod
    async def pull_model(self, name: str) -> AsyncIterator[PullProgress]:
        ...

    @abstractmethod
    async def delete_model(self, name: str) -> None:
        ...

    @abstractmethod
    async def model_info(self, name: str) -> Optional[ModelInfo]:
        ...

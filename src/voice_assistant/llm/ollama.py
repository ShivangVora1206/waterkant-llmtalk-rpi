"""Ollama LLM backend."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, AsyncIterator, Optional

import aiohttp

from ..utils.events import EventBus
from .base import LLMBackend, ModelInfo, PullProgress

logger = logging.getLogger(__name__)


class OllamaError(Exception):
    pass


class OllamaBackend(LLMBackend):
    def __init__(self, base_url: str = "http://127.0.0.1:11434", event_bus: Optional[EventBus] = None) -> None:
        self._base_url = base_url.rstrip("/")
        self._bus = event_bus
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=120, connect=10)
            self._session = aiohttp.ClientSession(timeout=timeout)
        return self._session

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()

    # ------------------------------------------------------------------
    async def stream(
        self,
        messages: list[dict[str, str]],
        params: dict[str, Any],
    ) -> AsyncIterator[str]:
        session = await self._get_session()
        payload = {
            "model": params.get("model", "llama3.2:3b"),
            "messages": messages,
            "stream": True,
            "options": {
                "temperature": params.get("temperature", 0.7),
                "top_p": params.get("top_p", 0.9),
                "top_k": params.get("top_k", 40),
                "num_ctx": params.get("num_ctx", 4096),
                "num_predict": params.get("num_predict", 512),
                "repeat_penalty": params.get("repeat_penalty", 1.1),
            },
            "keep_alive": params.get("keep_alive", "10m"),
        }

        try:
            async with session.post(f"{self._base_url}/api/chat", json=payload) as resp:
                if resp.status != 200:
                    body = await resp.text()
                    raise OllamaError(f"Ollama /api/chat returned {resp.status}: {body}")

                async for raw_line in resp.content:
                    line = raw_line.decode().strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    token = data.get("message", {}).get("content", "")
                    if token:
                        if self._bus:
                            await self._bus.publish("llm.token", {"token": token})
                        yield token

                    if data.get("done"):
                        if self._bus:
                            await self._bus.publish("llm.final", {"done": True})
                        break

        except aiohttp.ClientConnectorError as exc:
            raise OllamaError(f"Cannot connect to Ollama at {self._base_url}: {exc}") from exc
        except asyncio.CancelledError:
            raise
        except OllamaError:
            raise
        except Exception as exc:
            raise OllamaError(f"Unexpected Ollama error: {exc}") from exc

    # ------------------------------------------------------------------
    async def list_models(self) -> list[ModelInfo]:
        session = await self._get_session()
        try:
            async with session.get(f"{self._base_url}/api/tags") as resp:
                resp.raise_for_status()
                data = await resp.json()
            models = []
            for m in data.get("models", []):
                details = m.get("details", {})
                models.append(
                    ModelInfo(
                        name=m["name"],
                        size_bytes=m.get("size", 0),
                        family=details.get("family", ""),
                        quantisation=details.get("quantization_level", ""),
                        modified_at=m.get("modified_at", ""),
                    )
                )
            return models
        except Exception as exc:
            raise OllamaError(f"list_models failed: {exc}") from exc

    # ------------------------------------------------------------------
    async def pull_model(self, name: str) -> AsyncIterator[PullProgress]:
        session = await self._get_session()
        payload = {"name": name, "stream": True}
        try:
            async with session.post(f"{self._base_url}/api/pull", json=payload) as resp:
                resp.raise_for_status()
                async for raw_line in resp.content:
                    line = raw_line.decode().strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    progress = PullProgress(
                        status=data.get("status", ""),
                        total=data.get("total", 0),
                        completed=data.get("completed", 0),
                        digest=data.get("digest", ""),
                    )
                    if self._bus:
                        await self._bus.publish("llm.pull_progress", {
                            "model": name,
                            "status": progress.status,
                            "total": progress.total,
                            "completed": progress.completed,
                        })
                    yield progress
        except Exception as exc:
            raise OllamaError(f"pull_model failed: {exc}") from exc

    # ------------------------------------------------------------------
    async def delete_model(self, name: str) -> None:
        session = await self._get_session()
        try:
            async with session.delete(
                f"{self._base_url}/api/delete", json={"name": name}
            ) as resp:
                resp.raise_for_status()
        except Exception as exc:
            raise OllamaError(f"delete_model failed: {exc}") from exc

    # ------------------------------------------------------------------
    async def model_info(self, name: str) -> Optional[ModelInfo]:
        session = await self._get_session()
        try:
            async with session.post(f"{self._base_url}/api/show", json={"name": name}) as resp:
                if resp.status == 404:
                    return None
                resp.raise_for_status()
                data = await resp.json()
            details = data.get("details", {})
            return ModelInfo(
                name=name,
                size_bytes=data.get("size", 0),
                family=details.get("family", ""),
                quantisation=details.get("quantization_level", ""),
                modified_at=data.get("modified_at", ""),
            )
        except OllamaError:
            raise
        except Exception as exc:
            raise OllamaError(f"model_info failed: {exc}") from exc

    async def is_available(self) -> bool:
        try:
            session = await self._get_session()
            async with session.get(f"{self._base_url}/api/tags", timeout=aiohttp.ClientTimeout(total=3)) as resp:
                return resp.status == 200
        except Exception:
            return False

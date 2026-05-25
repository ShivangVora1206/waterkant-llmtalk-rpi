"""Async in-process event bus."""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from typing import Any, Callable, Coroutine

logger = logging.getLogger(__name__)

Handler = Callable[..., Coroutine | Any]

TOPICS = (
    "state.changed",
    "stt.partial",
    "stt.final",
    "llm.token",
    "llm.final",
    "tts.started",
    "tts.ended",
    "audio.level",
    "system.health",
    "config.changed",
    "error",
)


class EventBus:
    def __init__(self) -> None:
        self._handlers: dict[str, list[Handler]] = defaultdict(list)

    def subscribe(self, topic: str, handler: Handler) -> None:
        self._handlers[topic].append(handler)

    def unsubscribe(self, topic: str, handler: Handler) -> None:
        handlers = self._handlers[topic]
        if handler in handlers:
            handlers.remove(handler)

    async def publish(self, topic: str, payload: Any = None) -> None:
        handlers = list(self._handlers.get(topic, []))
        for handler in handlers:
            try:
                result = handler(topic, payload)
                if asyncio.iscoroutine(result):
                    await result
            except Exception as exc:
                logger.error("Event handler error for topic %s: %s", topic, exc)

    def subscribe_many(self, topics: list[str], handler: Handler) -> None:
        for topic in topics:
            self.subscribe(topic, handler)


# Singleton
_bus: EventBus | None = None


def get_event_bus() -> EventBus:
    global _bus
    if _bus is None:
        _bus = EventBus()
    return _bus

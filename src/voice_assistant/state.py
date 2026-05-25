"""Pipeline state machine."""

from __future__ import annotations

import asyncio
import logging
from enum import Enum
from typing import Any, Callable, Coroutine, Optional

logger = logging.getLogger(__name__)

Hook = Callable[["PipelineState", "PipelineState"], Coroutine | None]


class PipelineState(str, Enum):
    IDLE = "IDLE"
    LISTENING = "LISTENING"
    TRANSCRIBING = "TRANSCRIBING"
    THINKING = "THINKING"
    SPEAKING = "SPEAKING"
    PAUSED = "PAUSED"
    ERROR = "ERROR"


# Allowed transitions: {from_state: {to_states}}
ALLOWED_TRANSITIONS: dict[PipelineState, set[PipelineState]] = {
    PipelineState.IDLE: {
        PipelineState.LISTENING,
        PipelineState.PAUSED,
        PipelineState.ERROR,
    },
    PipelineState.LISTENING: {
        PipelineState.TRANSCRIBING,
        PipelineState.IDLE,
        PipelineState.PAUSED,
        PipelineState.ERROR,
    },
    PipelineState.TRANSCRIBING: {
        PipelineState.THINKING,
        PipelineState.IDLE,
        PipelineState.ERROR,
    },
    PipelineState.THINKING: {
        PipelineState.SPEAKING,
        PipelineState.IDLE,
        PipelineState.ERROR,
    },
    PipelineState.SPEAKING: {
        PipelineState.IDLE,
        PipelineState.LISTENING,  # barge-in
        PipelineState.ERROR,
    },
    PipelineState.PAUSED: {
        PipelineState.IDLE,
        PipelineState.LISTENING,
        PipelineState.ERROR,
    },
    PipelineState.ERROR: {
        PipelineState.IDLE,
        PipelineState.LISTENING,
    },
}


class InvalidTransitionError(Exception):
    pass


class StateMachine:
    def __init__(self, event_bus: Any | None = None) -> None:
        self._state = PipelineState.IDLE
        self._event_bus = event_bus
        self._hooks: list[Hook] = []
        self._lock = asyncio.Lock()

    @property
    def state(self) -> PipelineState:
        return self._state

    def add_hook(self, hook: Hook) -> None:
        self._hooks.append(hook)

    async def transition(self, new_state: PipelineState) -> None:
        async with self._lock:
            old = self._state
            allowed = ALLOWED_TRANSITIONS.get(old, set())
            if new_state not in allowed:
                raise InvalidTransitionError(
                    f"Cannot transition from {old} to {new_state}. "
                    f"Allowed: {[s.value for s in allowed]}"
                )
            self._state = new_state
            logger.debug("State: %s → %s", old.value, new_state.value)

        for hook in list(self._hooks):
            try:
                result = hook(old, new_state)
                if asyncio.iscoroutine(result):
                    await result
            except Exception as exc:
                logger.error("State hook error: %s", exc)

        if self._event_bus is not None:
            await self._event_bus.publish(
                "state.changed",
                {"from": old.value, "to": new_state.value},
            )

    async def force(self, new_state: PipelineState) -> None:
        """Force transition, bypassing allowed-transition check (for error recovery)."""
        async with self._lock:
            old = self._state
            self._state = new_state
            logger.warning("Forced state: %s → %s", old.value, new_state.value)

        if self._event_bus is not None:
            await self._event_bus.publish(
                "state.changed",
                {"from": old.value, "to": new_state.value, "forced": True},
            )

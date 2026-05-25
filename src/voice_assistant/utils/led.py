"""Optional GPIO LED status indicator."""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

from ..state import PipelineState

logger = logging.getLogger(__name__)

STATE_PATTERNS: dict[PipelineState, tuple] = {
    PipelineState.IDLE: ("off", None),
    PipelineState.LISTENING: ("on", None),
    PipelineState.TRANSCRIBING: ("blink", 0.3),
    PipelineState.THINKING: ("blink", 0.5),
    PipelineState.SPEAKING: ("on", None),
    PipelineState.PAUSED: ("blink", 1.0),
    PipelineState.ERROR: ("blink", 0.1),
}


class LEDIndicator:
    def __init__(self, pin: int = 18, event_bus: Optional[object] = None) -> None:
        self.pin = pin
        self._bus = event_bus
        self._led = None
        self._blink_task: Optional[asyncio.Task] = None

    def start(self) -> None:
        try:
            from gpiozero import LED  # type: ignore

            self._led = LED(self.pin)
            if self._bus:
                self._bus.subscribe("state.changed", self._on_state_changed)
            logger.info("LED indicator active on pin %d", self.pin)
        except ImportError:
            logger.debug("gpiozero not available — LED disabled")
        except Exception as exc:
            logger.debug("LED init failed: %s", exc)

    def stop(self) -> None:
        if self._led:
            try:
                self._led.off()
                self._led.close()
            except Exception:
                pass

    async def _on_state_changed(self, topic: str, payload: dict) -> None:
        try:
            state = PipelineState(payload.get("to", "IDLE"))
        except ValueError:
            return

        if self._blink_task:
            self._blink_task.cancel()
            self._blink_task = None

        pattern, interval = STATE_PATTERNS.get(state, ("off", None))
        if not self._led:
            return

        if pattern == "off":
            self._led.off()
        elif pattern == "on":
            self._led.on()
        elif pattern == "blink" and interval:
            self._blink_task = asyncio.create_task(self._blink(interval))

    async def _blink(self, interval: float) -> None:
        if not self._led:
            return
        while True:
            self._led.on()
            await asyncio.sleep(interval)
            self._led.off()
            await asyncio.sleep(interval)

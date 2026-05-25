"""Optional GPIO push-to-talk button support via gpiozero."""

from __future__ import annotations

import asyncio
import logging
from typing import Callable, Optional

logger = logging.getLogger(__name__)


class GPIOPushToTalk:
    """Monitors a GPIO button and fires async callbacks on press/release."""

    def __init__(
        self,
        pin: int = 17,
        on_press: Optional[Callable] = None,
        on_release: Optional[Callable] = None,
    ) -> None:
        self.pin = pin
        self._on_press = on_press
        self._on_release = on_release
        self._button = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def start(self, loop: asyncio.AbstractEventLoop) -> None:
        try:
            from gpiozero import Button  # type: ignore

            self._loop = loop
            self._button = Button(self.pin, pull_up=True)
            self._button.when_pressed = self._pressed
            self._button.when_released = self._released
            logger.info("GPIO PTT active on pin %d", self.pin)
        except ImportError:
            logger.warning("gpiozero not available — GPIO PTT disabled")
        except Exception as exc:
            logger.error("GPIO PTT init failed: %s", exc)

    def stop(self) -> None:
        if self._button:
            self._button.close()

    def _pressed(self) -> None:
        if self._on_press and self._loop:
            asyncio.run_coroutine_threadsafe(self._on_press(), self._loop)

    def _released(self) -> None:
        if self._on_release and self._loop:
            asyncio.run_coroutine_threadsafe(self._on_release(), self._loop)

"""Async ring-buffered microphone capture producing 20 ms PCM frames."""

from __future__ import annotations

import asyncio
import logging
import math
import time
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

FRAME_MS = 20  # ms per frame


class AudioCapture:
    """Opens a sounddevice input stream and pushes int16 PCM frames to a queue."""

    def __init__(
        self,
        sample_rate: int = 16000,
        channels: int = 1,
        device: Optional[str | int] = None,
        event_bus: Optional[object] = None,
    ) -> None:
        self.sample_rate = sample_rate
        self.channels = channels
        self.device = device
        self._event_bus = event_bus
        self._queue: asyncio.Queue[bytes] = asyncio.Queue(maxsize=200)
        self._stream = None
        self._running = False
        self._xrun_count = 0
        self._frame_size = int(sample_rate * FRAME_MS / 1000)
        self._level_accum: list[float] = []
        self._last_level_publish = 0.0

    # ------------------------------------------------------------------
    def _callback(self, indata: np.ndarray, frames: int, time_info, status) -> None:
        if status and status.input_overflow:
            self._xrun_count += 1
            logger.warning("Audio XRUN (overflow); total=%d", self._xrun_count)

        pcm = (indata[:, 0] * 32767).astype(np.int16).tobytes()
        try:
            self._queue.put_nowait(pcm)
        except asyncio.QueueFull:
            pass  # drop frame if consumer is slow

        # Accumulate RMS for level meter
        rms = float(np.sqrt(np.mean(indata**2)))
        self._level_accum.append(rms)

    # ------------------------------------------------------------------
    async def start(self) -> None:
        if self._running:
            return
        import sounddevice as sd
        from .playback import _resolve_input_device

        resolved = _resolve_input_device(self.device)
        loop = asyncio.get_event_loop()

        def _cb(indata, frames, time_info, status):
            loop.call_soon_threadsafe(self._callback, indata.copy(), frames, time_info, status)

        self._stream = sd.InputStream(
            samplerate=self.sample_rate,
            channels=self.channels,
            dtype="float32",
            device=resolved,
            blocksize=self._frame_size,
            callback=_cb,
        )
        self._stream.start()
        self._running = True
        logger.info("AudioCapture started (device=%s, rate=%d)", resolved, self.sample_rate)

        asyncio.create_task(self._level_publisher())

    async def stop(self) -> None:
        self._running = False
        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None
        logger.info("AudioCapture stopped (xruns=%d)", self._xrun_count)

    async def read_frame(self) -> bytes:
        return await self._queue.get()

    def __aiter__(self):
        return self

    async def __anext__(self) -> bytes:
        if not self._running:
            raise StopAsyncIteration
        return await self._queue.get()

    # ------------------------------------------------------------------
    async def _level_publisher(self) -> None:
        """Publish audio.level events at ~10 Hz while running."""
        while self._running:
            await asyncio.sleep(0.1)
            if self._level_accum and self._event_bus:
                rms = float(np.mean(self._level_accum))
                self._level_accum.clear()
                db = 20 * math.log10(max(rms, 1e-9))
                await self._event_bus.publish("audio.level", {"dbfs": round(db, 1)})

    @property
    def xrun_count(self) -> int:
        return self._xrun_count

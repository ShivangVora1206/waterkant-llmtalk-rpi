"""Async ring-buffered microphone capture producing 20 ms PCM frames."""

from __future__ import annotations

import asyncio
import logging
import math
import time
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

FRAME_MS = 20           # ms per frame (at target rate)
CAPTURE_HW_RATE = 48000  # open hardware at this rate; resample down to sample_rate


def _resample_float(data: np.ndarray, from_rate: int, to_rate: int) -> np.ndarray:
    """Linear-interpolation resample for float32 audio."""
    if from_rate == to_rate:
        return data
    target_len = int(len(data) * to_rate / from_rate)
    x_old = np.linspace(0, 1, len(data))
    x_new = np.linspace(0, 1, target_len)
    return np.interp(x_new, x_old, data).astype(np.float32)


class AudioCapture:
    """Opens a sounddevice input stream and pushes int16 PCM frames to a queue.

    The hardware is always opened at CAPTURE_HW_RATE (48 kHz) which is the
    native rate for both PipeWire-ALSA and most USB microphones.  Each frame
    is resampled down to `sample_rate` (default 16 kHz) before being queued,
    so callers (VAD, STT) always see the configured rate.
    """

    def __init__(
        self,
        sample_rate: int = 16000,
        channels: int = 1,
        device: Optional[str | int] = None,
        event_bus: Optional[object] = None,
    ) -> None:
        self.sample_rate = sample_rate      # rate exposed to consumers
        self.channels = channels
        self.device = device
        self._event_bus = event_bus
        self._hw_rate = CAPTURE_HW_RATE    # rate used for the hardware stream
        self._queue: asyncio.Queue[bytes] = asyncio.Queue(maxsize=200)
        self._stream = None
        self._running = False
        self._xrun_count = 0
        # frame_size is at the hardware rate so the OS gives us FRAME_MS-worth
        self._frame_size = int(self._hw_rate * FRAME_MS / 1000)
        self._level_accum: list[float] = []
        self._last_level_publish = 0.0

    # ------------------------------------------------------------------
    def _callback(self, indata: np.ndarray, frames: int, time_info, status) -> None:
        if status and status.input_overflow:
            self._xrun_count += 1
            logger.warning("Audio XRUN (overflow); total=%d", self._xrun_count)

        raw = indata[:, 0]  # float32 at _hw_rate

        # Resample from hardware rate to target consumer rate
        if self._hw_rate != self.sample_rate:
            raw = _resample_float(raw, self._hw_rate, self.sample_rate)

        pcm = (raw * 32767).astype(np.int16).tobytes()
        try:
            self._queue.put_nowait(pcm)
        except asyncio.QueueFull:
            pass  # drop frame if consumer is slow

        # Accumulate RMS for level meter (use original indata for accuracy)
        rms = float(np.sqrt(np.mean(indata ** 2)))
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

        logger.info(
            "Opening capture: device=%s hw_rate=%d target_rate=%d",
            resolved, self._hw_rate, self.sample_rate,
        )
        self._stream = sd.InputStream(
            samplerate=self._hw_rate,
            channels=self.channels,
            dtype="float32",
            device=resolved,
            blocksize=self._frame_size,
            callback=_cb,
        )
        self._stream.start()
        self._running = True
        logger.info("AudioCapture started (device=%s, hw_rate=%d→%d)", resolved, self._hw_rate, self.sample_rate)

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

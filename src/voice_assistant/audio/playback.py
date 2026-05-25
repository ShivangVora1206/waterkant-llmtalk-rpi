"""Async audio playback with barge-in support."""

from __future__ import annotations

import asyncio
import logging
from typing import AsyncIterator, Optional

import numpy as np

logger = logging.getLogger(__name__)

PLAYBACK_SAMPLE_RATE = 48000   # PipeWire native rate; Piper output is resampled up
PIPER_SAMPLE_RATE = 22050      # Piper always outputs 22050 Hz
PLAYBACK_CHANNELS = 1


def _resample(data: np.ndarray, from_rate: int, to_rate: int) -> np.ndarray:
    """Simple linear-interpolation resampler (no extra deps)."""
    if from_rate == to_rate:
        return data
    target_len = int(len(data) * to_rate / from_rate)
    x_old = np.linspace(0, 1, len(data))
    x_new = np.linspace(0, 1, target_len)
    return np.interp(x_new, x_old, data).astype(np.int16)


def _resolve_output_device(device: Optional[str | int]) -> Optional[str | int]:
    """Return a valid sounddevice output device identifier, or None for system default."""
    import sounddevice as sd

    if device is not None:
        return device

    # Try querying the default — if it returns -1 there is no ALSA default,
    # which happens on PipeWire-only setups. Fall back to the first output device found.
    try:
        info = sd.query_devices(kind="output")
        idx = info.get("index", -1) if isinstance(info, dict) else getattr(info, "index", -1)
        if idx >= 0:
            return None  # sounddevice default works fine
    except Exception:
        pass

    # Enumerate and take the first device with output channels
    try:
        for i, dev in enumerate(sd.query_devices()):
            if dev["max_output_channels"] > 0:
                logger.info("No ALSA default output — falling back to device %d: %s", i, dev["name"])
                return i
    except Exception:
        pass

    return None  # let sounddevice try anyway


def _resolve_input_device(device: Optional[str | int]) -> Optional[str | int]:
    """Return a valid sounddevice input device identifier."""
    import sounddevice as sd

    if device is not None:
        return device

    try:
        info = sd.query_devices(kind="input")
        idx = info.get("index", -1) if isinstance(info, dict) else getattr(info, "index", -1)
        if idx >= 0:
            return None
    except Exception:
        pass

    try:
        for i, dev in enumerate(sd.query_devices()):
            if dev["max_input_channels"] > 0:
                logger.info("No ALSA default input — falling back to device %d: %s", i, dev["name"])
                return i
    except Exception:
        pass

    return None


class AudioPlayback:
    """Plays an async iterator of int16 PCM chunks through the output device."""

    def __init__(
        self,
        sample_rate: int = PLAYBACK_SAMPLE_RATE,
        channels: int = PLAYBACK_CHANNELS,
        device: Optional[str | int] = None,
    ) -> None:
        self.sample_rate = sample_rate
        self.channels = channels
        self.device = device
        self._playing = False
        self._interrupt = asyncio.Event()

    async def play(
        self,
        chunks: AsyncIterator[bytes],
        input_sample_rate: int = PIPER_SAMPLE_RATE,
    ) -> None:
        """Play chunks. Returns when all chunks are played or interrupted.

        input_sample_rate: sample rate of the incoming PCM data.  Defaults to
        PIPER_SAMPLE_RATE (22050) so TTS output is resampled to the device
        rate automatically.  Pass self.sample_rate for pre-rendered audio.
        """
        import sounddevice as sd

        self._playing = True
        self._interrupt.clear()
        loop = asyncio.get_event_loop()
        write_queue: asyncio.Queue[Optional[bytes]] = asyncio.Queue(maxsize=20)

        resolved = _resolve_output_device(self.device)
        in_rate = input_sample_rate

        def _blocking_player() -> None:
            with sd.RawOutputStream(
                samplerate=self.sample_rate,
                channels=self.channels,
                dtype="int16",
                device=resolved,
            ) as stream:
                while True:
                    chunk = asyncio.run_coroutine_threadsafe(
                        write_queue.get(), loop
                    ).result(timeout=5)
                    if chunk is None:
                        break
                    samples = np.frombuffer(chunk, dtype=np.int16)
                    resampled = _resample(samples, in_rate, self.sample_rate)
                    stream.write(resampled.tobytes())

        player_future = loop.run_in_executor(None, _blocking_player)

        try:
            async for chunk in chunks:
                if self._interrupt.is_set():
                    break
                await write_queue.put(chunk)
        finally:
            await write_queue.put(None)
            try:
                await asyncio.wait_for(asyncio.shield(player_future), timeout=2.0)
            except asyncio.TimeoutError:
                pass
            self._playing = False

    def interrupt(self) -> None:
        """Signal playback to stop within ~100 ms."""
        self._interrupt.set()
        self._playing = False

    @property
    def is_playing(self) -> bool:
        return self._playing

    async def play_tone(self, frequency: float = 440.0, duration_s: float = 1.0) -> None:
        """Play a simple sine-wave test tone."""
        t = np.linspace(0, duration_s, int(self.sample_rate * duration_s), endpoint=False)
        wave = (np.sin(2 * np.pi * frequency * t) * 16000).astype(np.int16)

        async def _gen():
            chunk_size = self.sample_rate // 10
            for i in range(0, len(wave), chunk_size):
                yield wave[i : i + chunk_size].tobytes()

        await self.play(_gen(), input_sample_rate=self.sample_rate)

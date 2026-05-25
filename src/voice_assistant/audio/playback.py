"""Async audio playback with barge-in support."""

from __future__ import annotations

import asyncio
import logging
from typing import AsyncIterator, Optional

import numpy as np

logger = logging.getLogger(__name__)

PLAYBACK_SAMPLE_RATE = 22050
PLAYBACK_CHANNELS = 1


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

    async def play(self, chunks: AsyncIterator[bytes]) -> None:
        """Play chunks. Returns when all chunks are played or interrupted."""
        import sounddevice as sd

        self._playing = True
        self._interrupt.clear()
        loop = asyncio.get_event_loop()
        write_queue: asyncio.Queue[Optional[bytes]] = asyncio.Queue(maxsize=20)

        def _blocking_player() -> None:
            with sd.RawOutputStream(
                samplerate=self.sample_rate,
                channels=self.channels,
                dtype="int16",
                device=self.device,
            ) as stream:
                while True:
                    chunk = asyncio.run_coroutine_threadsafe(
                        write_queue.get(), loop
                    ).result(timeout=5)
                    if chunk is None:
                        break
                    stream.write(chunk)

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

        await self.play(_gen())

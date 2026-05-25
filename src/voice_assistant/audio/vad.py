"""Voice Activity Detection using Silero VAD (ONNX)."""

from __future__ import annotations

import logging
import time
from enum import Enum
from pathlib import Path
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

MODEL_PATH = Path(__file__).parent.parent.parent.parent / "data" / "models" / "silero_vad.onnx"
SILERO_HF_URL = "https://huggingface.co/onnx-community/silero-vad/resolve/main/onnx/model.onnx"
SAMPLE_RATE = 16000
CHUNK_SAMPLES = 512  # Silero requires 512 @ 16k


class VADEvent(str, Enum):
    NONE = "NONE"
    SPEECH_START = "SPEECH_START"
    SPEECH_END = "SPEECH_END"


class VADProcessor:
    """Stateful VAD processor. Feed int16 PCM frames; receive VADEvents."""

    def __init__(
        self,
        threshold: float = 0.5,
        min_speech_ms: int = 250,
        silence_timeout_ms: int = 800,
        sample_rate: int = SAMPLE_RATE,
    ) -> None:
        self.threshold = threshold
        self.min_speech_ms = min_speech_ms
        self.silence_timeout_ms = silence_timeout_ms
        self.sample_rate = sample_rate

        self._session = None
        self._h = np.zeros((2, 1, 64), dtype=np.float32)
        self._c = np.zeros((2, 1, 64), dtype=np.float32)

        self._in_speech = False
        self._speech_start_ms: Optional[float] = None
        self._last_speech_ms: Optional[float] = None
        self._buffer = np.array([], dtype=np.float32)
        self._now_ms: float = 0.0

    def _load(self) -> None:
        if self._session is not None:
            return
        if not MODEL_PATH.exists():
            self._download()
        import onnxruntime as ort

        opts = ort.SessionOptions()
        opts.inter_op_num_threads = 1
        opts.intra_op_num_threads = 1
        opts.log_severity_level = 3  # suppress INFO/WARNING from ORT (GPU probe noise)
        self._session = ort.InferenceSession(str(MODEL_PATH), sess_options=opts)
        logger.info("Silero VAD loaded from %s", MODEL_PATH)

    def _download(self) -> None:
        import urllib.request

        MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
        logger.info("Downloading Silero VAD model...")
        urllib.request.urlretrieve(SILERO_HF_URL, MODEL_PATH)
        logger.info("Silero VAD downloaded to %s", MODEL_PATH)

    def _infer_chunk(self, chunk: np.ndarray) -> float:
        self._load()
        x = chunk.astype(np.float32)[np.newaxis, :]
        sr = np.array(self.sample_rate, dtype=np.int64)
        out = self._session.run(
            None,
            {"input": x, "sr": sr, "h": self._h, "c": self._c},
        )
        prob, self._h, self._c = out[0], out[1], out[2]
        return float(prob[0, 0])

    def feed(self, pcm_int16: bytes) -> VADEvent:
        """Feed a frame of int16 PCM bytes; return the current VAD event."""
        samples = np.frombuffer(pcm_int16, dtype=np.int16).astype(np.float32) / 32768.0
        self._buffer = np.concatenate([self._buffer, samples])
        frame_ms = len(samples) / self.sample_rate * 1000
        self._now_ms += frame_ms

        event = VADEvent.NONE

        while len(self._buffer) >= CHUNK_SAMPLES:
            chunk = self._buffer[:CHUNK_SAMPLES]
            self._buffer = self._buffer[CHUNK_SAMPLES:]
            prob = self._infer_chunk(chunk)

            if prob >= self.threshold:
                self._last_speech_ms = self._now_ms
                if not self._in_speech:
                    self._in_speech = True
                    self._speech_start_ms = self._now_ms
                    event = VADEvent.SPEECH_START
            else:
                if self._in_speech and self._last_speech_ms is not None:
                    elapsed_silence = self._now_ms - self._last_speech_ms
                    if elapsed_silence >= self.silence_timeout_ms:
                        speech_duration = self._now_ms - (self._speech_start_ms or 0)
                        self._in_speech = False
                        if speech_duration >= self.min_speech_ms:
                            event = VADEvent.SPEECH_END
                        else:
                            logger.debug("Dropped short utterance (%.0f ms)", speech_duration)

        return event

    def reset(self) -> None:
        self._in_speech = False
        self._speech_start_ms = None
        self._last_speech_ms = None
        self._buffer = np.array([], dtype=np.float32)
        self._h = np.zeros((2, 1, 64), dtype=np.float32)
        self._c = np.zeros((2, 1, 64), dtype=np.float32)

    @property
    def in_speech(self) -> bool:
        return self._in_speech

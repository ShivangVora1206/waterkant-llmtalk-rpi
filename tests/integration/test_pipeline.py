"""Integration tests — full pipeline with fake audio/STT/LLM/TTS backends."""

from __future__ import annotations

import asyncio
import numpy as np
import pytest
from pathlib import Path

from voice_assistant.stt.base import STTBackend, Transcript
from voice_assistant.llm.base import LLMBackend, ModelInfo, PullProgress
from voice_assistant.tts.base import TTSBackend, VoiceInfo
from voice_assistant.audio.capture import AudioCapture
from voice_assistant.audio.playback import AudioPlayback
from voice_assistant.audio.vad import VADProcessor
from voice_assistant.config import ConfigStore
from voice_assistant.conversation import ConversationStore
from voice_assistant.orchestrator import Orchestrator
from voice_assistant.state import PipelineState, StateMachine
from voice_assistant.utils.events import EventBus


# ---------------------------------------------------------------------------
# Fake backends
# ---------------------------------------------------------------------------

class FakeSTT(STTBackend):
    async def transcribe(self, pcm, sample_rate) -> Transcript:
        return Transcript(text="What is two plus two?", latency_ms=50.0)

    def available_models(self): return ["fake"]
    async def load(self, model_name=None): pass
    async def unload(self): pass


class FakeLLM(LLMBackend):
    async def stream(self, messages, params):
        for tok in ["Four.", " That", " is", " the", " answer."]:
            yield tok
            await asyncio.sleep(0)

    async def list_models(self): return [ModelInfo(name="fake")]
    async def pull_model(self, name): yield PullProgress(status="done")
    async def delete_model(self, name): pass
    async def model_info(self, name): return ModelInfo(name="fake")


class FakeTTS(TTSBackend):
    async def synthesise(self, text, params):
        silence = np.zeros(2205, dtype=np.int16).tobytes()
        yield silence

    def available_voices(self): return [VoiceInfo("fake", "en", 22050, 0.0)]
    async def load_voice(self, name): pass
    async def unload(self): pass


class FakeCapture:
    def __init__(self, frames: list[bytes]) -> None:
        self._frames = frames
        self.sample_rate = 16000
        self.xrun_count = 0

    async def start(self): pass
    async def stop(self): pass

    def __aiter__(self): return self
    async def __anext__(self):
        if not self._frames:
            await asyncio.sleep(3600)
        return self._frames.pop(0)


class FakePlayback:
    async def play(self, chunks):
        async for _ in chunks:
            pass
    def interrupt(self): pass
    def play_tone(self, *a, **kw): pass
    @property
    def is_playing(self): return False


# ---------------------------------------------------------------------------
# Test
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@pytest.mark.integration
async def test_full_pipeline_utterance(tmp_path: Path):
    """Speak a fake utterance, confirm stt.final and tts.ended events fire."""
    bus = EventBus()
    sm = StateMachine(event_bus=bus)

    cfg_store = ConfigStore(
        default_path=Path("configs/default.yaml"),
        runtime_path=tmp_path / "runtime.json",
    )

    # Build 1 s of silence followed by "speech" (just non-zero audio to pass VAD min)
    silence = np.zeros(320, dtype=np.int16).tobytes()  # 20ms frame
    speech_frames = [silence] * 100  # won't trigger real VAD; we'll bypass

    capture = FakeCapture(speech_frames)
    playback = FakePlayback()
    vad = VADProcessor(threshold=0.5, min_speech_ms=100, silence_timeout_ms=200)

    conv = ConversationStore(db_path=tmp_path / "conv.sqlite")
    await conv.open()

    events_received = []
    bus.subscribe("stt.final", lambda t, p: events_received.append(("stt.final", p)))
    bus.subscribe("tts.ended", lambda t, p: events_received.append(("tts.ended", p)))

    orch = Orchestrator(
        config_store=cfg_store,
        event_bus=bus,
        state_machine=sm,
        capture=capture,
        playback=playback,
        vad=vad,
        stt_backend=FakeSTT(),
        llm_backend=FakeLLM(),
        tts_backend=FakeTTS(),
        conversation=conv,
    )

    # Directly exercise _handle_utterance instead of full loop
    orch._stt._buffer = [silence * 50]  # 1 s of audio
    await orch._safe_transition(PipelineState.LISTENING)
    await orch._handle_utterance()

    await conv.close()

    types = [e[0] for e in events_received]
    assert "stt.final" in types
    assert "tts.ended" in types

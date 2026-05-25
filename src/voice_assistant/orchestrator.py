"""Pipeline orchestrator — wires mic → VAD → STT → LLM → TTS → speaker."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Optional

from .audio.capture import AudioCapture
from .audio.playback import AudioPlayback
from .audio.vad import VADEvent, VADProcessor
from .config import AppConfig, ConfigStore
from .conversation import ConversationStore
from .llm.base import LLMBackend
from .llm.ollama import OllamaError
from .state import InvalidTransitionError, PipelineState, StateMachine
from .stt.base import STTBackend
from .stt.service import STTService
from .tts.base import TTSBackend
from .tts.service import TTSService
from .utils.events import EventBus

logger = logging.getLogger(__name__)


class Orchestrator:
    def __init__(
        self,
        config_store: ConfigStore,
        event_bus: EventBus,
        state_machine: StateMachine,
        capture: AudioCapture,
        playback: AudioPlayback,
        vad: VADProcessor,
        stt_backend: STTBackend,
        llm_backend: LLMBackend,
        tts_backend: TTSBackend,
        conversation: ConversationStore,
    ) -> None:
        self._cfg = config_store
        self._bus = event_bus
        self._sm = state_machine
        self._capture = capture
        self._playback = playback
        self._vad = vad
        self._stt = STTService(
            backend=stt_backend,
            vad=vad,
            event_bus=event_bus,
        )
        self._llm = llm_backend
        self._tts = TTSService(backend=tts_backend, playback=playback, event_bus=event_bus)
        self._conv = conversation

        self._ptt_active = False
        self._paused = False
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._llm_task: Optional[asyncio.Task] = None

    # ------------------------------------------------------------------
    async def start(self) -> None:
        self._running = True
        await self._capture.start()
        self._task = asyncio.create_task(self._loop(), name="orchestrator_loop")
        logger.info("Orchestrator started")

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
        await self._capture.stop()
        logger.info("Orchestrator stopped")

    # ------------------------------------------------------------------
    async def _loop(self) -> None:
        cfg = self._cfg.get()
        await self._safe_transition(PipelineState.LISTENING)

        async for frame in self._capture:
            if not self._running:
                break
            if self._paused:
                continue

            state = self._sm.state
            if state not in (PipelineState.LISTENING, PipelineState.SPEAKING):
                continue

            vad_event = self._vad.feed(frame)

            if vad_event == VADEvent.SPEECH_START:
                if state == PipelineState.SPEAKING:
                    # barge-in
                    cfg = self._cfg.get()
                    self._tts.interrupt()
                    if self._llm_task:
                        self._llm_task.cancel()
                    await self._safe_transition(PipelineState.LISTENING)
                self._stt.start_capture()

            if self._vad.in_speech or vad_event == VADEvent.SPEECH_START:
                self._stt._buffer.append(frame)

            if vad_event == VADEvent.SPEECH_END:
                await self._handle_utterance()

    # ------------------------------------------------------------------
    async def _handle_utterance(self) -> None:
        cfg = self._cfg.get()
        audio = b"".join(self._stt._buffer)
        self._stt._buffer.clear()

        if not audio:
            return

        # STT
        try:
            await self._safe_transition(PipelineState.TRANSCRIBING)
            t_stt_start = time.monotonic()
            transcript = await self._stt._backend.transcribe(audio, cfg.audio.sample_rate)
            stt_latency_ms = (time.monotonic() - t_stt_start) * 1000
        except Exception as exc:
            await self._publish_error("stt", str(exc))
            await self._recover()
            return

        text = transcript.text.strip()
        if not text:
            await self._safe_transition(PipelineState.LISTENING)
            return

        await self._bus.publish("stt.final", {"text": text, "latency_ms": stt_latency_ms})
        await self._conv.add_turn("user", text, stt_latency_ms=stt_latency_ms)

        # LLM
        try:
            await self._safe_transition(PipelineState.THINKING)
            messages = await self._conv.build_messages(
                cfg.llm.system_prompt, cfg.conversation.history_turns
            )
            llm_params = {
                "model": cfg.llm.model,
                "temperature": cfg.llm.temperature,
                "top_p": cfg.llm.top_p,
                "top_k": cfg.llm.top_k,
                "num_ctx": cfg.llm.num_ctx,
                "num_predict": cfg.llm.num_predict,
                "repeat_penalty": cfg.llm.repeat_penalty,
                "keep_alive": cfg.llm.keep_alive,
            }
            t_llm_start = time.monotonic()
            token_stream = self._llm.stream(messages, llm_params)
        except Exception as exc:
            await self._publish_error("llm", str(exc))
            await self._recover()
            return

        # TTS
        try:
            await self._safe_transition(PipelineState.SPEAKING)
            full_response = []

            async def _collecting_stream():
                async for tok in token_stream:
                    full_response.append(tok)
                    yield tok

            self._llm_task = asyncio.current_task()
            await self._tts.speak_stream(_collecting_stream())

            llm_latency_ms = (time.monotonic() - t_llm_start) * 1000
            response_text = "".join(full_response)
            if response_text.strip():
                await self._conv.add_turn("assistant", response_text, llm_latency_ms=llm_latency_ms)

        except asyncio.CancelledError:
            logger.info("LLM/TTS cancelled (barge-in or stop)")
        except (OllamaError, Exception) as exc:
            await self._publish_error("tts_or_llm", str(exc))
        finally:
            self._llm_task = None

        await self._recover()

    # ------------------------------------------------------------------
    async def _safe_transition(self, state: PipelineState) -> None:
        try:
            await self._sm.transition(state)
        except InvalidTransitionError as exc:
            logger.warning("Transition skipped: %s", exc)

    async def _recover(self) -> None:
        try:
            await self._sm.transition(PipelineState.IDLE)
            await self._sm.transition(PipelineState.LISTENING)
        except InvalidTransitionError:
            await self._sm.force(PipelineState.LISTENING)

    async def _publish_error(self, component: str, message: str) -> None:
        logger.error("[%s] %s", component, message)
        await self._bus.publish("error", {"component": component, "message": message})
        await self._sm.force(PipelineState.ERROR)

    # ------------------------------------------------------------------
    # External control API
    async def ptt_start(self) -> None:
        """Begin push-to-talk capture."""
        self._ptt_active = True
        self._vad.reset()
        self._stt.start_capture()
        await self._safe_transition(PipelineState.LISTENING)

    async def ptt_stop(self) -> None:
        """End push-to-talk and process."""
        self._ptt_active = False
        await self._handle_utterance()

    async def pause(self) -> None:
        self._paused = True
        await self._safe_transition(PipelineState.PAUSED)

    async def resume(self) -> None:
        self._paused = False
        await self._safe_transition(PipelineState.IDLE)
        await self._sm.transition(PipelineState.LISTENING)

    async def new_conversation(self) -> str:
        return await self._conv.new_conversation()

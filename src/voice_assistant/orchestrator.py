"""Pipeline orchestrator — wires mic → VAD → STT → LLM → TTS → speaker."""

from __future__ import annotations

import asyncio
import logging
import sys
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
        self._stt_backend = stt_backend
        self._llm = llm_backend
        self._tts = TTSService(backend=tts_backend, playback=playback, event_bus=event_bus)
        self._conv = conversation

        self._ptt_active = False
        self._paused = False
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._llm_task: Optional[asyncio.Task] = None
        # Shared speech accumulation buffer (written by loop, read by ptt_stop)
        self._speech_buffer: list[bytes] = []

    # ------------------------------------------------------------------
    async def start(self) -> None:
        self._running = True
        # Preload VAD ONNX model in a thread so the first frame doesn't block
        # the event loop (model init takes 2-5 s on Pi 5).
        ev_loop = asyncio.get_event_loop()
        await ev_loop.run_in_executor(None, self._vad._load)
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
        try:
            await self._loop_body()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            # Use print so the error is always visible even if logging isn't configured
            print(f"[ORCHESTRATOR CRASH] {exc}", file=sys.stderr, flush=True)
            logger.error("Orchestrator loop crashed: %s", exc, exc_info=True)
            await self._sm.force(PipelineState.ERROR)
            await self._bus.publish("error", {"component": "orchestrator_loop", "message": str(exc)})

    async def _loop_body(self) -> None:
        logger.info("Orchestrator loop starting")
        print("[ORCHESTRATOR] loop starting", file=sys.stderr, flush=True)
        await self._safe_transition(PipelineState.LISTENING)
        logger.info("Orchestrator loop listening")
        print("[ORCHESTRATOR] loop listening", file=sys.stderr, flush=True)

        async for frame in self._capture:
            if not self._running:
                break
            if self._paused:
                continue

            # In PTT mode just accumulate every frame — no VAD gating.
            if self._ptt_active:
                self._speech_buffer.append(frame)
                continue

            state = self._sm.state
            if state not in (PipelineState.LISTENING, PipelineState.SPEAKING):
                continue

            vad_event = self._vad.feed(frame)

            if vad_event == VADEvent.SPEECH_START:
                if state == PipelineState.SPEAKING:
                    # barge-in: stop current response
                    self._tts.interrupt()
                    if self._llm_task:
                        self._llm_task.cancel()
                    await self._safe_transition(PipelineState.LISTENING)
                # Start a fresh accumulation buffer
                self._speech_buffer = [frame]
                logger.debug("VAD: speech start")

            elif self._vad.in_speech:
                self._speech_buffer.append(frame)

            elif vad_event == VADEvent.SPEECH_END:
                logger.debug("VAD: speech end (%d frames)", len(self._speech_buffer))
                if self._speech_buffer:
                    buf = self._speech_buffer
                    self._speech_buffer = []
                    await self._handle_utterance(buf)

        logger.info("Orchestrator loop exited")

    # ------------------------------------------------------------------
    async def _handle_utterance(self, buffer: list[bytes]) -> None:
        cfg = self._cfg.get()
        audio = b"".join(buffer)
        if not audio:
            logger.debug("_handle_utterance: empty buffer, skipping")
            return

        duration_ms = len(audio) / 2 / cfg.audio.sample_rate * 1000
        logger.info("Utterance: %.0f ms of audio → STT", duration_ms)

        # STT
        try:
            await self._safe_transition(PipelineState.TRANSCRIBING)
            t0 = time.monotonic()
            transcript = await self._stt_backend.transcribe(audio, cfg.audio.sample_rate)
            stt_ms = (time.monotonic() - t0) * 1000
        except Exception as exc:
            logger.error("STT error: %s", exc, exc_info=True)
            await self._publish_error("stt", str(exc))
            await self._recover()
            return

        text = transcript.text.strip()
        logger.info("STT result: %r (%.0f ms)", text, stt_ms)
        if not text:
            await self._safe_transition(PipelineState.LISTENING)
            return

        await self._conv.add_turn("user", text, stt_latency_ms=stt_ms)
        await self._bus.publish("stt.final", {"text": text, "latency_ms": stt_ms})
        await self._bus.publish("conversation.updated", {"role": "user"})

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
            t_llm = time.monotonic()
            token_stream = self._llm.stream(messages, llm_params)
        except Exception as exc:
            logger.error("LLM setup error: %s", exc, exc_info=True)
            await self._publish_error("llm", str(exc))
            await self._recover()
            return

        # TTS (streams LLM tokens → sentences → Piper → speaker)
        full_response: list[str] = []
        try:
            await self._safe_transition(PipelineState.SPEAKING)

            async def _collecting_stream():
                async for tok in token_stream:
                    full_response.append(tok)
                    yield tok

            self._llm_task = asyncio.current_task()
            await self._tts.speak_stream(_collecting_stream())

        except asyncio.CancelledError:
            logger.info("LLM/TTS cancelled (barge-in or stop)")
        except (OllamaError, Exception) as exc:
            logger.error("TTS/LLM error: %s", exc, exc_info=True)
            await self._publish_error("tts_or_llm", str(exc))
        finally:
            self._llm_task = None
            llm_ms = (time.monotonic() - t_llm) * 1000
            response_text = "".join(full_response)
            logger.info("LLM+TTS done (%.0f ms): %r", llm_ms, response_text[:80])
            if response_text.strip():
                await self._conv.add_turn("assistant", response_text, llm_latency_ms=llm_ms)
                await self._bus.publish("conversation.updated", {"role": "assistant"})

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
        """Begin push-to-talk recording."""
        if self._sm.state == PipelineState.SPEAKING:
            self._tts.interrupt()
            if self._llm_task:
                self._llm_task.cancel()
        self._speech_buffer = []
        self._vad.reset()
        self._ptt_active = True
        logger.info("PTT started")

    async def ptt_stop(self) -> None:
        """End push-to-talk and process the recorded audio."""
        self._ptt_active = False
        buf = self._speech_buffer
        self._speech_buffer = []
        logger.info("PTT stopped: %d frames buffered", len(buf))
        if buf:
            await self._handle_utterance(buf)
        else:
            logger.warning("PTT stopped with empty buffer — mic capture may have failed")

    async def pause(self) -> None:
        self._paused = True
        await self._safe_transition(PipelineState.PAUSED)

    async def resume(self) -> None:
        self._paused = False
        await self._safe_transition(PipelineState.IDLE)
        await self._sm.transition(PipelineState.LISTENING)

    async def new_conversation(self) -> str:
        return await self._conv.new_conversation()

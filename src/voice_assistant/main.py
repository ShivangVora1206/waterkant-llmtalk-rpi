"""FastAPI application entrypoint."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from .api.routes_audio import router as audio_router
from .api.routes_config import router as config_router
from .api.routes_conversation import router as conv_router
from .api.routes_models import router as models_router
from .api.routes_system import router as system_router
from .api.ws import WSManager
from .audio.capture import AudioCapture
from .audio.devices import pick_default_input, pick_default_output
from .audio.playback import AudioPlayback
from .audio.vad import VADProcessor
from .config import get_config_store
from .conversation import ConversationStore
from .llm.ollama import OllamaBackend
from .orchestrator import Orchestrator
from .state import StateMachine
from .stt.faster_whisper import FasterWhisperBackend
from .tts.piper import PiperBackend
from .utils.events import get_event_bus
from .utils.health import HealthMonitor
from .utils.logging import configure_logging

FRONTEND_DIST = Path(__file__).parent.parent.parent / "frontend" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI):
    log_level = os.environ.get("LOG_LEVEL", "INFO")
    configure_logging(log_level)

    cfg_store = get_config_store()
    cfg = cfg_store.get()
    bus = get_event_bus()

    # State machine
    sm = StateMachine(event_bus=bus)

    # Audio devices
    input_dev = cfg.audio.input_device or pick_default_input()
    output_dev = cfg.audio.output_device or pick_default_output()

    capture = AudioCapture(
        sample_rate=cfg.audio.sample_rate,
        channels=cfg.audio.channels,
        device=input_dev,
        event_bus=bus,
    )
    playback = AudioPlayback(device=output_dev)
    vad = VADProcessor(
        threshold=cfg.vad.threshold,
        min_speech_ms=cfg.vad.min_speech_ms,
        silence_timeout_ms=cfg.vad.silence_timeout_ms,
    )

    # STT
    stt_backend = FasterWhisperBackend(
        model_name=cfg.stt.model,
        compute_type=cfg.stt.compute_type,
        language=cfg.stt.language,
        beam_size=cfg.stt.beam_size,
    )

    # LLM
    llm_backend = OllamaBackend(base_url=cfg.llm.base_url, event_bus=bus)

    # TTS
    tts_backend = PiperBackend(
        voice=cfg.tts.voice,
        speed=cfg.tts.speed,
        noise_scale=cfg.tts.noise_scale,
        length_scale=cfg.tts.length_scale,
    )

    # Conversation
    conversation = ConversationStore()
    await conversation.open()

    # Orchestrator
    orchestrator = Orchestrator(
        config_store=cfg_store,
        event_bus=bus,
        state_machine=sm,
        capture=capture,
        playback=playback,
        vad=vad,
        stt_backend=stt_backend,
        llm_backend=llm_backend,
        tts_backend=tts_backend,
        conversation=conversation,
    )

    # WS manager
    ws_manager = WSManager(bus, sm)
    await ws_manager.start()

    # Health monitor
    health_monitor = HealthMonitor(bus)
    await health_monitor.start()

    # Attach to app state for route access
    app.state.config_store = cfg_store
    app.state.event_bus = bus
    app.state.state_machine = sm
    app.state.capture = capture
    app.state.playback = playback
    app.state.orchestrator = orchestrator
    app.state.stt_backend = stt_backend
    app.state.llm_backend = llm_backend
    app.state.tts_backend = tts_backend
    app.state.conversation = conversation
    app.state.ws_manager = ws_manager

    # Start orchestrator (begins listening)
    await orchestrator.start()

    yield

    # Shutdown
    await orchestrator.stop()
    await conversation.close()
    await health_monitor.stop()
    if hasattr(llm_backend, "close"):
        await llm_backend.close()


def create_app() -> FastAPI:
    app = FastAPI(
        title="Voice Assistant",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # restrict in production
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # REST routes
    app.include_router(config_router)
    app.include_router(models_router)
    app.include_router(conv_router)
    app.include_router(audio_router)
    app.include_router(system_router)

    # WebSocket
    @app.websocket("/ws/state")
    async def ws_state(websocket: WebSocket):
        await websocket.app.state.ws_manager.connect(websocket)

    # Health check
    @app.get("/healthz")
    async def healthz():
        return {"status": "ok"}

    # Serve React frontend
    if FRONTEND_DIST.exists():
        app.mount("/", StaticFiles(directory=str(FRONTEND_DIST), html=True), name="frontend")
    else:
        @app.get("/")
        async def root():
            return JSONResponse(
                {"message": "Voice Assistant API running. Build the frontend to see the dashboard."},
                status_code=200,
            )

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    cfg = get_config_store().get()
    uvicorn.run(
        "voice_assistant.main:app",
        host=cfg.server.host,
        port=cfg.server.port,
        reload=False,
    )

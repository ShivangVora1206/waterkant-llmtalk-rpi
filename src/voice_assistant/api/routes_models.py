"""Model management routes."""

from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from ..llm.ollama import OllamaError
from ..stt.faster_whisper import AVAILABLE_MODELS as WHISPER_MODELS
from ..tts.piper import KNOWN_VOICES

router = APIRouter(prefix="/api/models", tags=["models"])


def _get_llm(request: Request):
    return request.app.state.llm_backend


def _get_tts(request: Request):
    return request.app.state.tts_backend


# ------------------------------------------------------------------
# LLM models
# ------------------------------------------------------------------
@router.get("/llm")
async def list_llm_models(request: Request):
    try:
        models = await _get_llm(request).list_models()
        return [m.__dict__ for m in models]
    except OllamaError as exc:
        raise HTTPException(status_code=503, detail=str(exc))


@router.post("/llm/pull")
async def pull_llm_model(request: Request):
    body = await request.json()
    name = body.get("name")
    if not name:
        raise HTTPException(status_code=400, detail="name required")

    async def _stream():
        try:
            async for progress in _get_llm(request).pull_model(name):
                yield json.dumps(progress.__dict__) + "\n"
        except OllamaError as exc:
            yield json.dumps({"error": str(exc)}) + "\n"

    return StreamingResponse(_stream(), media_type="application/x-ndjson")


@router.delete("/llm/{name:path}")
async def delete_llm_model(name: str, request: Request):
    try:
        await _get_llm(request).delete_model(name)
        return {"deleted": name}
    except OllamaError as exc:
        raise HTTPException(status_code=503, detail=str(exc))


# ------------------------------------------------------------------
# STT models
# ------------------------------------------------------------------
@router.get("/stt")
async def list_stt_models(request: Request):
    from ..stt.faster_whisper import FasterWhisperBackend
    backend: FasterWhisperBackend = request.app.state.stt_backend
    downloaded = backend.downloaded_models() if hasattr(backend, "downloaded_models") else []
    return [
        {"name": m, "downloaded": m in downloaded}
        for m in WHISPER_MODELS
    ]


@router.post("/stt/download")
async def download_stt_model(request: Request):
    body = await request.json()
    name = body.get("name")
    if not name:
        raise HTTPException(status_code=400, detail="name required")
    from ..stt.faster_whisper import FasterWhisperBackend
    backend: FasterWhisperBackend = request.app.state.stt_backend
    # Trigger download by loading the model
    await backend.load(name)
    return {"downloaded": name}


# ------------------------------------------------------------------
# TTS voices
# ------------------------------------------------------------------
@router.get("/tts")
async def list_tts_voices(request: Request):
    from ..tts.piper import PiperBackend
    backend: PiperBackend = request.app.state.tts_backend
    downloaded = backend.downloaded_voices() if hasattr(backend, "downloaded_voices") else []
    voices = []
    for name, meta in KNOWN_VOICES.items():
        voices.append({
            "name": name,
            "language": meta["language"],
            "sample_rate": meta["sample_rate"],
            "size_mb": meta["size_mb"],
            "downloaded": name in downloaded,
        })
    return voices


@router.post("/tts/download")
async def download_tts_voice(request: Request):
    body = await request.json()
    name = body.get("name")
    if not name:
        raise HTTPException(status_code=400, detail="name required")
    from ..tts.piper import PiperBackend
    backend: PiperBackend = request.app.state.tts_backend
    await backend.download_voice(name)
    return {"downloaded": name}

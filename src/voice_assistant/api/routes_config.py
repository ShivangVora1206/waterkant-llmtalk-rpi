"""Config REST routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/api/config", tags=["config"])


def _get_store(request: Request):
    return request.app.state.config_store


@router.get("")
async def get_config(request: Request):
    store = _get_store(request)
    return store.get().model_dump()


@router.patch("")
async def patch_config(request: Request):
    store = _get_store(request)
    body = await request.json()
    try:
        new_cfg = await store.update(body)
        return new_cfg.model_dump()
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.patch("/llm")
async def patch_llm(request: Request):
    body = await request.json()
    return await _patch_section(request, "llm", body)


@router.patch("/stt")
async def patch_stt(request: Request):
    body = await request.json()
    return await _patch_section(request, "stt", body)


@router.patch("/tts")
async def patch_tts(request: Request):
    body = await request.json()
    return await _patch_section(request, "tts", body)


@router.patch("/audio")
async def patch_audio(request: Request):
    body = await request.json()
    return await _patch_section(request, "audio", body)


@router.patch("/vad")
async def patch_vad(request: Request):
    body = await request.json()
    return await _patch_section(request, "vad", body)


async def _patch_section(request: Request, section: str, body: dict):
    store = _get_store(request)
    try:
        new_cfg = await store.update({section: body})
        return new_cfg.model_dump()
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc))

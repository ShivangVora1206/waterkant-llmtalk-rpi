"""Audio control and device routes."""

from __future__ import annotations

import asyncio
import io
import struct
import wave

import numpy as np
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response

from ..audio.devices import list_devices

router = APIRouter(tags=["audio"])


def _orchestrator(request: Request):
    return request.app.state.orchestrator


def _playback(request: Request):
    return request.app.state.playback


def _capture(request: Request):
    return request.app.state.capture


# ------------------------------------------------------------------
@router.get("/api/audio/devices")
async def get_devices():
    return list_devices()


@router.post("/api/audio/test/speaker")
async def test_speaker(request: Request):
    body = await request.json() if request.headers.get("content-length", "0") != "0" else {}
    freq = float(body.get("frequency", 440))
    pb = _playback(request)
    asyncio.create_task(pb.play_tone(freq, 1.0))
    return {"status": "playing"}


@router.post("/api/audio/test/speaker/voice")
async def test_speaker_voice(request: Request):
    """Play a short TTS sample for the currently-selected (or specified) voice."""
    body = await request.json() if request.headers.get("content-length", "0") != "0" else {}
    text = body.get("text", "Hello! This is a voice preview.")
    voice = body.get("voice")
    tts = request.app.state.tts_backend
    params = {}
    if voice:
        params["voice"] = voice
    pb = _playback(request)

    async def _play():
        await pb.play(tts.synthesise(text, params))

    asyncio.create_task(_play())
    return {"status": "playing", "text": text}


@router.post("/api/audio/test/mic")
async def test_mic(request: Request):
    """Record 3 s from the mic and return RMS dBFS + WAV."""
    cap = _capture(request)
    sample_rate = cap.sample_rate
    duration_s = 3
    frames = []
    total_samples = sample_rate * duration_s

    collected = 0
    async for frame in cap:
        frames.append(frame)
        collected += len(frame) // 2
        if collected >= total_samples:
            break

    raw = b"".join(frames)
    audio = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    rms = float(np.sqrt(np.mean(audio**2))) if len(audio) > 0 else 0.0
    import math
    dbfs = 20 * math.log10(max(rms, 1e-9))

    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(raw)
    wav_bytes = buf.getvalue()

    return {
        "rms_dbfs": round(dbfs, 1),
        "duration_s": duration_s,
        "wav_size_bytes": len(wav_bytes),
    }


# ------------------------------------------------------------------
@router.post("/api/control/ptt/start")
async def ptt_start(request: Request):
    await _orchestrator(request).ptt_start()
    return {"status": "ptt_started"}


@router.post("/api/control/ptt/stop")
async def ptt_stop(request: Request):
    await _orchestrator(request).ptt_stop()
    return {"status": "ptt_stopped"}


@router.post("/api/control/pause")
async def pause(request: Request):
    await _orchestrator(request).pause()
    return {"status": "paused"}


@router.post("/api/control/resume")
async def resume(request: Request):
    await _orchestrator(request).resume()
    return {"status": "resumed"}


@router.post("/api/control/new_conversation")
async def new_conversation(request: Request):
    cid = await _orchestrator(request).new_conversation()
    return {"id": cid}

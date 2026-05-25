"""Conversation REST routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, Response

router = APIRouter(prefix="/api/conversations", tags=["conversations"])


def _store(request: Request):
    return request.app.state.conversation


@router.get("")
async def list_convs(request: Request, limit: int = 50):
    return await _store(request).list_conversations(limit)


@router.get("/{cid}")
async def get_conv(cid: str, request: Request):
    data = await _store(request).get_conversation(cid)
    if not data:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return data


@router.post("")
async def new_conv(request: Request):
    cid = await _store(request).new_conversation()
    return {"id": cid}


@router.delete("/{cid}")
async def delete_conv(cid: str, request: Request):
    await _store(request).delete_conversation(cid)
    return {"deleted": cid}


@router.post("/{cid}/export")
async def export_conv(cid: str, request: Request):
    data = await _store(request).export_conversation(cid)
    if data is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return Response(
        content=data,
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="conversation-{cid}.json"'},
    )

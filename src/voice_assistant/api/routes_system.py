"""System health and info routes."""

from __future__ import annotations

from fastapi import APIRouter, Request

from ..utils.health import get_health_snapshot

router = APIRouter(prefix="/api/system", tags=["system"])


@router.get("/health")
async def system_health():
    return get_health_snapshot()

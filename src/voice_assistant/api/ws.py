"""WebSocket /ws/state — real-time event fan-out."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any, Set

from fastapi import WebSocket, WebSocketDisconnect

from ..state import StateMachine
from ..utils.events import EventBus

logger = logging.getLogger(__name__)

HEARTBEAT_INTERVAL = 15  # seconds


class WSManager:
    def __init__(self, event_bus: EventBus, state_machine: StateMachine) -> None:
        self._bus = event_bus
        self._sm = state_machine
        self._clients: Set[WebSocket] = set()
        self._queues: dict[WebSocket, asyncio.Queue] = {}
        self._started = False

    async def start(self) -> None:
        if self._started:
            return
        self._started = True
        topics = [
            "state.changed",
            "stt.partial",
            "stt.final",
            "llm.token",
            "llm.final",
            "tts.started",
            "tts.ended",
            "audio.level",
            "system.health",
            "config.changed",
            "error",
        ]
        for topic in topics:
            self._bus.subscribe(topic, self._on_event)

    async def _on_event(self, topic: str, payload: Any) -> None:
        msg = json.dumps({"type": topic, "data": payload})
        dead = []
        for ws, q in list(self._queues.items()):
            try:
                q.put_nowait(msg)
            except asyncio.QueueFull:
                dead.append(ws)
        for ws in dead:
            await self._remove(ws)

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        q: asyncio.Queue[str] = asyncio.Queue(maxsize=500)
        self._clients.add(ws)
        self._queues[ws] = q

        # Send current state snapshot on connect
        snapshot = json.dumps({
            "type": "state.snapshot",
            "data": {"state": self._sm.state.value},
        })
        await ws.send_text(snapshot)

        sender_task = asyncio.create_task(self._sender(ws, q))
        heartbeat_task = asyncio.create_task(self._heartbeat(ws))

        try:
            while True:
                await ws.receive_text()  # keeps connection alive; ignore client messages
        except WebSocketDisconnect:
            pass
        except Exception as exc:
            logger.debug("WS disconnected: %s", exc)
        finally:
            sender_task.cancel()
            heartbeat_task.cancel()
            await self._remove(ws)

    async def _sender(self, ws: WebSocket, q: asyncio.Queue) -> None:
        while True:
            msg = await q.get()
            try:
                await ws.send_text(msg)
            except Exception:
                break

    async def _heartbeat(self, ws: WebSocket) -> None:
        while True:
            await asyncio.sleep(HEARTBEAT_INTERVAL)
            try:
                await ws.send_text(json.dumps({"type": "ping", "ts": time.time()}))
            except Exception:
                break

    async def _remove(self, ws: WebSocket) -> None:
        self._clients.discard(ws)
        self._queues.pop(ws, None)

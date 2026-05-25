"""Conversation history management with SQLite persistence."""

from __future__ import annotations

import json
import logging
import time
import uuid
from pathlib import Path
from typing import Optional

import aiosqlite

logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent.parent.parent / "data" / "conversations.sqlite"

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT
);

CREATE TABLE IF NOT EXISTS conversations (
    id TEXT PRIMARY KEY,
    created_at REAL,
    updated_at REAL
);

CREATE TABLE IF NOT EXISTS turns (
    id TEXT PRIMARY KEY,
    conversation_id TEXT REFERENCES conversations(id) ON DELETE CASCADE,
    role TEXT,
    text TEXT,
    created_at REAL,
    audio_duration_ms REAL DEFAULT 0,
    stt_latency_ms REAL DEFAULT 0,
    llm_latency_ms REAL DEFAULT 0,
    tts_latency_ms REAL DEFAULT 0
);
"""


class ConversationStore:
    def __init__(self, db_path: Path = DB_PATH) -> None:
        self._db_path = db_path
        self._db: Optional[aiosqlite.Connection] = None
        self._current_id: Optional[str] = None

    async def open(self) -> None:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._db = await aiosqlite.connect(str(self._db_path))
        self._db.row_factory = aiosqlite.Row
        await self._db.executescript(SCHEMA)
        await self._db.execute("PRAGMA journal_mode=WAL")
        await self._db.commit()
        # Resume or start a conversation
        await self._ensure_conversation()

    async def close(self) -> None:
        if self._db:
            await self._db.close()

    # ------------------------------------------------------------------
    async def _ensure_conversation(self) -> None:
        if self._current_id is None:
            await self.new_conversation()

    async def new_conversation(self) -> str:
        cid = str(uuid.uuid4())
        now = time.time()
        await self._db.execute(
            "INSERT INTO conversations (id, created_at, updated_at) VALUES (?, ?, ?)",
            (cid, now, now),
        )
        await self._db.commit()
        self._current_id = cid
        return cid

    async def reset(self) -> str:
        return await self.new_conversation()

    @property
    def current_id(self) -> Optional[str]:
        return self._current_id

    # ------------------------------------------------------------------
    async def add_turn(
        self,
        role: str,
        text: str,
        audio_duration_ms: float = 0,
        stt_latency_ms: float = 0,
        llm_latency_ms: float = 0,
        tts_latency_ms: float = 0,
    ) -> str:
        if not self._current_id:
            await self.new_conversation()
        tid = str(uuid.uuid4())
        now = time.time()
        await self._db.execute(
            """INSERT INTO turns
               (id, conversation_id, role, text, created_at, audio_duration_ms,
                stt_latency_ms, llm_latency_ms, tts_latency_ms)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                tid,
                self._current_id,
                role,
                text,
                now,
                audio_duration_ms,
                stt_latency_ms,
                llm_latency_ms,
                tts_latency_ms,
            ),
        )
        await self._db.execute(
            "UPDATE conversations SET updated_at=? WHERE id=?",
            (now, self._current_id),
        )
        await self._db.commit()
        return tid

    # ------------------------------------------------------------------
    async def build_messages(
        self, system_prompt: str, history_turns: int = 6
    ) -> list[dict[str, str]]:
        messages = [{"role": "system", "content": system_prompt}]
        if not self._current_id:
            return messages

        async with self._db.execute(
            """SELECT role, text FROM turns
               WHERE conversation_id=?
               ORDER BY created_at DESC LIMIT ?""",
            (self._current_id, history_turns * 2),
        ) as cur:
            rows = await cur.fetchall()

        for row in reversed(rows):
            messages.append({"role": row["role"], "content": row["text"]})
        return messages

    # ------------------------------------------------------------------
    async def list_conversations(self, limit: int = 50) -> list[dict]:
        async with self._db.execute(
            "SELECT id, created_at, updated_at FROM conversations ORDER BY updated_at DESC LIMIT ?",
            (limit,),
        ) as cur:
            rows = await cur.fetchall()
        return [dict(r) for r in rows]

    async def get_conversation(self, cid: str) -> Optional[dict]:
        async with self._db.execute(
            "SELECT * FROM conversations WHERE id=?", (cid,)
        ) as cur:
            conv = await cur.fetchone()
        if not conv:
            return None
        async with self._db.execute(
            "SELECT * FROM turns WHERE conversation_id=? ORDER BY created_at", (cid,)
        ) as cur:
            turns = await cur.fetchall()
        return {**dict(conv), "turns": [dict(t) for t in turns]}

    async def delete_conversation(self, cid: str) -> None:
        await self._db.execute("DELETE FROM conversations WHERE id=?", (cid,))
        await self._db.commit()
        if self._current_id == cid:
            await self.new_conversation()

    async def export_conversation(self, cid: str) -> str:
        data = await self.get_conversation(cid)
        return json.dumps(data, indent=2, default=str)

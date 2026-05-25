"""Unit tests for ConversationStore."""

import pytest
from pathlib import Path
from voice_assistant.conversation import ConversationStore


@pytest.fixture
async def store(tmp_path: Path) -> ConversationStore:
    s = ConversationStore(db_path=tmp_path / "test.sqlite")
    await s.open()
    yield s
    await s.close()


@pytest.mark.asyncio
async def test_new_conversation(store: ConversationStore) -> None:
    cid = await store.new_conversation()
    assert len(cid) == 36  # UUID


@pytest.mark.asyncio
async def test_add_turn(store: ConversationStore) -> None:
    await store.add_turn("user", "Hello!")
    messages = await store.build_messages("You are a bot", history_turns=10)
    assert any(m["content"] == "Hello!" for m in messages)


@pytest.mark.asyncio
async def test_history_truncated(store: ConversationStore) -> None:
    for i in range(10):
        await store.add_turn("user", f"msg {i}")
    messages = await store.build_messages("sys", history_turns=3)
    # system + 3 turns max (3*2 = 6 roles but only user turns here)
    user_msgs = [m for m in messages if m["role"] == "user"]
    assert len(user_msgs) <= 3


@pytest.mark.asyncio
async def test_system_prompt_first(store: ConversationStore) -> None:
    await store.add_turn("user", "hi")
    messages = await store.build_messages("SYSTEM", history_turns=10)
    assert messages[0]["role"] == "system"
    assert messages[0]["content"] == "SYSTEM"


@pytest.mark.asyncio
async def test_list_conversations(store: ConversationStore) -> None:
    cid1 = await store.new_conversation()
    cid2 = await store.new_conversation()
    convs = await store.list_conversations()
    ids = [c["id"] for c in convs]
    assert cid1 in ids
    assert cid2 in ids


@pytest.mark.asyncio
async def test_delete_conversation(store: ConversationStore) -> None:
    cid = store.current_id
    await store.delete_conversation(cid)
    # After deletion, a new conversation is auto-created
    assert store.current_id != cid


@pytest.mark.asyncio
async def test_export_json(store: ConversationStore) -> None:
    import json
    await store.add_turn("user", "Hello")
    cid = store.current_id
    exported = await store.export_conversation(cid)
    data = json.loads(exported)
    assert data["id"] == cid
    assert len(data["turns"]) == 1

"""Unit tests for ConfigStore."""

import json
import pytest
from pathlib import Path

from voice_assistant.config import AppConfig, ConfigStore


@pytest.fixture
def tmp_store(tmp_path: Path) -> ConfigStore:
    default = tmp_path / "default.yaml"
    default.write_text(
        "mode: continuous\nllm:\n  model: llama3.2:3b\n  temperature: 0.7\n"
    )
    runtime = tmp_path / "runtime.json"
    return ConfigStore(default_path=default, runtime_path=runtime)


def test_load_defaults(tmp_store: ConfigStore) -> None:
    cfg = tmp_store.get()
    assert cfg.mode == "continuous"
    assert cfg.llm.model == "llama3.2:3b"
    assert cfg.llm.temperature == 0.7


@pytest.mark.asyncio
async def test_partial_update(tmp_store: ConfigStore) -> None:
    new_cfg = await tmp_store.update({"llm": {"temperature": 0.3}})
    assert new_cfg.llm.temperature == 0.3
    assert new_cfg.llm.model == "llama3.2:3b"  # unchanged


@pytest.mark.asyncio
async def test_persistence(tmp_store: ConfigStore, tmp_path: Path) -> None:
    await tmp_store.update({"llm": {"model": "phi3:mini"}})
    runtime = tmp_path / "runtime.json"
    assert runtime.exists()
    data = json.loads(runtime.read_text())
    assert data["llm"]["model"] == "phi3:mini"


@pytest.mark.asyncio
async def test_reload_after_update(tmp_store: ConfigStore) -> None:
    await tmp_store.update({"llm": {"temperature": 1.5}})
    tmp_store.reload()
    assert tmp_store.get().llm.temperature == 1.5


@pytest.mark.asyncio
async def test_invalid_value_rejected(tmp_store: ConfigStore) -> None:
    with pytest.raises(Exception):
        await tmp_store.update({"llm": {"temperature": 999}})


@pytest.mark.asyncio
async def test_invalid_mode_rejected(tmp_store: ConfigStore) -> None:
    with pytest.raises(Exception):
        await tmp_store.update({"mode": "invalid_mode"})


@pytest.mark.asyncio
async def test_change_handler_called(tmp_store: ConfigStore) -> None:
    called = []
    tmp_store.subscribe(lambda cfg: called.append(cfg))
    await tmp_store.update({"llm": {"temperature": 0.5}})
    assert len(called) == 1
    assert called[0].llm.temperature == 0.5

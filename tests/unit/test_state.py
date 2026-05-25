"""Unit tests for StateMachine."""

import pytest
from voice_assistant.state import InvalidTransitionError, PipelineState, StateMachine


@pytest.fixture
def sm() -> StateMachine:
    return StateMachine()


@pytest.mark.asyncio
async def test_initial_state(sm: StateMachine) -> None:
    assert sm.state == PipelineState.IDLE


@pytest.mark.asyncio
async def test_valid_transition_idle_to_listening(sm: StateMachine) -> None:
    await sm.transition(PipelineState.LISTENING)
    assert sm.state == PipelineState.LISTENING


@pytest.mark.asyncio
async def test_full_pipeline_sequence(sm: StateMachine) -> None:
    for s in [PipelineState.LISTENING, PipelineState.TRANSCRIBING,
              PipelineState.THINKING, PipelineState.SPEAKING, PipelineState.IDLE]:
        await sm.transition(s)
    assert sm.state == PipelineState.IDLE


@pytest.mark.asyncio
async def test_invalid_transition_raises(sm: StateMachine) -> None:
    with pytest.raises(InvalidTransitionError):
        await sm.transition(PipelineState.TRANSCRIBING)  # must go via LISTENING first


@pytest.mark.asyncio
async def test_invalid_idle_to_speaking(sm: StateMachine) -> None:
    with pytest.raises(InvalidTransitionError):
        await sm.transition(PipelineState.SPEAKING)


@pytest.mark.asyncio
async def test_invalid_idle_to_thinking(sm: StateMachine) -> None:
    with pytest.raises(InvalidTransitionError):
        await sm.transition(PipelineState.THINKING)


@pytest.mark.asyncio
async def test_invalid_listening_to_speaking(sm: StateMachine) -> None:
    await sm.transition(PipelineState.LISTENING)
    with pytest.raises(InvalidTransitionError):
        await sm.transition(PipelineState.SPEAKING)


@pytest.mark.asyncio
async def test_invalid_transcribing_to_listening(sm: StateMachine) -> None:
    await sm.transition(PipelineState.LISTENING)
    await sm.transition(PipelineState.TRANSCRIBING)
    with pytest.raises(InvalidTransitionError):
        await sm.transition(PipelineState.LISTENING)


@pytest.mark.asyncio
async def test_error_from_any_listening(sm: StateMachine) -> None:
    await sm.transition(PipelineState.LISTENING)
    await sm.transition(PipelineState.ERROR)
    assert sm.state == PipelineState.ERROR


@pytest.mark.asyncio
async def test_hook_called_on_transition(sm: StateMachine) -> None:
    events = []
    sm.add_hook(lambda old, new: events.append((old, new)))
    await sm.transition(PipelineState.LISTENING)
    assert len(events) == 1
    assert events[0] == (PipelineState.IDLE, PipelineState.LISTENING)


@pytest.mark.asyncio
async def test_event_bus_published(sm: StateMachine) -> None:
    from voice_assistant.utils.events import EventBus
    bus = EventBus()
    sm2 = StateMachine(event_bus=bus)
    received = []
    bus.subscribe("state.changed", lambda t, p: received.append(p))
    await sm2.transition(PipelineState.LISTENING)
    assert len(received) == 1
    assert received[0]["to"] == "LISTENING"


@pytest.mark.asyncio
async def test_barge_in_speaking_to_listening(sm: StateMachine) -> None:
    await sm.transition(PipelineState.LISTENING)
    await sm.transition(PipelineState.TRANSCRIBING)
    await sm.transition(PipelineState.THINKING)
    await sm.transition(PipelineState.SPEAKING)
    await sm.transition(PipelineState.LISTENING)
    assert sm.state == PipelineState.LISTENING

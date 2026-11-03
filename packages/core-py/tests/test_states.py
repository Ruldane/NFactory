import pytest

from nfactory_core.states import (
    TERMINAL_STATES,
    InvalidTransitionError,
    RunState,
    can_transition,
    transition,
)


def test_nominal_path_from_draft_to_completed() -> None:
    path = [
        RunState.PLANNING,
        RunState.APPROVAL_PENDING,
        RunState.QUEUED,
        RunState.RUNNING,
        RunState.REVIEW_PENDING,
        RunState.COMPLETED,
    ]
    state = RunState.DRAFT
    for target in path:
        state = transition(state, target)
    assert state is RunState.COMPLETED


@pytest.mark.parametrize("state", sorted(set(RunState) - TERMINAL_STATES))
def test_any_active_state_can_be_cancelled(state: RunState) -> None:
    assert can_transition(state, RunState.CANCELLED)


@pytest.mark.parametrize("terminal", sorted(TERMINAL_STATES))
@pytest.mark.parametrize("target", list(RunState))
def test_terminal_states_never_change(terminal: RunState, target: RunState) -> None:
    # Reworking a finished project means a new run, never "back to COMPLETED".
    assert not can_transition(terminal, target)


def test_cannot_complete_without_running() -> None:
    with pytest.raises(InvalidTransitionError) as exc:
        transition(RunState.QUEUED, RunState.COMPLETED)
    assert exc.value.current is RunState.QUEUED
    assert exc.value.target is RunState.COMPLETED


def test_cannot_skip_queue_from_draft_to_running() -> None:
    assert not can_transition(RunState.DRAFT, RunState.RUNNING)


def test_waiting_for_input_returns_to_planning() -> None:
    assert transition(RunState.WAITING_FOR_INPUT, RunState.PLANNING) is RunState.PLANNING

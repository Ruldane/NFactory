"""Run state machine (spec §10.2).

Interface: `RunState`, `can_transition`, `transition`, `TERMINAL_STATES`.
A terminal state never changes: reworking a project means creating a new run.
"""

from enum import StrEnum


class RunState(StrEnum):
    DRAFT = "DRAFT"
    PLANNING = "PLANNING"
    WAITING_FOR_INPUT = "WAITING_FOR_INPUT"
    APPROVAL_PENDING = "APPROVAL_PENDING"
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    REVIEW_PENDING = "REVIEW_PENDING"
    COMPLETED = "COMPLETED"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class StepState(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"
    CANCELLED = "CANCELLED"


TERMINAL_STATES: frozenset[RunState] = frozenset(
    {RunState.COMPLETED, RunState.PARTIAL, RunState.FAILED, RunState.CANCELLED}
)

_S = RunState
_ABORT = {_S.CANCELLED, _S.FAILED}  # reachable from any active state

_TRANSITIONS: dict[RunState, frozenset[RunState]] = {
    _S.DRAFT: frozenset({_S.PLANNING, _S.QUEUED, *_ABORT}),
    _S.PLANNING: frozenset({_S.WAITING_FOR_INPUT, _S.APPROVAL_PENDING, _S.QUEUED, *_ABORT}),
    _S.WAITING_FOR_INPUT: frozenset({_S.PLANNING, *_ABORT}),
    _S.APPROVAL_PENDING: frozenset({_S.QUEUED, _S.RUNNING, *_ABORT}),
    _S.QUEUED: frozenset({_S.RUNNING, *_ABORT}),
    _S.RUNNING: frozenset(
        {
            _S.APPROVAL_PENDING,
            _S.WAITING_FOR_INPUT,
            _S.REVIEW_PENDING,
            _S.COMPLETED,
            _S.PARTIAL,
            *_ABORT,
        }
    ),
    _S.REVIEW_PENDING: frozenset({_S.RUNNING, _S.COMPLETED, _S.PARTIAL, *_ABORT}),
}


class InvalidTransitionError(ValueError):
    def __init__(self, current: RunState, target: RunState) -> None:
        super().__init__(f"Invalid run transition: {current} -> {target}")
        self.current = current
        self.target = target


def can_transition(current: RunState, target: RunState) -> bool:
    return target in _TRANSITIONS.get(current, frozenset())


def transition(current: RunState, target: RunState) -> RunState:
    """Return `target` if the transition is allowed, else raise InvalidTransitionError."""
    if not can_transition(current, target):
        raise InvalidTransitionError(current, target)
    return target

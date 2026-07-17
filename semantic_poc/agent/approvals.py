from __future__ import annotations

from .schemas import ChangeStatus


class InvalidStateTransition(ValueError):
    """Raised when a change lifecycle transition is not permitted."""


_ALLOWED_TRANSITIONS: dict[ChangeStatus, frozenset[ChangeStatus]] = {
    ChangeStatus.DRAFT: frozenset({ChangeStatus.PROPOSED, ChangeStatus.REJECTED, ChangeStatus.FAILED}),
    ChangeStatus.PROPOSED: frozenset({ChangeStatus.APPROVED, ChangeStatus.REJECTED, ChangeStatus.FAILED}),
    ChangeStatus.APPROVED: frozenset({ChangeStatus.APPLIED_LOCAL, ChangeStatus.REJECTED, ChangeStatus.FAILED}),
    ChangeStatus.APPLIED_LOCAL: frozenset({ChangeStatus.VALIDATED, ChangeStatus.FAILED}),
    ChangeStatus.VALIDATED: frozenset(),
    ChangeStatus.REJECTED: frozenset(),
    ChangeStatus.FAILED: frozenset(),
}


def allowed_transitions(status: ChangeStatus) -> frozenset[ChangeStatus]:
    return _ALLOWED_TRANSITIONS[status]


def validate_transition(current: ChangeStatus, proposed: ChangeStatus) -> None:
    if proposed not in allowed_transitions(current):
        raise InvalidStateTransition(f"Transition from {current.value} to {proposed.value} is not allowed.")

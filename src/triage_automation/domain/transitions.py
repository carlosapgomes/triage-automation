"""Deterministic transition guards for case statuses."""

from __future__ import annotations

from typing import Final

from triage_automation.domain.case_status import CaseStatus


class InvalidCaseTransitionError(ValueError):
    """Raised when an attempted case state transition is not allowed."""


_ALLOWED_TRANSITIONS: Final[dict[CaseStatus, frozenset[CaseStatus]]] = {
    CaseStatus.NEW: frozenset({CaseStatus.R1_ACK_PROCESSING}),
    CaseStatus.R1_ACK_PROCESSING: frozenset({CaseStatus.EXTRACTING}),
    CaseStatus.EXTRACTING: frozenset({CaseStatus.LLM_STRUCT, CaseStatus.FAILED}),
    CaseStatus.LLM_STRUCT: frozenset({CaseStatus.LLM_SUGGEST, CaseStatus.FAILED}),
    CaseStatus.LLM_SUGGEST: frozenset({CaseStatus.R2_POST_WIDGET, CaseStatus.FAILED}),
    CaseStatus.R2_POST_WIDGET: frozenset({CaseStatus.WAIT_DOCTOR}),
    CaseStatus.WAIT_DOCTOR: frozenset({CaseStatus.DOCTOR_DENIED, CaseStatus.DOCTOR_ACCEPTED}),
    CaseStatus.DOCTOR_DENIED: frozenset({CaseStatus.WAIT_R1_CLEANUP_THUMBS}),
    CaseStatus.DOCTOR_ACCEPTED: frozenset({CaseStatus.R3_POST_REQUEST}),
    CaseStatus.R3_POST_REQUEST: frozenset({CaseStatus.WAIT_APPT}),
    CaseStatus.WAIT_APPT: frozenset({CaseStatus.APPT_CONFIRMED, CaseStatus.APPT_DENIED}),
    CaseStatus.APPT_CONFIRMED: frozenset({CaseStatus.WAIT_R1_CLEANUP_THUMBS}),
    CaseStatus.APPT_DENIED: frozenset({CaseStatus.WAIT_R1_CLEANUP_THUMBS}),
    CaseStatus.FAILED: frozenset({CaseStatus.WAIT_R1_CLEANUP_THUMBS}),
    # Compatibility status in enum; runtime still transitions to WAIT_R1_CLEANUP_THUMBS directly.
    CaseStatus.R1_FINAL_REPLY_POSTED: frozenset({CaseStatus.WAIT_R1_CLEANUP_THUMBS}),
    CaseStatus.WAIT_R1_CLEANUP_THUMBS: frozenset({CaseStatus.CLEANUP_RUNNING}),
    CaseStatus.CLEANUP_RUNNING: frozenset({CaseStatus.CLEANED}),
    CaseStatus.CLEANED: frozenset(),
}


def can_transition(from_status: CaseStatus, to_status: CaseStatus) -> bool:
    """Return whether the transition is valid for the case state machine."""

    allowed_targets = _ALLOWED_TRANSITIONS[from_status]
    return to_status in allowed_targets


def assert_transition(from_status: CaseStatus, to_status: CaseStatus) -> None:
    """Assert a transition is allowed, else raise deterministic domain error."""

    if not can_transition(from_status, to_status):
        raise InvalidCaseTransitionError(
            f"Invalid case status transition: {from_status.value} -> {to_status.value}"
        )

from __future__ import annotations

import pytest

from triage_automation.domain.case_status import CaseStatus
from triage_automation.domain.transitions import (
    InvalidCaseTransitionError,
    assert_transition,
)


@pytest.mark.parametrize(
    ("from_status", "to_status"),
    [
        (CaseStatus.NEW, CaseStatus.R1_ACK_PROCESSING),
        (CaseStatus.R1_ACK_PROCESSING, CaseStatus.EXTRACTING),
        (CaseStatus.EXTRACTING, CaseStatus.LLM_STRUCT),
        (CaseStatus.EXTRACTING, CaseStatus.FAILED),
        (CaseStatus.LLM_STRUCT, CaseStatus.LLM_SUGGEST),
        (CaseStatus.LLM_SUGGEST, CaseStatus.R2_POST_WIDGET),
        (CaseStatus.WAIT_DOCTOR, CaseStatus.DOCTOR_ACCEPTED),
        (CaseStatus.WAIT_DOCTOR, CaseStatus.DOCTOR_DENIED),
        (CaseStatus.DOCTOR_ACCEPTED, CaseStatus.R3_POST_REQUEST),
        (CaseStatus.R3_POST_REQUEST, CaseStatus.WAIT_APPT),
        (CaseStatus.WAIT_APPT, CaseStatus.APPT_CONFIRMED),
        (CaseStatus.WAIT_APPT, CaseStatus.APPT_DENIED),
        (CaseStatus.WAIT_R1_CLEANUP_THUMBS, CaseStatus.CLEANUP_RUNNING),
        (CaseStatus.CLEANUP_RUNNING, CaseStatus.CLEANED),
    ],
)
def test_allowed_transitions_pass(from_status: CaseStatus, to_status: CaseStatus) -> None:
    assert_transition(from_status, to_status)


@pytest.mark.parametrize(
    "from_status",
    [
        CaseStatus.DOCTOR_DENIED,
        CaseStatus.APPT_CONFIRMED,
        CaseStatus.APPT_DENIED,
        CaseStatus.FAILED,
        CaseStatus.R1_FINAL_REPLY_POSTED,
    ],
)
def test_final_reply_related_states_transition_directly_to_wait_cleanup(
    from_status: CaseStatus,
) -> None:
    assert_transition(from_status, CaseStatus.WAIT_R1_CLEANUP_THUMBS)


@pytest.mark.parametrize(
    ("from_status", "to_status"),
    [
        (CaseStatus.NEW, CaseStatus.WAIT_DOCTOR),
        (CaseStatus.WAIT_APPT, CaseStatus.CLEANUP_RUNNING),
        (CaseStatus.CLEANED, CaseStatus.NEW),
        (CaseStatus.WAIT_DOCTOR, CaseStatus.WAIT_DOCTOR),
    ],
)
def test_invalid_transitions_raise_deterministic_error(
    from_status: CaseStatus,
    to_status: CaseStatus,
) -> None:
    with pytest.raises(InvalidCaseTransitionError) as exc_info:
        assert_transition(from_status, to_status)

    message = str(exc_info.value)
    assert from_status.value in message
    assert to_status.value in message

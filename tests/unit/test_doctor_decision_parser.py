from __future__ import annotations

from uuid import UUID

import pytest

from triage_automation.domain.doctor_decision_parser import (
    DoctorDecisionParseError,
    parse_doctor_decision_reply,
)


def test_parse_accept_template_success() -> None:
    case_id = "11111111-1111-1111-1111-111111111111"
    body = (
        "decision: accept\n"
        "support_flag: anesthesist\n"
        "reason: risco cardiovascular moderado\n"
        f"case_id: {case_id}\n"
    )

    parsed = parse_doctor_decision_reply(body=body)

    assert str(parsed.case_id) == case_id
    assert parsed.decision == "accept"
    assert parsed.support_flag == "anesthesist"
    assert parsed.reason == "risco cardiovascular moderado"


def test_parse_deny_template_with_empty_reason_success() -> None:
    case_id = "22222222-2222-2222-2222-222222222222"
    body = (
        "decision: deny\n"
        "support_flag: none\n"
        "reason:\n"
        f"case_id: {case_id}\n"
    )

    parsed = parse_doctor_decision_reply(body=body)

    assert str(parsed.case_id) == case_id
    assert parsed.decision == "deny"
    assert parsed.support_flag == "none"
    assert parsed.reason is None


def test_parse_rejects_unknown_field() -> None:
    body = (
        "decision: accept\n"
        "support_flag: none\n"
        "reason: ok\n"
        "caso: 11111111-1111-1111-1111-111111111111\n"
    )

    with pytest.raises(DoctorDecisionParseError, match="unknown_field"):
        parse_doctor_decision_reply(body=body)


def test_parse_rejects_missing_required_field() -> None:
    body = (
        "decision: accept\n"
        "reason: ok\n"
        "case_id: 11111111-1111-1111-1111-111111111111\n"
    )

    with pytest.raises(DoctorDecisionParseError, match="missing_support_flag_line"):
        parse_doctor_decision_reply(body=body)


def test_parse_rejects_invalid_case_uuid() -> None:
    body = (
        "decision: accept\n"
        "support_flag: none\n"
        "reason: ok\n"
        "case_id: not-a-uuid\n"
    )

    with pytest.raises(DoctorDecisionParseError, match="invalid_case_line"):
        parse_doctor_decision_reply(body=body)


def test_parse_rejects_case_id_mismatch() -> None:
    body = (
        "decision: accept\n"
        "support_flag: none\n"
        "reason: ok\n"
        "case_id: 11111111-1111-1111-1111-111111111111\n"
    )

    with pytest.raises(DoctorDecisionParseError, match="case_id_mismatch"):
        parse_doctor_decision_reply(
            body=body,
            expected_case_id=UUID("22222222-2222-2222-2222-222222222222"),
        )

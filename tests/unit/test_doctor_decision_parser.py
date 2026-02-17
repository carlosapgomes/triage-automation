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
        "decisao: aceitar\n"
        "suporte: anestesista\n"
        "motivo: risco cardiovascular moderado\n"
        f"caso: {case_id}\n"
    )

    parsed = parse_doctor_decision_reply(body=body)

    assert str(parsed.case_id) == case_id
    assert parsed.decision == "accept"
    assert parsed.support_flag == "anesthesist"
    assert parsed.reason is None


def test_parse_deny_template_with_empty_reason_success() -> None:
    case_id = "22222222-2222-2222-2222-222222222222"
    body = (
        "decisao: negar\n"
        "suporte: nenhum\n"
        "motivo:\n"
        f"caso: {case_id}\n"
    )

    parsed = parse_doctor_decision_reply(body=body)

    assert str(parsed.case_id) == case_id
    assert parsed.decision == "deny"
    assert parsed.support_flag == "none"
    assert parsed.reason is None


def test_parse_treats_optional_reason_marker_as_empty() -> None:
    case_id = "22222222-2222-2222-2222-222222222222"
    body = (
        "decisao: aceitar\n"
        "suporte: nenhum\n"
        "motivo: (opcional)\n"
        f"caso: {case_id}\n"
    )

    parsed = parse_doctor_decision_reply(body=body)

    assert str(parsed.case_id) == case_id
    assert parsed.reason is None


def test_parse_still_accepts_legacy_english_keys_for_backward_compatibility() -> None:
    body = (
        "decision: accept\n"
        "support_flag: none\n"
        "reason: ok\n"
        "case_id: 11111111-1111-1111-1111-111111111111\n"
    )

    parsed = parse_doctor_decision_reply(body=body)

    assert parsed.decision == "accept"
    assert parsed.support_flag == "none"


def test_parse_accepts_without_space_after_colon() -> None:
    body = (
        "decisao:aceitar\n"
        "suporte:nenhum\n"
        "motivo:ok\n"
        "caso:11111111-1111-1111-1111-111111111111\n"
    )

    parsed = parse_doctor_decision_reply(body=body)

    assert parsed.decision == "accept"
    assert parsed.support_flag == "none"
    assert parsed.reason is None


def test_parse_accepts_template_wrapped_in_code_fences() -> None:
    body = (
        "```text\n"
        "decisao: aceitar\n"
        "suporte: nenhum\n"
        "motivo: ok\n"
        "caso: 11111111-1111-1111-1111-111111111111\n"
        "```\n"
    )

    parsed = parse_doctor_decision_reply(body=body)

    assert parsed.decision == "accept"
    assert parsed.support_flag == "none"


def test_parse_accepts_decisao_with_accent() -> None:
    body = (
        "decisão: aceitar\n"
        "suporte: nenhum\n"
        "motivo: ok\n"
        "caso: 11111111-1111-1111-1111-111111111111\n"
    )

    parsed = parse_doctor_decision_reply(body=body)

    assert parsed.decision == "accept"
    assert parsed.support_flag == "none"


def test_parse_ignores_unknown_field_lines() -> None:
    body = (
        "decisao: aceitar\n"
        "suporte: nenhum\n"
        "motivo: ok\n"
        "campo_extra: 11111111-1111-1111-1111-111111111111\n"
        "caso: 11111111-1111-1111-1111-111111111111\n"
    )

    parsed = parse_doctor_decision_reply(body=body)

    assert parsed.decision == "accept"
    assert parsed.support_flag == "none"


def test_parse_rejects_missing_required_field() -> None:
    body = (
        "decisao: aceitar\n"
        "motivo: ok\n"
        "caso: 11111111-1111-1111-1111-111111111111\n"
    )

    with pytest.raises(DoctorDecisionParseError, match="missing_support_flag_line"):
        parse_doctor_decision_reply(body=body)


def test_parse_rejects_invalid_case_uuid() -> None:
    body = (
        "decisao: aceitar\n"
        "suporte: nenhum\n"
        "motivo: ok\n"
        "caso: not-a-uuid\n"
    )

    with pytest.raises(DoctorDecisionParseError, match="invalid_case_line"):
        parse_doctor_decision_reply(body=body)


def test_parse_rejects_case_id_mismatch() -> None:
    body = (
        "decisao: aceitar\n"
        "suporte: nenhum\n"
        "motivo: ok\n"
        "caso: 11111111-1111-1111-1111-111111111111\n"
    )

    with pytest.raises(DoctorDecisionParseError, match="case_id_mismatch"):
        parse_doctor_decision_reply(
            body=body,
            expected_case_id=UUID("22222222-2222-2222-2222-222222222222"),
        )


def test_parse_rejects_deny_with_non_none_support_flag() -> None:
    body = (
        "decisao: negar\n"
        "suporte: anestesista\n"
        "motivo: risco alto\n"
        "caso: 11111111-1111-1111-1111-111111111111\n"
    )

    with pytest.raises(DoctorDecisionParseError, match="invalid_support_flag_for_decision"):
        parse_doctor_decision_reply(body=body)


def test_parse_accept_allows_anesthesist_icu_support_flag() -> None:
    body = (
        "decisao: aceitar\n"
        "suporte: anestesista_uti\n"
        "motivo: suporte adicional recomendado\n"
        "caso: 11111111-1111-1111-1111-111111111111\n"
    )

    parsed = parse_doctor_decision_reply(body=body)

    assert parsed.decision == "accept"
    assert parsed.support_flag == "anesthesist_icu"


def test_parse_rejects_typed_doctor_user_id_field() -> None:
    body = (
        "decisao: aceitar\n"
        "suporte: nenhum\n"
        "motivo: ok\n"
        "doctor_user_id: @doctor:example.org\n"
        "caso: 11111111-1111-1111-1111-111111111111\n"
    )

    with pytest.raises(DoctorDecisionParseError, match="unknown_field"):
        parse_doctor_decision_reply(body=body)


def test_parse_ignores_non_labeled_extra_line() -> None:
    body = (
        "texto livre sem campo\n"
        "decisao: aceitar\n"
        "suporte: nenhum\n"
        "motivo: ok\n"
        "caso: 11111111-1111-1111-1111-111111111111\n"
    )

    parsed = parse_doctor_decision_reply(body=body)

    assert parsed.decision == "accept"
    assert parsed.support_flag == "none"


def test_parse_accept_without_reason_line_success() -> None:
    body = (
        "decisao: aceitar\n"
        "suporte: nenhum\n"
        "caso: 11111111-1111-1111-1111-111111111111\n"
    )

    parsed = parse_doctor_decision_reply(body=body)

    assert parsed.decision == "accept"
    assert parsed.support_flag == "none"
    assert parsed.reason is None


def test_parse_accept_ignores_non_empty_reason() -> None:
    body = (
        "decisao: aceitar\n"
        "suporte: anestesista\n"
        "motivo: manter em observacao\n"
        "caso: 11111111-1111-1111-1111-111111111111\n"
    )

    parsed = parse_doctor_decision_reply(body=body)

    assert parsed.decision == "accept"
    assert parsed.support_flag == "anesthesist"
    assert parsed.reason is None


def test_parse_rejects_invalid_decision_enum_value() -> None:
    body = (
        "decisao: talvez\n"
        "suporte: nenhum\n"
        "motivo: ok\n"
        "caso: 11111111-1111-1111-1111-111111111111\n"
    )

    with pytest.raises(DoctorDecisionParseError, match="invalid_decision_value"):
        parse_doctor_decision_reply(body=body)


def test_parse_rejects_invalid_support_flag_enum_value() -> None:
    body = (
        "decisao: aceitar\n"
        "suporte: cirurgiao\n"
        "motivo: ok\n"
        "caso: 11111111-1111-1111-1111-111111111111\n"
    )

    with pytest.raises(DoctorDecisionParseError, match="invalid_support_flag_value"):
        parse_doctor_decision_reply(body=body)

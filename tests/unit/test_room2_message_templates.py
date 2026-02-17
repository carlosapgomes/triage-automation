from __future__ import annotations

from uuid import UUID

from triage_automation.infrastructure.matrix.message_templates import (
    build_room2_case_decision_instructions_message,
    build_room2_case_pdf_message,
    build_room2_case_summary_message,
    build_room2_decision_ack_message,
)


def test_build_room2_case_pdf_message_includes_case_and_pdf_context() -> None:
    case_id = UUID("11111111-1111-1111-1111-111111111111")

    body = build_room2_case_pdf_message(
        case_id=case_id,
        agency_record_number="12345",
        pdf_mxc_url="mxc://example.org/report-1",
    )

    assert str(case_id) in body
    assert "12345" in body
    assert "mxc://example.org/report-1" in body
    assert "PDF original" in body


def test_build_room2_case_summary_message_includes_structured_payloads() -> None:
    case_id = UUID("22222222-2222-2222-2222-222222222222")

    body = build_room2_case_summary_message(
        case_id=case_id,
        structured_data={"policy_precheck": {"labs_pass": "yes"}, "eda": {"asa": {"class": "II"}}},
        summary_text="Resumo LLM1",
        suggested_action={"suggestion": "accept", "support_recommendation": "none"},
    )

    assert str(case_id) in body
    assert "Resumo LLM1" in body
    assert '"labs_pass": "yes"' in body
    assert '"suggestion": "accept"' in body
    assert "Dados estruturados" in body
    assert "Recomendacao" in body


def test_build_room2_case_decision_instructions_message_has_strict_template() -> None:
    case_id = UUID("33333333-3333-3333-3333-333333333333")

    body = build_room2_case_decision_instructions_message(case_id=case_id)

    assert "reply" in body.lower()
    assert "decision: accept|deny" in body
    assert "support_flag: none|anesthesist|anesthesist_icu" in body
    assert "reason:" in body
    assert f"case_id: {case_id}" in body


def test_build_room2_decision_ack_message_has_deterministic_success_fields() -> None:
    case_id = UUID("44444444-4444-4444-4444-444444444444")

    body = build_room2_decision_ack_message(
        case_id=case_id,
        decision="accept",
        support_flag="none",
        reason="criterios atendidos",
    )

    assert "resultado: sucesso" in body
    assert f"case_id: {case_id}" in body
    assert "decision: accept" in body
    assert "support_flag: none" in body
    assert "reason: criterios atendidos" in body

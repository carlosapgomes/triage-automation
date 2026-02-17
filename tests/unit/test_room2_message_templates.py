from __future__ import annotations

from uuid import UUID

from triage_automation.infrastructure.matrix.message_templates import (
    build_room2_case_decision_instructions_message,
    build_room2_case_pdf_message,
    build_room2_case_summary_message,
    build_room2_decision_ack_message,
    build_room2_decision_error_message,
)


def test_build_room2_case_pdf_message_includes_case_and_pdf_context() -> None:
    case_id = UUID("11111111-1111-1111-1111-111111111111")

    body = build_room2_case_pdf_message(
        case_id=case_id,
        agency_record_number="12345",
        extracted_text="Paciente com dispepsia crônica.",
    )

    assert f"caso: {case_id}" in body
    assert "12345" in body
    assert "Paciente com dispepsia crônica." in body
    assert "texto extraido" in body.lower()


def test_build_room2_case_summary_message_includes_structured_payloads() -> None:
    case_id = UUID("22222222-2222-2222-2222-222222222222")

    body = build_room2_case_summary_message(
        case_id=case_id,
        structured_data={
            "policy_precheck": {"labs_pass": "yes", "pediatric_flag": True},
            "eda": {"asa": {"class": "II"}, "ecg": {"abnormal_flag": "unknown"}},
        },
        summary_text="Resumo LLM1",
        suggested_action={"suggestion": "accept", "support_recommendation": "none"},
    )

    assert f"caso: {case_id}" in body
    assert "Resumo LLM1" in body
    assert "- prechecagem_politica:" in body
    assert "  - laboratorio_aprovado: sim" in body
    assert "  - é pediátrico?: sim" in body
    assert "  - asa: classe=II" in body
    assert "  - ecg: sinal de alerta=desconhecido" in body
    assert "flag_pediatrico" not in body
    assert "abnormal_flag" not in body
    assert "sugestao" in body.lower()
    assert "aceitar" in body
    assert "accept" not in body
    assert "Dados extraidos" in body
    assert "Recomendacao" in body
    assert "```json" not in body


def test_build_room2_case_decision_instructions_message_has_strict_template() -> None:
    case_id = UUID("33333333-3333-3333-3333-333333333333")

    body = build_room2_case_decision_instructions_message(case_id=case_id)

    assert "resposta" in body.lower()
    assert "decisao: aceitar|negar" in body
    assert "suporte: nenhum|anestesista|anestesista_uti" in body
    assert "motivo:" in body
    assert f"caso: {case_id}" in body


def test_build_room2_decision_ack_message_has_deterministic_success_fields() -> None:
    case_id = UUID("44444444-4444-4444-4444-444444444444")

    body = build_room2_decision_ack_message(
        case_id=case_id,
        decision="accept",
        support_flag="none",
        reason="criterios atendidos",
    )

    assert "resultado: sucesso" in body
    assert f"caso: {case_id}" in body
    assert "decisao: aceitar" in body
    assert "suporte: nenhum" in body
    assert "motivo: criterios atendidos" in body


def test_build_room2_decision_error_message_has_actionable_guidance() -> None:
    case_id = UUID("55555555-5555-5555-5555-555555555555")

    body = build_room2_decision_error_message(
        case_id=case_id,
        error_code="invalid_template",
    )

    assert "resultado: erro" in body
    assert f"caso: {case_id}" in body
    assert "codigo_erro: invalid_template" in body
    assert "acao:" in body
    assert "Modelo obrigatorio" in body
    assert "decisao: aceitar|negar" in body

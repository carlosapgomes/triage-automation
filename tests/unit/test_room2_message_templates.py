from __future__ import annotations

from uuid import UUID

from triage_automation.infrastructure.matrix.message_templates import (
    build_room2_case_decision_instructions_formatted_html,
    build_room2_case_decision_instructions_message,
    build_room2_case_decision_template_formatted_html,
    build_room2_case_decision_template_message,
    build_room2_case_pdf_attachment_filename,
    build_room2_case_pdf_formatted_html,
    build_room2_case_pdf_message,
    build_room2_case_summary_formatted_html,
    build_room2_case_summary_message,
    build_room2_decision_ack_message,
    build_room2_decision_error_message,
)


def test_build_room2_case_pdf_message_includes_compact_context_and_attachment_hint() -> None:
    case_id = UUID("11111111-1111-1111-1111-111111111111")

    body = build_room2_case_pdf_message(
        case_id=case_id,
        agency_record_number="12345",
        patient_name="MARIA",
        extracted_text="Paciente com dispepsia crônica.",
    )

    assert "no. ocorrência: 12345" in body
    assert "paciente: MARIA" in body
    assert f"caso: {case_id}" not in body
    assert "PDF original do relatório" in body


def test_build_room2_case_pdf_formatted_html_includes_preview_context() -> None:
    case_id = UUID("11111111-1111-1111-1111-111111111111")

    body = build_room2_case_pdf_formatted_html(
        case_id=case_id,
        agency_record_number="12345",
        patient_name="MARIA",
        extracted_text="Linha 1\nLinha 2",
    )

    assert "<h1>Solicitação de triagem - contexto original</h1>" in body
    assert "<p>no. ocorrência: 12345</p>" in body
    assert "<p>paciente: MARIA</p>" in body
    assert f"<p>caso: {case_id}</p>" not in body
    assert "PDF original do relatório" in body


def test_build_room2_case_pdf_attachment_filename_is_deterministic() -> None:
    case_id = UUID("11111111-1111-1111-1111-111111111111")

    filename = build_room2_case_pdf_attachment_filename(
        case_id=case_id,
        agency_record_number="4777300",
    )

    assert (
        filename
        == "ocorrencia-4777300-caso-11111111-1111-1111-1111-111111111111-relatorio-original.pdf"
    )


def test_build_room2_case_pdf_attachment_filename_uses_fallback_when_record_missing() -> None:
    case_id = UUID("11111111-1111-1111-1111-111111111111")

    filename = build_room2_case_pdf_attachment_filename(
        case_id=case_id,
        agency_record_number=" ",
    )

    assert (
        filename
        == "ocorrencia-indisponivel-caso-11111111-1111-1111-1111-111111111111-relatorio-original.pdf"
    )


def test_build_room2_case_summary_message_includes_structured_payloads() -> None:
    case_id = UUID("22222222-2222-2222-2222-222222222222")

    body = build_room2_case_summary_message(
        case_id=case_id,
        agency_record_number="12345",
        patient_name="PACIENTE",
        structured_data={
            "policy_precheck": {"labs_pass": "yes", "pediatric_flag": True},
            "eda": {"asa": {"class": "II"}, "ecg": {"abnormal_flag": "unknown"}},
        },
        summary_text="Resumo LLM1",
        suggested_action={"suggestion": "accept", "support_recommendation": "none"},
    )

    assert "no. ocorrência: 12345" in body
    assert "paciente: PACIENTE" in body
    assert f"caso: {case_id}" not in body
    assert "Resumo LLM1" in body
    assert "# Resumo técnico da triagem" in body
    assert "## Resumo clínico:" in body
    assert "## Dados extraídos:" in body
    assert "## Recomendação do sistema:" in body
    assert "- prechecagem_politica: laboratorio_aprovado=sim;" in body
    assert "é pediátrico?=sim" in body
    assert "- eda: asa.classe=II; ecg.sinal de alerta=desconhecido" in body
    assert "flag_pediatrico" not in body
    assert "abnormal_flag" not in body
    assert "sugestao" in body.lower()
    assert "aceitar" in body
    assert "accept" not in body
    assert "Dados extraídos" in body
    assert "Recomendação" in body
    assert "```json" not in body


def test_build_room2_case_decision_instructions_message_has_strict_template() -> None:
    case_id = UUID("33333333-3333-3333-3333-333333333333")

    body = build_room2_case_decision_instructions_message(
        case_id=case_id,
        agency_record_number="12345",
        patient_name="PACIENTE",
    )

    assert "copie a próxima mensagem" in body.lower()
    assert "responda como resposta a ela" in body.lower()
    assert "decisão:aceitar" in body
    assert "valores válidos" in body.lower()
    assert "no. ocorrência: 12345" in body
    assert "paciente: PACIENTE" in body
    assert "caso esperado" not in body


def test_build_room2_case_decision_instructions_formatted_html_has_guidance() -> None:
    case_id = UUID("33333333-3333-3333-3333-333333333333")

    body = build_room2_case_decision_instructions_formatted_html(
        case_id=case_id,
        agency_record_number="12345",
        patient_name="PACIENTE",
    )

    assert "<h1>Instrução de decisão médica</h1>" in body
    assert "<ol>" in body
    assert "Copie a <strong>PRÓXIMA mensagem</strong>" in body
    assert "<p>no. ocorrência: 12345<br>paciente: PACIENTE</p>" in body
    assert "decisão:aceitar" in body


def test_build_room2_case_decision_template_message_is_copy_paste_ready() -> None:
    case_id = UUID("33333333-3333-3333-3333-333333333333")

    body = build_room2_case_decision_template_message(case_id=case_id)

    assert body.startswith("decisao: aceitar\n")
    assert "suporte: nenhum\n" in body
    assert "motivo: (opcional)\n" in body
    assert body.endswith(f"caso: {case_id}")


def test_build_room2_case_decision_template_formatted_html_has_plain_lines() -> None:
    case_id = UUID("33333333-3333-3333-3333-333333333333")

    body = build_room2_case_decision_template_formatted_html(case_id=case_id)

    assert body.startswith("<p>")
    assert "decisao: aceitar" in body
    assert "suporte: nenhum" in body
    assert "motivo: (opcional)" in body
    assert f"caso: {case_id}" in body
    assert "<br>" in body
    assert body.endswith("</p>")


def test_build_room2_case_summary_formatted_html_includes_sections() -> None:
    case_id = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")

    body = build_room2_case_summary_formatted_html(
        case_id=case_id,
        agency_record_number="12345",
        patient_name="PACIENTE",
        structured_data={
            "policy_precheck": {"labs_pass": "yes", "pediatric_flag": True},
            "eda": {"ecg": {"abnormal_flag": "unknown"}},
        },
        summary_text="Resumo LLM1",
        suggested_action={"suggestion": "accept", "support_recommendation": "none"},
    )

    assert "<h1>Resumo técnico da triagem</h1>" in body
    assert "<p>no. ocorrência: 12345</p>" in body
    assert "<p>paciente: PACIENTE</p>" in body
    assert f"<p>caso: {case_id}</p>" not in body
    assert "<h2>Resumo clínico:</h2>" in body
    assert "<p>Resumo LLM1</p>" in body
    assert "<h2>Dados extraídos:</h2>" in body
    assert "<li>prechecagem_politica: laboratorio_aprovado=sim;" in body
    assert "é pediátrico?=sim" in body
    assert "<li>eda: ecg.sinal de alerta=desconhecido</li>" in body
    assert "<h2>Recomendação do sistema:</h2>" in body
    assert "<li>sugestao: aceitar</li>" in body


def test_build_room2_case_summary_message_removes_redundant_metadata() -> None:
    case_id = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")

    body = build_room2_case_summary_message(
        case_id=case_id,
        agency_record_number="12345",
        patient_name="JOSE",
        structured_data={
            "language": "pt-BR",
            "schema_version": "1.1",
            "agency_record_number": "12345",
            "patient": {"name": "JOSE"},
        },
        summary_text="Resumo clínico",
        suggested_action={
            "case_id": str(case_id),
            "language": "pt-BR",
            "schema_version": "1.1",
            "agency_record_number": "12345",
            "suggestion": "deny",
        },
    )

    assert body.count("idioma:") == 0
    assert body.count("versao_schema:") == 0
    assert body.count("caso:") == 0
    assert body.count("no. ocorrência: 12345") == 1
    assert body.count("paciente: JOSE") == 1
    assert body.count("numero_registro: 12345") == 1


def test_build_room2_decision_ack_message_has_deterministic_success_fields() -> None:
    case_id = UUID("44444444-4444-4444-4444-444444444444")

    body = build_room2_decision_ack_message(
        case_id=case_id,
        decision="accept",
        support_flag="none",
        reason="criterios atendidos",
    )

    assert "resultado: sucesso" in body
    assert "no. ocorrência: não detectado" in body
    assert "paciente: não detectado" in body
    assert f"caso: {case_id}" not in body
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
    assert "Modelo obrigatório" in body
    assert "decisao: aceitar|negar" in body

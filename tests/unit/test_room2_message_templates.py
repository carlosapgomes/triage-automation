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


def _extract_markdown_section_lines(
    *,
    body: str,
    section: str,
    next_section: str | None,
) -> list[str]:
    start = body.index(section) + len(section)
    if next_section is None:
        end = len(body)
    else:
        end = body.index(next_section, start)
    chunk = body[start:end]
    return [line.strip() for line in chunk.splitlines() if line.strip()]


def _extract_html_section_chunk(*, body: str, section: str, next_section: str) -> str:
    start = body.index(section) + len(section)
    end = body.index(next_section, start)
    return body[start:end]


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
        == (
            "ocorrencia-indisponivel-caso-11111111-1111-1111-1111-111111111111-"
            "relatorio-original.pdf"
        )
    )


def test_build_room2_case_summary_message_avoids_full_flattened_dump() -> None:
    case_id = UUID("22222222-2222-2222-2222-222222222222")

    body = build_room2_case_summary_message(
        case_id=case_id,
        agency_record_number="12345",
        patient_name="PACIENTE",
        structured_data={
            "policy_precheck": {
                "labs_pass": "yes",
                "ecg_present": "no",
                "labs_failed_items": ["INR ausente"],
            },
            "eda": {
                "labs": {"hb_g_dl": 10.2, "platelets_per_mm3": 140000, "inr": None},
                "ecg": {"report_present": "no", "abnormal_flag": "unknown"},
            },
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
    assert "## Achados críticos:" in body
    assert "## Pendências críticas:" in body
    assert "## Decisão sugerida:" in body
    assert "## Suporte recomendado:" in body
    assert "## Motivo objetivo:" in body
    assert "## Conduta sugerida:" in body
    assert "## Dados extraídos:" not in body
    assert "## Recomendação do sistema:" not in body
    section_order = [
        "## Resumo clínico:",
        "## Achados críticos:",
        "## Pendências críticas:",
        "## Decisão sugerida:",
        "## Suporte recomendado:",
        "## Motivo objetivo:",
        "## Conduta sugerida:",
    ]
    section_positions = [body.index(section) for section in section_order]
    assert section_positions == sorted(section_positions)
    assert "- Hb: 10.2" in body
    assert "- Plaquetas: 140000" in body
    assert "- INR: não informado" in body
    assert "- ECG presente: nao" in body
    assert "- ECG sinal de alerta: desconhecido" in body
    assert "- Pré-check laboratório: sim" in body
    assert "- Pré-check ECG: nao" in body
    assert "- Pendências de laboratório: INR ausente" in body
    assert "flag_pediatrico" not in body
    assert "abnormal_flag" not in body
    assert "prechecagem_politica:" not in body
    assert "asa.classe=" not in body
    assert "ecg.sinal de alerta=" not in body
    assert "aceitar" in body
    assert "accept" not in body
    assert "Achados críticos" in body
    assert "Conduta sugerida" in body
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
            "policy_precheck": {
                "labs_pass": "yes",
                "ecg_present": "no",
                "labs_failed_items": ["INR ausente"],
            },
            "eda": {
                "labs": {"hb_g_dl": 10.2, "platelets_per_mm3": 140000, "inr": None},
                "ecg": {"report_present": "no", "abnormal_flag": "unknown"},
            },
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
    assert "<h2>Achados críticos:</h2>" in body
    assert "<h2>Pendências críticas:</h2>" in body
    assert "<h2>Decisão sugerida:</h2>" in body
    assert "<h2>Suporte recomendado:</h2>" in body
    assert "<h2>Motivo objetivo:</h2>" in body
    assert "<h2>Conduta sugerida:</h2>" in body
    assert "<h2>Dados extraídos:</h2>" not in body
    assert "<h2>Recomendação do sistema:</h2>" not in body
    section_order = [
        "<h2>Resumo clínico:</h2>",
        "<h2>Achados críticos:</h2>",
        "<h2>Pendências críticas:</h2>",
        "<h2>Decisão sugerida:</h2>",
        "<h2>Suporte recomendado:</h2>",
        "<h2>Motivo objetivo:</h2>",
        "<h2>Conduta sugerida:</h2>",
    ]
    section_positions = [body.index(section) for section in section_order]
    assert section_positions == sorted(section_positions)
    assert "<li>Hb: 10.2</li>" in body
    assert "<li>Plaquetas: 140000</li>" in body
    assert "<li>INR: não informado</li>" in body
    assert "<li>ECG presente: nao</li>" in body
    assert "<li>ECG sinal de alerta: desconhecido</li>" in body
    assert "<li>Pré-check laboratório: sim</li>" in body
    assert "<li>Pré-check ECG: nao</li>" in body
    assert "<li>Pendências de laboratório: INR ausente</li>" in body
    assert "prechecagem_politica:" not in body
    assert "ecg.sinal de alerta=" not in body
    assert "<li>aceitar</li>" in body


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

    assert "idioma:" not in body
    assert "versao_schema:" not in body
    assert "caso:" not in body
    assert body.count("no. ocorrência: 12345") == 1
    assert body.count("paciente: JOSE") == 1
    assert "numero_registro: 12345" not in body


def test_build_room2_case_summary_message_limits_clinical_summary_to_two_to_four_lines() -> None:
    case_id = UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")
    summary_text = "Linha 1\nLinha 2\nLinha 3\nLinha 4\nLinha 5"

    body = build_room2_case_summary_message(
        case_id=case_id,
        agency_record_number="12345",
        patient_name="JOSE",
        structured_data={},
        summary_text=summary_text,
        suggested_action={"suggestion": "accept", "support_recommendation": "none"},
    )

    lines = _extract_markdown_section_lines(
        body=body,
        section="## Resumo clínico:\n\n",
        next_section="\n\n## Achados críticos:",
    )
    assert 2 <= len(lines) <= 4
    assert "Linha 1" in lines
    assert "Linha 4" in lines
    assert "Linha 5" not in lines


def test_build_room2_case_summary_formatted_html_keeps_two_to_four_paragraphs_in_summary() -> None:
    case_id = UUID("dddddddd-dddd-dddd-dddd-dddddddddddd")
    summary_text = "Resumo clínico curto para validação."

    body = build_room2_case_summary_formatted_html(
        case_id=case_id,
        agency_record_number="12345",
        patient_name="JOSE",
        structured_data={},
        summary_text=summary_text,
        suggested_action={"suggestion": "accept", "support_recommendation": "none"},
    )

    start = body.index("<h2>Resumo clínico:</h2>") + len("<h2>Resumo clínico:</h2>")
    end = body.index("<h2>Achados críticos:</h2>", start)
    summary_chunk = body[start:end]

    paragraph_count = summary_chunk.count("<p>")
    assert 2 <= paragraph_count <= 4


def test_room2_summary_decision_and_support_come_only_from_suggested_action_markdown() -> None:
    case_id = UUID("eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee")
    body = build_room2_case_summary_message(
        case_id=case_id,
        agency_record_number="12345",
        patient_name="JOSE",
        structured_data={
            "suggestion": "accept",
            "support_recommendation": "none",
            "policy_precheck": {"labs_pass": "yes"},
        },
        summary_text="Resumo clínico base",
        suggested_action={
            "suggestion": "deny",
            "support_recommendation": "anesthesist_icu",
            "confidence": "media",
        },
    )

    decision_lines = _extract_markdown_section_lines(
        body=body,
        section="## Decisão sugerida:\n\n",
        next_section="\n\n## Suporte recomendado:",
    )
    support_lines = _extract_markdown_section_lines(
        body=body,
        section="## Suporte recomendado:\n\n",
        next_section="\n\n## Motivo objetivo:",
    )
    assert decision_lines == ["- negar"]
    assert support_lines == ["- anestesista_uti"]
    assert "aceitar" not in "\n".join(decision_lines + support_lines)


def test_room2_summary_decision_and_support_come_only_from_suggested_action_html() -> None:
    case_id = UUID("ffffffff-ffff-ffff-ffff-ffffffffffff")
    body = build_room2_case_summary_formatted_html(
        case_id=case_id,
        agency_record_number="12345",
        patient_name="JOSE",
        structured_data={
            "suggestion": "accept",
            "support_recommendation": "none",
        },
        summary_text="Resumo clínico base",
        suggested_action={
            "suggestion": "deny",
            "support_recommendation": "anesthesist",
        },
    )

    decision_chunk = _extract_html_section_chunk(
        body=body,
        section="<h2>Decisão sugerida:</h2>",
        next_section="<h2>Suporte recomendado:</h2>",
    )
    support_chunk = _extract_html_section_chunk(
        body=body,
        section="<h2>Suporte recomendado:</h2>",
        next_section="<h2>Motivo objetivo:</h2>",
    )

    assert "<li>negar</li>" in decision_chunk
    assert "<li>anestesista</li>" in support_chunk
    assert "aceitar" not in decision_chunk + support_chunk


def test_room2_summary_objective_reason_is_short_and_coherent_markdown() -> None:
    case_id = UUID("12121212-1212-1212-1212-121212121212")
    long_reason = (
        "Paciente com múltiplas comorbidades e necessidade de revisão laboratorial detalhada "
        "antes do procedimento endoscópico para reduzir risco perioperatório em cenário de "
        "instabilidade clínica potencial."
    )
    body = build_room2_case_summary_message(
        case_id=case_id,
        agency_record_number="12345",
        patient_name="JOSE",
        structured_data={},
        summary_text="Resumo clínico base",
        suggested_action={
            "suggestion": "deny",
            "support_recommendation": "anesthesist_icu",
            "rationale": {"short_reason": long_reason},
        },
    )

    reason_lines = _extract_markdown_section_lines(
        body=body,
        section="## Motivo objetivo:\n\n",
        next_section="\n\n## Conduta sugerida:",
    )
    reason_text = "\n".join(reason_lines)

    assert 1 <= len(reason_lines) <= 2
    assert "negar" in reason_text
    assert "anestesista_uti" in reason_text


def test_room2_summary_critical_sections_use_nao_informado_fallback() -> None:
    case_id = UUID("abababab-abab-abab-abab-abababababab")
    body = build_room2_case_summary_message(
        case_id=case_id,
        agency_record_number="12345",
        patient_name="JOSE",
        structured_data={},
        summary_text="Resumo clínico base",
        suggested_action={"suggestion": "accept", "support_recommendation": "none"},
    )

    findings_lines = _extract_markdown_section_lines(
        body=body,
        section="## Achados críticos:\n\n",
        next_section="\n\n## Pendências críticas:",
    )
    pending_lines = _extract_markdown_section_lines(
        body=body,
        section="## Pendências críticas:\n\n",
        next_section="\n\n## Decisão sugerida:",
    )

    assert findings_lines == [
        "- Hb: não informado",
        "- Plaquetas: não informado",
        "- INR: não informado",
        "- ECG presente: não informado",
        "- ECG sinal de alerta: não informado",
    ]
    assert pending_lines == [
        "- Pré-check laboratório: não informado",
        "- Pré-check ECG: não informado",
        "- Pendências de laboratório: não informado",
    ]


def test_room2_summary_includes_emergent_priority_phrase_for_bleeding_with_instability() -> None:
    case_id = UUID("56565656-5656-5656-5656-565656565656")
    body = build_room2_case_summary_message(
        case_id=case_id,
        agency_record_number="12345",
        patient_name="JOSE",
        structured_data={
            "eda": {"indication_category": "bleeding"},
            "policy_precheck": {
                "notes": "Paciente com hipotensão importante e instabilidade hemodinâmica.",
            },
        },
        summary_text="Paciente com hematêmese e PA 79/53 em sala vermelha.",
        suggested_action={"suggestion": "accept", "support_recommendation": "anesthesist_icu"},
    )

    conduct_lines = _extract_markdown_section_lines(
        body=body,
        section="## Conduta sugerida:\n\n",
        next_section=None,
    )
    assert any("PRIORIDADE EMERGENTE" in line for line in conduct_lines)


def test_room2_summary_does_not_include_emergent_priority_phrase_without_instability() -> None:
    case_id = UUID("78787878-7878-7878-7878-787878787878")
    body = build_room2_case_summary_message(
        case_id=case_id,
        agency_record_number="12345",
        patient_name="JOSE",
        structured_data={"eda": {"indication_category": "dyspepsia"}},
        summary_text="Paciente estável em investigação eletiva.",
        suggested_action={"suggestion": "accept", "support_recommendation": "none"},
    )

    conduct_lines = _extract_markdown_section_lines(
        body=body,
        section="## Conduta sugerida:\n\n",
        next_section=None,
    )
    assert all("PRIORIDADE EMERGENTE" not in line for line in conduct_lines)


def test_room2_summary_conduct_targets_three_bullets_by_default() -> None:
    case_id = UUID("90909090-9090-9090-9090-909090909090")
    body = build_room2_case_summary_message(
        case_id=case_id,
        agency_record_number="12345",
        patient_name="JOSE",
        structured_data={"eda": {"indication_category": "dyspepsia"}},
        summary_text="Caso estável, sem urgência imediata.",
        suggested_action={"suggestion": "accept", "support_recommendation": "none"},
    )

    conduct_lines = _extract_markdown_section_lines(
        body=body,
        section="## Conduta sugerida:\n\n",
        next_section=None,
    )
    assert len(conduct_lines) == 3


def test_room2_summary_conduct_has_max_four_bullets_with_emergent_priority() -> None:
    case_id = UUID("91919191-9191-9191-9191-919191919191")
    body = build_room2_case_summary_message(
        case_id=case_id,
        agency_record_number="12345",
        patient_name="JOSE",
        structured_data={
            "eda": {"indication_category": "bleeding"},
            "policy_precheck": {"notes": "Instabilidade hemodinâmica e hipotensão."},
        },
        summary_text="Paciente com melena e PAS 80, instável.",
        suggested_action={"suggestion": "deny", "support_recommendation": "anesthesist_icu"},
    )

    conduct_lines = _extract_markdown_section_lines(
        body=body,
        section="## Conduta sugerida:\n\n",
        next_section=None,
    )
    assert len(conduct_lines) <= 4
    assert len(conduct_lines) >= 3


def test_room2_summary_objective_reason_is_short_and_coherent_html() -> None:
    case_id = UUID("34343434-3434-3434-3434-343434343434")
    body = build_room2_case_summary_formatted_html(
        case_id=case_id,
        agency_record_number="12345",
        patient_name="JOSE",
        structured_data={},
        summary_text="Resumo clínico base",
        suggested_action={
            "suggestion": "accept",
            "support_recommendation": "anesthesist",
            "rationale": {"short_reason": "Apto com suporte especializado."},
        },
    )

    reason_chunk = _extract_html_section_chunk(
        body=body,
        section="<h2>Motivo objetivo:</h2>",
        next_section="<h2>Conduta sugerida:</h2>",
    )

    assert 1 <= reason_chunk.count("<li>") <= 2
    assert "aceitar" in reason_chunk
    assert "anestesista" in reason_chunk


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

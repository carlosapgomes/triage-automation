"""Matrix message templates for triage workflow posts."""

from __future__ import annotations

import json
from datetime import datetime
from html import escape
from uuid import UUID

# Case-id visibility contract across Room-1/2/3 builders:
# - structural: parser-bound templates must preserve `caso: <uuid>` line.
# - informational: UUID is not parser-critical and can be de-emphasized in UX copy.
STRUCTURAL_CASE_ID_TEMPLATE_BUILDERS: tuple[str, ...] = (
    "build_room2_case_decision_template_message",
    "build_room2_case_decision_template_formatted_html",
    "build_room2_decision_error_message",
    "build_room3_reply_template_message",
    "build_room3_invalid_format_reprompt",
)

INFORMATIONAL_CASE_ID_TEMPLATE_BUILDERS: tuple[str, ...] = (
    "build_room2_widget_message",
    "build_room2_case_pdf_message",
    "build_room2_case_pdf_formatted_html",
    "build_room2_case_pdf_attachment_filename",
    "build_room2_case_summary_message",
    "build_room2_case_summary_formatted_html",
    "build_room2_case_decision_instructions_message",
    "build_room2_case_decision_instructions_formatted_html",
    "build_room2_ack_message",
    "build_room2_decision_ack_message",
    "build_room3_request_message",
    "build_room3_ack_message",
    "build_room1_final_accepted_message",
    "build_room1_final_denied_triage_message",
    "build_room1_final_denied_appointment_message",
    "build_room1_final_failure_message",
)


def build_human_identification_block(
    *,
    agency_record_number: str | None,
    patient_name: str | None,
) -> str:
    """Build standardized human-readable identification lines for case messages."""

    record_value = _normalize_human_identification_value(agency_record_number)
    patient_value = _normalize_human_identification_value(patient_name)
    return f"no. ocorrência: {record_value}\npaciente: {patient_value}"


_PT_BR_KEY_MAP: dict[str, str] = {
    "agency_record_number": "numero_registro",
    "age": "idade",
    "asa": "asa",
    "bullet_points": "pontos",
    "cardiovascular_risk": "risco_cardiovascular",
    "case_id": "caso",
    "class": "classe",
    "confidence": "confianca",
    "details": "detalhes",
    "document_id": "documento",
    "ecg": "ecg",
    "abnormal_flag": "sinal de alerta",
    "ecg_ok": "ecg_ok",
    "ecg_present": "ecg_presente",
    "ecg_required": "ecg_obrigatorio",
    "eda": "eda",
    "excluded_from_eda_flow": "fora_fluxo_eda",
    "excluded_request": "solicitacao_excluida",
    "exclusion_reason": "motivo_exclusao",
    "exclusion_type": "tipo_exclusao",
    "extraction_quality": "qualidade_extracao",
    "foreign_body_suspected": "suspeita_corpo_estranho",
    "hb_g_dl": "hemoglobina_g_dl",
    "indication_category": "categoria_indicacao",
    "inr": "inr",
    "is_pediatric": "pediatrico",
    "labs": "laboratorio",
    "labs_failed_items": "itens_reprovados",
    "labs_ok": "laboratorio_ok",
    "labs_pass": "laboratorio_aprovado",
    "labs_required": "laboratorio_obrigatorio",
    "language": "idioma",
    "level": "nivel",
    "missing_fields": "campos_ausentes",
    "missing_info_questions": "perguntas_faltantes",
    "name": "nome",
    "notes": "notas",
    "one_liner": "uma_linha",
    "patient": "paciente",
    "pediatric_flag": "é pediátrico?",
    "platelets_per_mm3": "plaquetas_mm3",
    "policy_alignment": "alinhamento_politica",
    "policy_precheck": "prechecagem_politica",
    "rationale": "justificativa",
    "reason": "motivo",
    "report_present": "laudo_presente",
    "requested_procedure": "procedimento_solicitado",
    "schema_version": "versao_schema",
    "sex": "sexo",
    "short_reason": "motivo_curto",
    "source_text_hint": "fonte_texto",
    "suggestion": "sugestao",
    "support_recommendation": "recomendacao_suporte",
    "summary": "resumo_estruturado",
    "urgency": "urgencia",
}


def _normalize_human_identification_value(value: str | None) -> str:
    normalized = (value or "").strip()
    if not normalized:
        return "não detectado"
    return normalized


def _build_human_identification_html(
    *,
    agency_record_number: str | None,
    patient_name: str | None,
) -> str:
    record_value = _normalize_human_identification_value(agency_record_number)
    patient_value = _normalize_human_identification_value(patient_name)
    return (
        f"<p>no. ocorrência: {escape(record_value)}</p>"
        f"<p>paciente: {escape(patient_value)}</p>"
    )


def _build_human_identification_html_multiline(
    *,
    agency_record_number: str | None,
    patient_name: str | None,
) -> str:
    record_value = _normalize_human_identification_value(agency_record_number)
    patient_value = _normalize_human_identification_value(patient_name)
    return (
        "<p>"
        f"no. ocorrência: {escape(record_value)}<br>"
        f"paciente: {escape(patient_value)}"
        "</p>"
    )


def build_room2_widget_message(
    *,
    case_id: UUID,
    agency_record_number: str,
    patient_name: str | None = None,
    widget_launch_url: str,
    payload: dict[str, object],
) -> str:
    """Build Room-2 widget post body with embedded JSON payload."""

    payload_json = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
    identification_block = build_human_identification_block(
        agency_record_number=agency_record_number,
        patient_name=patient_name,
    )
    return (
        "Solicitação de triagem\n"
        f"{identification_block}\n\n"
        f"Abra o widget de decisão: {widget_launch_url}\n\n"
        "Payload do widget:\n"
        f"```json\n{payload_json}\n```"
    )


def build_room2_case_pdf_message(
    *,
    case_id: UUID,
    agency_record_number: str,
    patient_name: str | None = None,
    extracted_text: str,
) -> str:
    """Build Room-2 message I body with concise context plus PDF attachment guidance."""
    _ = extracted_text

    identification_block = build_human_identification_block(
        agency_record_number=agency_record_number,
        patient_name=patient_name,
    )
    return (
        "# Solicitação de triagem - contexto original\n\n"
        f"{identification_block}\n\n"
        "O PDF original do relatório foi anexado como resposta a esta mensagem."
    )


def build_room2_case_pdf_formatted_html(
    *,
    case_id: UUID,
    agency_record_number: str,
    patient_name: str | None = None,
    extracted_text: str,
) -> str:
    """Build Room-2 message I HTML payload with concise PDF attachment guidance."""
    _ = extracted_text

    identification_html = _build_human_identification_html(
        agency_record_number=agency_record_number,
        patient_name=patient_name,
    )
    return (
        "<h1>Solicitação de triagem - contexto original</h1>"
        f"{identification_html}"
        "<p>O PDF original do relatório foi anexado como resposta a esta mensagem.</p>"
    )


def build_room2_case_pdf_attachment_filename(
    *,
    case_id: UUID,
    agency_record_number: str | None = None,
) -> str:
    """Build deterministic Room-2 original report PDF attachment filename."""

    record_slug = _normalize_record_number_for_filename(agency_record_number)
    return f"ocorrencia-{record_slug}-caso-{case_id}-relatorio-original.pdf"


def build_room2_case_summary_message(
    *,
    case_id: UUID,
    agency_record_number: str | None = None,
    patient_name: str | None = None,
    structured_data: dict[str, object],
    summary_text: str,
    suggested_action: dict[str, object],
) -> str:
    """Build Room-2 message II body using markdown-like section headings."""

    translated_structured = _translate_keys_to_portuguese(value=structured_data)
    translated_suggestion = _translate_keys_to_portuguese(value=suggested_action)
    compact_structured, compact_suggestion = _prune_redundant_summary_fields(
        structured_data=translated_structured,
        suggested_action=translated_suggestion,
    )
    structured_lines = _format_compact_markdown_lines(compact_structured)
    suggestion_lines = _format_compact_markdown_lines(compact_suggestion)
    structured_block = "\n".join(structured_lines)
    suggestion_block = "\n".join(suggestion_lines)
    identification_block = build_human_identification_block(
        agency_record_number=agency_record_number,
        patient_name=patient_name,
    )
    return (
        "# Resumo técnico da triagem\n\n"
        f"{identification_block}\n\n"
        "## Resumo clínico:\n\n"
        f"{summary_text}\n\n"
        "## Dados extraídos:\n\n"
        f"{structured_block}\n\n"
        "## Recomendação do sistema:\n\n"
        f"{suggestion_block}"
    )


def build_room2_case_summary_formatted_html(
    *,
    case_id: UUID,
    agency_record_number: str | None = None,
    patient_name: str | None = None,
    structured_data: dict[str, object],
    summary_text: str,
    suggested_action: dict[str, object],
) -> str:
    """Build Room-2 message II HTML payload for Matrix formatted_body rendering."""

    translated_structured = _translate_keys_to_portuguese(value=structured_data)
    translated_suggestion = _translate_keys_to_portuguese(value=suggested_action)
    compact_structured, compact_suggestion = _prune_redundant_summary_fields(
        structured_data=translated_structured,
        suggested_action=translated_suggestion,
    )
    structured_lines = _format_compact_markdown_lines(compact_structured)
    suggestion_lines = _format_compact_markdown_lines(compact_suggestion)

    summary_html = _format_paragraphs_html(summary_text)
    structured_html = _format_markdown_lines_html(structured_lines)
    suggestion_html = _format_markdown_lines_html(suggestion_lines)
    identification_html = _build_human_identification_html(
        agency_record_number=agency_record_number,
        patient_name=patient_name,
    )
    return (
        "<h1>Resumo técnico da triagem</h1>"
        f"{identification_html}"
        "<h2>Resumo clínico:</h2>"
        f"{summary_html}"
        "<h2>Dados extraídos:</h2>"
        f"{structured_html}"
        "<h2>Recomendação do sistema:</h2>"
        f"{suggestion_html}"
    )


def _translate_keys_to_portuguese(*, value: object) -> object:
    if isinstance(value, dict):
        translated: dict[str, object] = {}
        for key, nested in value.items():
            source_key = str(key)
            translated_key = _PT_BR_KEY_MAP.get(source_key, source_key)
            translated[translated_key] = _translate_keys_to_portuguese(value=nested)
        return translated
    if isinstance(value, list):
        return [_translate_keys_to_portuguese(value=item) for item in value]
    return value


def _format_markdown_lines(value: object) -> list[str]:
    if not isinstance(value, dict):
        return [f"- {_format_scalar(value)}"]

    top_level: dict[str, object] = {str(k): v for k, v in value.items()}
    if not top_level:
        return ["- (vazio)"]

    lines: list[str] = []
    for top_key in sorted(top_level):
        top_value = top_level[top_key]
        if isinstance(top_value, dict):
            lines.append(f"### {top_key}:")
            second_level: dict[str, object] = {str(k): v for k, v in top_value.items()}
            if not second_level:
                lines.append("- (vazio)")
                continue
            for second_key in sorted(second_level):
                second_value = second_level[second_key]
                lines.append(f"- {second_key}: {_format_compact_value(second_value)}")
            continue
        lines.append(f"- {top_key}: {_format_compact_value(top_value)}")
    return lines


def _format_compact_markdown_lines(value: object) -> list[str]:
    """Format dict payload using compact one-line-per-section representation."""

    if not isinstance(value, dict):
        return [f"- {_format_scalar(value)}"]

    top_level: dict[str, object] = {str(k): v for k, v in value.items()}
    if not top_level:
        return ["- (vazio)"]

    lines: list[str] = []
    for top_key in sorted(top_level):
        top_value = top_level[top_key]
        if isinstance(top_value, dict):
            flat_parts = _flatten_dict_pairs(top_value)
            if not flat_parts:
                lines.append(f"- {top_key}: (vazio)")
                continue
            lines.append(f"- {top_key}: {'; '.join(flat_parts)}")
            continue
        lines.append(f"- {top_key}: {_format_compact_value(top_value)}")
    return lines


def _format_paragraphs_html(value: str) -> str:
    stripped_lines = [line.strip() for line in value.splitlines() if line.strip()]
    if not stripped_lines:
        return "<p>(vazio)</p>"
    return "".join(f"<p>{escape(line)}</p>" for line in stripped_lines)


def _format_markdown_lines_html(lines: list[str]) -> str:
    html_parts: list[str] = []
    in_list = False

    for line in lines:
        content = line.strip()
        if not content:
            if in_list:
                html_parts.append("</ul>")
                in_list = False
            continue

        if content.startswith("### "):
            if in_list:
                html_parts.append("</ul>")
                in_list = False
            html_parts.append(f"<h3>{escape(content[4:])}</h3>")
            continue

        if content.startswith("- "):
            if not in_list:
                html_parts.append("<ul>")
                in_list = True
            html_parts.append(f"<li>{escape(content[2:])}</li>")
            continue

        if in_list:
            html_parts.append("</ul>")
            in_list = False
        html_parts.append(f"<p>{escape(content)}</p>")

    if in_list:
        html_parts.append("</ul>")

    if not html_parts:
        return "<p>(vazio)</p>"
    return "".join(html_parts)


def _format_compact_value(value: object) -> str:
    if isinstance(value, dict):
        nested: dict[str, object] = {str(k): v for k, v in value.items()}
        if not nested:
            return "(vazio)"
        parts = [f"{key}={_format_compact_value(nested[key])}" for key in sorted(nested)]
        return "; ".join(parts)
    if isinstance(value, list):
        if not value:
            return "(vazio)"
        return ", ".join(_format_compact_value(item) for item in value)
    return _format_scalar(value)


def _format_scalar(value: object) -> str:
    if value is None:
        return "(vazio)"
    if isinstance(value, bool):
        return "sim" if value else "nao"
    if isinstance(value, str):
        if not value:
            return "(vazio)"
        return _map_presentation_value(value)
    return str(value)


def _flatten_dict_pairs(value: dict[str, object], prefix: str = "") -> list[str]:
    """Flatten nested dict into key path pairs preserving all leaf values."""

    if not value:
        return []

    pairs: list[str] = []
    for key in sorted(value):
        nested = value[key]
        key_path = f"{prefix}.{key}" if prefix else key
        if isinstance(nested, dict):
            nested_pairs = _flatten_dict_pairs(
                {str(inner_key): inner_value for inner_key, inner_value in nested.items()},
                prefix=key_path,
            )
            if nested_pairs:
                pairs.extend(nested_pairs)
                continue
            pairs.append(f"{key_path}=(vazio)")
            continue
        pairs.append(f"{key_path}={_format_compact_value(nested)}")
    return pairs


def _prune_redundant_summary_fields(
    *,
    structured_data: object,
    suggested_action: object,
) -> tuple[object, object]:
    """Remove redundant metadata fields to reduce vertical payload size."""

    if not isinstance(structured_data, dict) or not isinstance(suggested_action, dict):
        return structured_data, suggested_action

    shared_drop_keys = {"idioma", "versao_schema"}
    structured_clean = {
        str(key): value
        for key, value in structured_data.items()
        if str(key) not in shared_drop_keys
    }
    suggestion_clean = {
        str(key): value
        for key, value in suggested_action.items()
        if str(key) not in shared_drop_keys | {"caso"}
    }

    structured_record = structured_clean.get("numero_registro")
    if (
        "numero_registro" in suggestion_clean
        and suggestion_clean.get("numero_registro") == structured_record
    ):
        suggestion_clean.pop("numero_registro", None)

    return structured_clean, suggestion_clean


def build_room2_case_decision_instructions_message(
    *,
    case_id: UUID,
    agency_record_number: str | None = None,
    patient_name: str | None = None,
) -> str:
    """Build Room-2 guidance message that points doctors to the copy template."""

    identification_block = build_human_identification_block(
        agency_record_number=agency_record_number,
        patient_name=patient_name,
    )
    return (
        "# Instrução de decisão médica\n\n"
        f"{identification_block}\n\n"
        "1. Copie a PRÓXIMA mensagem (modelo puro).\n"
        "2. Responda como resposta a ela, preenchendo os campos.\n"
        "3. Mantenha exatamente uma linha por campo.\n\n"
        "Regras:\n"
        "- Pode usar com ou sem espaço após ':' (ex.: decisão:aceitar)\n"
        "- decisão=negar exige suporte=nenhum\n"
        "- valores válidos: decisão=aceitar|negar; suporte=nenhum|anestesista|anestesista_uti\n"
        "- Não adicione linhas fora do modelo\n"
        "- Use a mensagem de modelo para preencher o campo de caso"
    )


def build_room2_case_decision_instructions_formatted_html(
    *,
    case_id: UUID,
    agency_record_number: str | None = None,
    patient_name: str | None = None,
) -> str:
    """Build Room-2 guidance HTML payload that points doctors to template message."""

    identification_html = _build_human_identification_html_multiline(
        agency_record_number=agency_record_number,
        patient_name=patient_name,
    )
    return (
        "<h1>Instrução de decisão médica</h1>"
        f"{identification_html}"
        "<ol>"
        "<li>Copie a <strong>PRÓXIMA mensagem</strong> (modelo puro).</li>"
        "<li>Responda como resposta a ela, preenchendo os campos.</li>"
        "<li>Mantenha exatamente uma linha por campo.</li>"
        "</ol>"
        "<h2>Regras:</h2>"
        "<ul>"
        "<li>Pode usar com ou sem espaço após ':' (ex.: decisão:aceitar)</li>"
        "<li>decisão=negar exige suporte=nenhum</li>"
        "<li>valores válidos: decisão=aceitar|negar; "
        "suporte=nenhum|anestesista|anestesista_uti</li>"
        "<li>Não adicione linhas fora do modelo</li>"
        "<li>Use a mensagem de modelo para preencher o campo de caso</li>"
        "</ul>"
    )


def build_room2_case_decision_template_message(*, case_id: UUID) -> str:
    """Build Room-2 pure template message intended for doctor copy/paste reply."""

    return (
        "decisao: aceitar\n"
        "suporte: nenhum\n"
        "motivo: (opcional)\n"
        f"caso: {case_id}"
    )


def build_room2_case_decision_template_formatted_html(*, case_id: UUID) -> str:
    """Build Room-2 pure template HTML payload without code fencing."""

    case_value = escape(str(case_id))
    return (
        "<p>"
        "decisao: aceitar<br>"
        "suporte: nenhum<br>"
        "motivo: (opcional)<br>"
        f"caso: {case_value}"
        "</p>"
    )


def build_room2_ack_message(
    *,
    case_id: UUID,
    agency_record_number: str | None = None,
    patient_name: str | None = None,
) -> str:
    """Build Room-2 ack body used as audit-only reaction target."""

    identification_block = build_human_identification_block(
        agency_record_number=agency_record_number,
        patient_name=patient_name,
    )
    return f"Triagem registrada\n{identification_block}\nReaja com +1 para confirmar."


def build_room2_decision_ack_message(
    *,
    case_id: UUID,
    decision: str,
    support_flag: str,
    reason: str | None,
    agency_record_number: str | None = None,
    patient_name: str | None = None,
) -> str:
    """Build Room-2 post-decision acknowledgment body for doctor reaction."""

    reason_value = reason or ""
    decision_label = _format_decision_value(decision)
    support_label = _format_support_value(support_flag)
    identification_block = build_human_identification_block(
        agency_record_number=agency_record_number,
        patient_name=patient_name,
    )
    return (
        "resultado: sucesso\n"
        f"{identification_block}\n"
        f"decisao: {decision_label}\n"
        f"suporte: {support_label}\n"
        f"motivo: {reason_value}\n"
        "Reaja com +1 para confirmar ciência do encerramento."
    )


def build_room2_decision_error_message(*, case_id: UUID, error_code: str) -> str:
    """Build deterministic Room-2 decision error feedback with correction guidance."""

    guidance = _room2_decision_error_guidance(error_code=error_code)
    return (
        "resultado: erro\n"
        f"caso: {case_id}\n"
        f"codigo_erro: {error_code}\n"
        f"acao: {guidance}\n\n"
        "Modelo obrigatório:\n"
        "decisao: aceitar|negar\n"
        "suporte: nenhum|anestesista|anestesista_uti\n"
        "motivo: <texto livre ou vazio>\n"
        f"caso: {case_id}"
    )


def _room2_decision_error_guidance(*, error_code: str) -> str:
    if error_code == "invalid_template":
        return "Responda novamente como resposta usando exatamente o modelo."
    if error_code == "authorization_failed":
        return "Apenas membros autorizados da Room-2 podem decidir; verifique acesso."
    if error_code == "state_conflict":
        return "Caso não está aguardando decisão médica; não reenvie decisão duplicada."
    return "Revise o modelo e tente novamente."


def _format_decision_value(value: str) -> str:
    if value == "accept":
        return "aceitar"
    if value == "deny":
        return "negar"
    return value


def _format_support_value(value: str) -> str:
    if value == "none":
        return "nenhum"
    if value == "anesthesist":
        return "anestesista"
    if value == "anesthesist_icu":
        return "anestesista_uti"
    return value


def _map_presentation_value(value: str) -> str:
    mapping = {
        "accept": "aceitar",
        "deny": "negar",
        "none": "nenhum",
        "anesthesist": "anestesista",
        "anesthesist_icu": "anestesista_uti",
        "yes": "sim",
        "no": "nao",
        "unknown": "desconhecido",
        "bleeding": "sangramento",
        "moderate": "moderado",
        "low": "baixo",
        "high": "alto",
    }
    return mapping.get(value, value)


def build_room3_request_message(
    *,
    case_id: UUID,
    agency_record_number: str | None,
    patient_name: str | None,
    patient_age: str | None,
    requested_exam: str | None,
) -> str:
    """Build Room-3 guidance message that points scheduler to copy template."""

    _ = case_id
    identification_block = build_human_identification_block(
        agency_record_number=agency_record_number,
        patient_name=patient_name,
    )
    details_block = _build_room3_details_block(
        patient_age=patient_age,
        requested_exam=requested_exam,
    )
    return (
        "Solicitacao de agendamento\n\n"
        f"{identification_block}\n"
        f"{details_block}\n\n"
        "1. Copie a PROXIMA mensagem (modelo puro).\n"
        "2. Responda como resposta a ela, preenchendo os campos.\n"
        "3. Mantenha exatamente uma linha por campo.\n\n"
        "Regras:\n"
        "- status=confirmado exige data_hora, local e instrucoes preenchidos\n"
        "- status=negado usa motivo opcional"
    )


def _format_room3_context_value(value: str | None) -> str:
    normalized = (value or "").strip()
    if not normalized:
        return "(vazio)"
    return normalized


def build_room3_reply_template_message(
    *,
    case_id: UUID,
    agency_record_number: str | None = None,
    patient_name: str | None = None,
) -> str:
    """Build Room-3 pure scheduler template message for copy/paste reply."""

    identification_block = build_human_identification_block(
        agency_record_number=agency_record_number,
        patient_name=patient_name,
    )
    return (
        f"{identification_block}\n"
        "status: confirmado\n"
        "data_hora: DD-MM-YYYY HH:MM BRT\n"
        "local:\n"
        "instrucoes:\n"
        "motivo: (opcional; usado quando status=negado)\n"
        f"caso: {case_id}"
    )


def build_room3_ack_message(
    *,
    case_id: UUID,
    agency_record_number: str | None,
    patient_name: str | None,
    patient_age: str | None,
    requested_exam: str | None,
) -> str:
    """Build Room-3 ack body used as audit-only reaction target."""

    _ = case_id
    identification_block = build_human_identification_block(
        agency_record_number=agency_record_number,
        patient_name=patient_name,
    )
    details_block = _build_room3_details_block(
        patient_age=patient_age,
        requested_exam=requested_exam,
    )
    return (
        "Solicitacao de agendamento registrada\n"
        f"{identification_block}\n"
        f"{details_block}\n"
        "Reaja com +1 para confirmar."
    )


def build_room3_invalid_format_reprompt(
    *,
    case_id: UUID,
    agency_record_number: str | None = None,
    patient_name: str | None = None,
) -> str:
    """Build strict Room-3 reformat prompt for invalid scheduler replies."""

    identification_block = build_human_identification_block(
        agency_record_number=agency_record_number,
        patient_name=patient_name,
    )
    return (
        "Nao consegui interpretar sua resposta para este caso.\n\n"
        f"{identification_block}\n\n"
        "Copie o modelo abaixo, preencha os campos e responda nesta mensagem.\n\n"
        "status: confirmado|negado\n"
        "data_hora: DD-MM-YYYY HH:MM BRT\n"
        "local:\n"
        "instrucoes:\n"
        "motivo: (opcional; usado quando status=negado)\n"
        f"caso: {case_id}"
    )


def build_room1_final_accepted_message(
    *,
    case_id: UUID,
    agency_record_number: str | None,
    patient_name: str | None,
    patient_age: str | None,
    requested_exam: str | None,
    appointment_at: datetime,
    location: str,
    instructions: str,
) -> str:
    """Build Room-1 accepted final reply template."""

    context_block = _build_case_context_block(
        case_id=case_id,
        agency_record_number=agency_record_number,
        patient_name=patient_name,
        patient_age=patient_age,
        requested_exam=requested_exam,
    )
    return (
        "✅ aceito\n"
        f"{context_block}\n"
        f"agendamento: {appointment_at.strftime('%d-%m-%Y %H:%M')} BRT\n"
        f"local: {location}\n"
        f"instrucoes: {instructions}\n\n"
        "Reaja com +1 para confirmar ciência do encerramento."
    )


def build_room1_final_denied_triage_message(
    *,
    case_id: UUID,
    agency_record_number: str | None,
    patient_name: str | None,
    patient_age: str | None,
    requested_exam: str | None,
    reason: str,
) -> str:
    """Build Room-1 triage denied final reply template."""

    context_block = _build_case_context_block(
        case_id=case_id,
        agency_record_number=agency_record_number,
        patient_name=patient_name,
        patient_age=patient_age,
        requested_exam=requested_exam,
    )
    return (
        "❌ negado (triagem)\n"
        f"{context_block}\n"
        f"motivo: {reason}\n\n"
        "Reaja com +1 para confirmar ciência do encerramento."
    )


def build_room1_final_denied_appointment_message(
    *,
    case_id: UUID,
    agency_record_number: str | None,
    patient_name: str | None,
    patient_age: str | None,
    requested_exam: str | None,
    reason: str,
) -> str:
    """Build Room-1 appointment denied final reply template."""

    context_block = _build_case_context_block(
        case_id=case_id,
        agency_record_number=agency_record_number,
        patient_name=patient_name,
        patient_age=patient_age,
        requested_exam=requested_exam,
    )
    return (
        "❌ negado (agendamento)\n"
        f"{context_block}\n"
        f"motivo: {reason}\n\n"
        "Reaja com +1 para confirmar ciência do encerramento."
    )


def build_room1_final_failure_message(
    *,
    case_id: UUID,
    agency_record_number: str | None,
    patient_name: str | None,
    patient_age: str | None,
    requested_exam: str | None,
    cause: str,
    details: str,
) -> str:
    """Build Room-1 processing failed final reply template."""

    context_block = _build_case_context_block(
        case_id=case_id,
        agency_record_number=agency_record_number,
        patient_name=patient_name,
        patient_age=patient_age,
        requested_exam=requested_exam,
    )
    return (
        "⚠️ falha no processamento\n"
        f"{context_block}\n"
        f"causa: {cause}\n"
        f"detalhes: {details}\n\n"
        "Reaja com +1 para confirmar ciência do encerramento."
    )


def _build_case_context_block(
    *,
    case_id: UUID,
    agency_record_number: str | None,
    patient_name: str | None,
    patient_age: str | None,
    requested_exam: str | None,
) -> str:
    _ = case_id
    identification_block = build_human_identification_block(
        agency_record_number=agency_record_number,
        patient_name=patient_name,
    )
    details_block = _build_room3_details_block(
        patient_age=patient_age,
        requested_exam=requested_exam,
    )
    return (
        f"{identification_block}\n"
        f"{details_block}"
    )


def _build_room3_details_block(
    *,
    patient_age: str | None,
    requested_exam: str | None,
) -> str:
    return (
        f"idade: {_format_room3_context_value(patient_age)}\n"
        f"exame solicitado: {_format_room3_context_value(requested_exam)}"
    )


def _normalize_record_number_for_filename(value: str | None) -> str:
    normalized = (value or "").strip()
    if not normalized:
        return "indisponivel"
    slug_chars: list[str] = []
    for char in normalized:
        if char.isalnum():
            slug_chars.append(char.lower())
            continue
        slug_chars.append("-")
    slug = "".join(slug_chars).strip("-")
    if not slug:
        return "indisponivel"
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug

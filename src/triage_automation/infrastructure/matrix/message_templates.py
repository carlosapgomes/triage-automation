"""Matrix message templates for triage workflow posts."""

from __future__ import annotations

import json
import re
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
    recent_denial_context: dict[str, object] | None = None,
) -> str:
    """Build Room-2 message II body using markdown-like section headings."""

    _ = case_id, recent_denial_context
    summary_lines = _build_room2_clinical_summary_lines(summary_text)
    summary_block = "\n".join(summary_lines)
    findings_block = "\n".join(_build_room2_critical_findings_lines(structured_data))
    pending_block = "\n".join(_build_room2_critical_pending_lines(structured_data))
    decision_block = "\n".join(_build_room2_decision_lines(suggested_action))
    support_block = "\n".join(_build_room2_support_lines(suggested_action))
    reason_block = "\n".join(_build_room2_objective_reason_lines(suggested_action))
    conduct_block = "\n".join(
        _build_room2_conduct_lines(
            suggested_action=suggested_action,
            structured_data=structured_data,
            summary_text=summary_text,
        )
    )
    identification_block = build_human_identification_block(
        agency_record_number=agency_record_number,
        patient_name=patient_name,
    )
    return (
        "# Resumo técnico da triagem\n\n"
        f"{identification_block}\n\n"
        "## Resumo clínico:\n\n"
        f"{summary_block}\n\n"
        "## Achados críticos:\n\n"
        f"{findings_block}\n\n"
        "## Pendências críticas:\n\n"
        f"{pending_block}\n\n"
        "## Decisão sugerida:\n\n"
        f"{decision_block}\n\n"
        "## Suporte recomendado:\n\n"
        f"{support_block}\n\n"
        "## Motivo objetivo:\n\n"
        f"{reason_block}\n\n"
        "## Conduta sugerida:\n\n"
        f"{conduct_block}"
    )


def build_room2_case_summary_formatted_html(
    *,
    case_id: UUID,
    agency_record_number: str | None = None,
    patient_name: str | None = None,
    structured_data: dict[str, object],
    summary_text: str,
    suggested_action: dict[str, object],
    recent_denial_context: dict[str, object] | None = None,
) -> str:
    """Build Room-2 message II HTML payload for Matrix formatted_body rendering."""

    _ = case_id, recent_denial_context
    summary_html = _format_room2_clinical_summary_html(summary_text)
    findings_html = _format_markdown_lines_html(
        _build_room2_critical_findings_lines(structured_data)
    )
    pending_html = _format_markdown_lines_html(
        _build_room2_critical_pending_lines(structured_data)
    )
    decision_html = _format_markdown_lines_html(_build_room2_decision_lines(suggested_action))
    support_html = _format_markdown_lines_html(_build_room2_support_lines(suggested_action))
    reason_html = _format_markdown_lines_html(_build_room2_objective_reason_lines(suggested_action))
    conduct_html = _format_markdown_lines_html(
        _build_room2_conduct_lines(
            suggested_action=suggested_action,
            structured_data=structured_data,
            summary_text=summary_text,
        )
    )
    identification_html = _build_human_identification_html(
        agency_record_number=agency_record_number,
        patient_name=patient_name,
    )
    return (
        "<h1>Resumo técnico da triagem</h1>"
        f"{identification_html}"
        "<h2>Resumo clínico:</h2>"
        f"{summary_html}"
        "<h2>Achados críticos:</h2>"
        f"{findings_html}"
        "<h2>Pendências críticas:</h2>"
        f"{pending_html}"
        "<h2>Decisão sugerida:</h2>"
        f"{decision_html}"
        "<h2>Suporte recomendado:</h2>"
        f"{support_html}"
        "<h2>Motivo objetivo:</h2>"
        f"{reason_html}"
        "<h2>Conduta sugerida:</h2>"
        f"{conduct_html}"
    )


def _build_room2_clinical_summary_lines(summary_text: str) -> list[str]:
    """Normalize clinical summary into a deterministic concise 2-4 line block."""

    stripped_lines = [line.strip() for line in summary_text.splitlines() if line.strip()]
    if not stripped_lines:
        return [
            "Resumo clínico não informado.",
            "Consulte o relatório original para contexto clínico.",
        ]

    if len(stripped_lines) >= 2:
        return stripped_lines[:4]

    one_liner = stripped_lines[0]
    words = one_liner.split()
    if len(words) >= 4:
        midpoint = len(words) // 2
        first_half = " ".join(words[:midpoint]).strip()
        second_half = " ".join(words[midpoint:]).strip()
        if first_half and second_half:
            return [first_half, second_half]

    return [
        one_liner,
        f"Base clínica: {one_liner}",
    ]


def _format_room2_clinical_summary_html(summary_text: str) -> str:
    """Render normalized clinical summary lines as HTML paragraphs."""

    lines = _build_room2_clinical_summary_lines(summary_text)
    return "".join(f"<p>{escape(line)}</p>" for line in lines)


def _build_room2_critical_findings_lines(structured_data: dict[str, object]) -> list[str]:
    """Return concise critical findings section lines."""

    hb_value = _extract_room2_nested_value(structured_data, "eda", "labs", "hb_g_dl")
    platelets_value = _extract_room2_nested_value(
        structured_data,
        "eda",
        "labs",
        "platelets_per_mm3",
    )
    inr_value = _extract_room2_nested_value(structured_data, "eda", "labs", "inr")
    ecg_present_value = _extract_room2_nested_value(
        structured_data,
        "eda",
        "ecg",
        "report_present",
    )
    ecg_alert_value = _extract_room2_nested_value(
        structured_data,
        "eda",
        "ecg",
        "abnormal_flag",
    )
    return [
        f"- Hb: {_format_room2_value_or_fallback(hb_value)}",
        f"- Plaquetas: {_format_room2_value_or_fallback(platelets_value)}",
        f"- INR: {_format_room2_value_or_fallback(inr_value)}",
        f"- ECG presente: {_format_room2_value_or_fallback(ecg_present_value)}",
        f"- ECG sinal de alerta: {_format_room2_value_or_fallback(ecg_alert_value)}",
    ]


def _build_room2_critical_pending_lines(structured_data: dict[str, object]) -> list[str]:
    """Return concise critical pending section lines."""

    precheck_labs_pass = _extract_room2_nested_value(
        structured_data,
        "policy_precheck",
        "labs_pass",
    )
    precheck_ecg_present = _extract_room2_nested_value(
        structured_data,
        "policy_precheck",
        "ecg_present",
    )
    labs_failed_items = _extract_room2_nested_value(
        structured_data,
        "policy_precheck",
        "labs_failed_items",
    )

    failed_items_text = "não informado"
    if isinstance(labs_failed_items, list):
        normalized_items = [str(item).strip() for item in labs_failed_items if str(item).strip()]
        if normalized_items:
            failed_items_text = ", ".join(normalized_items)

    return [
        f"- Pré-check laboratório: {_format_room2_value_or_fallback(precheck_labs_pass)}",
        f"- Pré-check ECG: {_format_room2_value_or_fallback(precheck_ecg_present)}",
        f"- Pendências de laboratório: {failed_items_text}",
    ]


def _build_room2_decision_lines(
    suggested_action: dict[str, object],
) -> list[str]:
    """Return decision section lines based on reconciled suggestion payload."""

    suggestion = suggested_action.get("suggestion")
    if isinstance(suggestion, str):
        return [f"- {_format_scalar(suggestion)}"]
    return ["- não informado"]


def _build_room2_support_lines(suggested_action: dict[str, object]) -> list[str]:
    """Return support section lines based on reconciled suggestion payload."""

    support_recommendation = suggested_action.get("support_recommendation")
    if isinstance(support_recommendation, str):
        return [f"- {_format_scalar(support_recommendation)}"]
    return ["- não informado"]


def _build_room2_objective_reason_lines(suggested_action: dict[str, object]) -> list[str]:
    """Return concise objective reason section lines."""

    decision = suggested_action.get("suggestion")
    support_recommendation = suggested_action.get("support_recommendation")
    decision_label = (
        _format_scalar(decision)
        if isinstance(decision, str)
        else "não informado"
    )
    support_label = (
        _format_scalar(support_recommendation)
        if isinstance(support_recommendation, str)
        else "não informado"
    )

    reason = _extract_room2_short_reason(suggested_action)
    lines = [f"- Decisão {decision_label} com suporte {support_label}."]
    if reason:
        lines.append(f"- {_truncate_room2_reason_line(reason)}")
    return lines[:2]


def _extract_room2_short_reason(suggested_action: dict[str, object]) -> str | None:
    """Extract preferred short rationale text from reconciled suggestion payload."""

    rationale = suggested_action.get("rationale")
    if isinstance(rationale, str):
        normalized = rationale.strip()
        if normalized:
            return normalized
        return None
    if isinstance(rationale, dict):
        short_reason = rationale.get("short_reason")
        if isinstance(short_reason, str):
            normalized = short_reason.strip()
            if normalized:
                return normalized
    return None


def _truncate_room2_reason_line(reason: str, limit: int = 180) -> str:
    """Return normalized one-line reason text capped for concise objective display."""

    normalized = " ".join(reason.split())
    if len(normalized) <= limit:
        return normalized
    return f"{normalized[: limit - 1].rstrip()}…"


def _build_room2_conduct_lines(
    *,
    suggested_action: dict[str, object],
    structured_data: dict[str, object],
    summary_text: str,
) -> list[str]:
    """Return concise conduct section lines."""

    suggestion = suggested_action.get("suggestion")
    lines: list[str]
    if suggestion == "deny":
        lines = [
            "- Reavaliar após resolução das pendências críticas.",
            "- Priorizar coleta/validação dos exames pendentes críticos.",
            "- Consultar relatório completo para suporte à decisão.",
        ]
    else:
        lines = [
            "- Prosseguir conforme protocolo clínico local.",
            "- Confirmar pendências críticas antes do procedimento.",
            "- Reavaliar estabilidade clínica imediatamente antes da EDA.",
        ]

    if _should_include_room2_emergent_priority_phrase(
        structured_data=structured_data,
        summary_text=summary_text,
    ):
        lines.insert(
            0,
            (
                "- PRIORIDADE EMERGENTE: estabilizar hemodinamicamente e seguir via "
                "urgente sem atraso por pendências não críticas."
            ),
        )

    return lines[:4]


def _should_include_room2_emergent_priority_phrase(
    *,
    structured_data: dict[str, object],
    summary_text: str,
) -> bool:
    """Return True when case indicates bleeding with documented hemodynamic instability."""

    return _is_room2_bleeding_case(
        structured_data=structured_data,
        summary_text=summary_text,
    ) and _has_room2_documented_hemodynamic_instability(
        structured_data=structured_data,
        summary_text=summary_text,
    )


def _is_room2_bleeding_case(*, structured_data: dict[str, object], summary_text: str) -> bool:
    """Detect bleeding context by structured indicator or narrative keywords."""

    indication_category = _extract_room2_nested_value(structured_data, "eda", "indication_category")
    if isinstance(indication_category, str) and indication_category.strip().lower() == "bleeding":
        return True

    combined_text = " ".join(_collect_room2_context_texts(structured_data, summary_text)).lower()
    bleeding_markers = ("hematêmese", "hematemese", "melena", "hda", "hemorragia digestiva")
    return any(marker in combined_text for marker in bleeding_markers)


def _has_room2_documented_hemodynamic_instability(
    *,
    structured_data: dict[str, object],
    summary_text: str,
) -> bool:
    """Detect documented hemodynamic instability by keywords or low systolic values."""

    texts = _collect_room2_context_texts(structured_data, summary_text)
    combined_text = " ".join(texts).lower()
    keyword_markers = (
        "instabilidade hemodin",
        "hemodinamicamente inst",
        "choque",
        "hipotensão",
        "hipotensao",
        "hipovol",
    )
    if any(marker in combined_text for marker in keyword_markers):
        return True

    systolic_values = _extract_room2_systolic_values(combined_text)
    return any(value < 90 for value in systolic_values)


def _collect_room2_context_texts(
    structured_data: dict[str, object],
    summary_text: str,
) -> list[str]:
    """Collect free-text fields relevant for emergent-context detection."""

    texts: list[str] = []
    if summary_text.strip():
        texts.append(summary_text.strip())

    policy_notes = _extract_room2_nested_value(structured_data, "policy_precheck", "notes")
    if isinstance(policy_notes, str) and policy_notes.strip():
        texts.append(policy_notes.strip())

    return texts


def _extract_room2_systolic_values(text: str) -> list[int]:
    """Extract systolic blood-pressure values from common textual notations."""

    values: list[int] = []
    single_patterns = (
        r"\bpas\s*[:=]?\s*([0-9]{2,3})\b",
    )
    paired_patterns = (
        r"\bpa\s*[:=]?\s*([0-9]{2,3})\s*[x/]\s*([0-9]{2,3})\b",
        r"\bta\s*[:=]?\s*([0-9]{2,3})\s*[x/]\s*([0-9]{2,3})\b",
    )

    for pattern in single_patterns:
        for match in re.finditer(pattern, text):
            values.append(int(match.group(1)))

    for pattern in paired_patterns:
        for match in re.finditer(pattern, text):
            values.append(int(match.group(1)))

    return values


def _extract_room2_nested_value(payload: dict[str, object], *keys: str) -> object | None:
    """Return nested dictionary value by key path, or None when missing."""

    current: object = payload
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _format_room2_value_or_fallback(value: object | None) -> str:
    """Return human-readable scalar value with deterministic 'não informado' fallback."""

    if value is None:
        return "não informado"
    if isinstance(value, str):
        normalized = value.strip()
        if not normalized:
            return "não informado"
        return _map_presentation_value(normalized)
    if isinstance(value, bool):
        return "sim" if value else "nao"
    if isinstance(value, (int, float)):
        return str(value)
    return str(value)


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


def build_room2_case_decision_template_message(
    *,
    case_id: UUID,
    agency_record_number: str | None = None,
    patient_name: str | None = None,
) -> str:
    """Build strict Room-2 doctor reply template with human identification context."""

    identification_block = build_human_identification_block(
        agency_record_number=agency_record_number,
        patient_name=patient_name,
    )

    return (
        f"{identification_block}\n"
        "decisao: aceitar\n"
        "suporte: nenhum\n"
        "motivo: (opcional)\n"
        f"caso: {case_id}"
    )


def build_room2_case_decision_template_formatted_html(
    *,
    case_id: UUID,
    agency_record_number: str | None = None,
    patient_name: str | None = None,
) -> str:
    """Build strict Room-2 doctor reply template HTML payload without code fencing."""

    identification_block = build_human_identification_block(
        agency_record_number=agency_record_number,
        patient_name=patient_name,
    )
    identification_lines_html = "<br>".join(
        escape(line) for line in identification_block.splitlines()
    )
    case_value = escape(str(case_id))
    return (
        "<p>"
        f"{identification_lines_html}<br>"
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

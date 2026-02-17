"""Matrix message templates for triage workflow posts."""

from __future__ import annotations

import json
from datetime import datetime
from uuid import UUID

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


def build_room2_widget_message(
    *,
    case_id: UUID,
    agency_record_number: str,
    widget_launch_url: str,
    payload: dict[str, object],
) -> str:
    """Build Room-2 widget post body with embedded JSON payload."""

    payload_json = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
    return (
        "Solicitacao de triagem\n"
        f"caso: {case_id}\n"
        f"registro: {agency_record_number}\n\n"
        f"Abra o widget de decisao: {widget_launch_url}\n\n"
        "Payload do widget:\n"
        f"```json\n{payload_json}\n```"
    )


def build_room2_case_pdf_message(
    *,
    case_id: UUID,
    agency_record_number: str,
    extracted_text: str,
) -> str:
    """Build Room-2 message I body containing extracted original report text."""

    return (
        "Solicitacao de triagem - contexto original\n"
        f"caso: {case_id}\n"
        f"registro: {agency_record_number}\n"
        "Texto extraido do relatorio original:\n"
        f"{extracted_text}"
    )


def build_room2_case_summary_message(
    *,
    case_id: UUID,
    structured_data: dict[str, object],
    summary_text: str,
    suggested_action: dict[str, object],
) -> str:
    """Build Room-2 message II body in plain text with pt-BR field labels."""

    translated_structured = _translate_keys_to_portuguese(value=structured_data)
    translated_suggestion = _translate_keys_to_portuguese(value=suggested_action)
    structured_lines = _format_markdown_lines(translated_structured)
    suggestion_lines = _format_markdown_lines(translated_suggestion)
    structured_block = "\n".join(structured_lines)
    suggestion_block = "\n".join(suggestion_lines)
    return (
        "Resumo tecnico da triagem\n"
        f"caso: {case_id}\n\n"
        "Resumo clinico:\n"
        f"{summary_text}\n\n"
        "Dados extraidos (chaves em portugues):\n"
        f"{structured_block}\n\n"
        "Recomendacao do sistema (chaves em portugues):\n"
        f"{suggestion_block}"
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
            lines.append(f"- {top_key}:")
            second_level: dict[str, object] = {str(k): v for k, v in top_value.items()}
            if not second_level:
                lines.append("  - (vazio)")
                continue
            for second_key in sorted(second_level):
                second_value = second_level[second_key]
                lines.append(f"  - {second_key}: {_format_compact_value(second_value)}")
            continue
        lines.append(f"- {top_key}: {_format_compact_value(top_value)}")
    return lines


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


def build_room2_case_decision_instructions_message(*, case_id: UUID) -> str:
    """Build Room-2 message III body with strict doctor decision reply template."""

    return (
        "Instrucao de decisao medica\n"
        "Responda como resposta a mensagem raiz deste caso usando exatamente o modelo:\n\n"
        "decisao: aceitar|negar\n"
        "suporte: nenhum|anestesista|anestesista_uti\n"
        "motivo: <texto livre ou vazio>\n"
        f"caso: {case_id}\n\n"
        "Regras:\n"
        "- decisao=negar exige suporte=nenhum\n"
        "- Nao use texto fora do modelo"
    )


def build_room2_ack_message(*, case_id: UUID) -> str:
    """Build Room-2 ack body used as audit-only reaction target."""

    return f"Triagem registrada para o caso: {case_id}\nReaja com +1 para confirmar."


def build_room2_decision_ack_message(
    *,
    case_id: UUID,
    decision: str,
    support_flag: str,
    reason: str | None,
) -> str:
    """Build Room-2 post-decision acknowledgment body for doctor reaction."""

    reason_value = reason or ""
    decision_label = _format_decision_value(decision)
    support_label = _format_support_value(support_flag)
    return (
        "resultado: sucesso\n"
        f"caso: {case_id}\n"
        f"decisao: {decision_label}\n"
        f"suporte: {support_label}\n"
        f"motivo: {reason_value}\n"
        "Reaja com +1 para confirmar ciencia do encerramento."
    )


def build_room2_decision_error_message(*, case_id: UUID, error_code: str) -> str:
    """Build deterministic Room-2 decision error feedback with correction guidance."""

    guidance = _room2_decision_error_guidance(error_code=error_code)
    return (
        "resultado: erro\n"
        f"caso: {case_id}\n"
        f"codigo_erro: {error_code}\n"
        f"acao: {guidance}\n\n"
        "Modelo obrigatorio:\n"
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
        return "Caso nao esta aguardando decisao medica; nao reenviar decisao duplicada."
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


def build_room3_request_message(*, case_id: UUID) -> str:
    """Build Room-3 scheduling request body including strict reply instructions."""

    return (
        "Solicitacao de agendamento\n"
        "Responda usando um dos formatos estritos abaixo.\n\n"
        "Confirmado:\n"
        "DD-MM-YYYY HH:MM BRT\n"
        "local: <texto livre>\n"
        "instrucoes: <texto livre>\n"
        f"caso: {case_id}\n\n"
        "Negado:\n"
        "negado\n"
        "motivo: <texto livre opcional>\n"
        f"caso: {case_id}"
    )


def build_room3_ack_message(*, case_id: UUID) -> str:
    """Build Room-3 ack body used as audit-only reaction target."""

    return (
        f"Solicitacao de agendamento registrada para o caso: {case_id}\n"
        "Reaja com +1 para confirmar."
    )


def build_room3_invalid_format_reprompt(*, case_id: UUID) -> str:
    """Build strict Room-3 reformat prompt for invalid scheduler replies."""

    return (
        "Nao consegui interpretar sua resposta para este caso.\n\n"
        "Responda usando UM dos formatos abaixo (um campo por linha) e inclua a linha "
        "do caso.\n\n"
        "CONFIRMADO:\n"
        "DD-MM-YYYY HH:MM BRT\n"
        "local: ...\n"
        "instrucoes: ...\n"
        f"caso: {case_id}\n\n"
        "NEGADO:\n"
        "negado\n"
        "motivo: ...\n"
        f"caso: {case_id}"
    )


def build_room1_final_accepted_message(
    *,
    case_id: UUID,
    appointment_at: datetime,
    location: str,
    instructions: str,
) -> str:
    """Build Room-1 accepted final reply template."""

    return (
        "✅ aceito\n"
        f"agendamento: {appointment_at.strftime('%d-%m-%Y %H:%M')} BRT\n"
        f"local: {location}\n"
        f"instrucoes: {instructions}\n"
        f"caso: {case_id}"
    )


def build_room1_final_denied_triage_message(*, case_id: UUID, reason: str) -> str:
    """Build Room-1 triage denied final reply template."""

    return f"❌ negado (triagem)\nmotivo: {reason}\ncaso: {case_id}"


def build_room1_final_denied_appointment_message(*, case_id: UUID, reason: str) -> str:
    """Build Room-1 appointment denied final reply template."""

    return f"❌ negado (agendamento)\nmotivo: {reason}\ncaso: {case_id}"


def build_room1_final_failure_message(*, case_id: UUID, cause: str, details: str) -> str:
    """Build Room-1 processing failed final reply template."""

    return (
        "⚠️ falha no processamento\n"
        f"causa: {cause}\n"
        f"detalhes: {details}\n"
        f"caso: {case_id}"
    )

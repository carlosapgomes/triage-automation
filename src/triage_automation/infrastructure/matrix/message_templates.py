"""Matrix message templates for triage workflow posts."""

from __future__ import annotations

import json
from datetime import datetime
from typing import cast
from uuid import UUID

_PT_BR_KEY_MAP: dict[str, str] = {
    "agency_record_number": "numero_registro",
    "age": "idade",
    "asa": "asa",
    "bullet_points": "pontos",
    "cardiovascular_risk": "risco_cardiovascular",
    "case_id": "case_id",
    "class": "classe",
    "confidence": "confianca",
    "details": "detalhes",
    "document_id": "documento",
    "ecg": "ecg",
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
    "pediatric_flag": "flag_pediatrico",
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
        f"case_id: {case_id}\n"
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
        f"case_id: {case_id}\n\n"
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


def _format_markdown_lines(value: object, *, depth: int = 0) -> list[str]:
    indent = "  " * depth
    if isinstance(value, dict):
        dict_value = cast("dict[object, object]", value)
        if not dict_value:
            return [f"{indent}- (vazio)"]
        sorted_items = sorted(
            ((str(raw_key), nested) for raw_key, nested in dict_value.items()),
            key=lambda item: item[0],
        )
        lines: list[str] = []
        for key, nested in sorted_items:
            if isinstance(nested, (dict, list)):
                lines.append(f"{indent}- {key}:")
                lines.extend(_format_markdown_lines(nested, depth=depth + 1))
            else:
                lines.append(f"{indent}- {key}: {_format_scalar(nested)}")
        return lines

    if isinstance(value, list):
        if not value:
            return [f"{indent}- (vazio)"]
        lines = []
        for item in value:
            if isinstance(item, (dict, list)):
                lines.append(f"{indent}-")
                lines.extend(_format_markdown_lines(item, depth=depth + 1))
            else:
                lines.append(f"{indent}- {_format_scalar(item)}")
        return lines

    return [f"{indent}- {_format_scalar(value)}"]


def _format_scalar(value: object) -> str:
    if value is None:
        return "(vazio)"
    if isinstance(value, bool):
        return "sim" if value else "nao"
    if isinstance(value, str):
        return value if value else "(vazio)"
    return str(value)


def build_room2_case_decision_instructions_message(*, case_id: UUID) -> str:
    """Build Room-2 message III body with strict doctor decision reply template."""

    return (
        "Instrucao de decisao medica\n"
        "Responda como reply a mensagem raiz deste caso usando exatamente o template:\n\n"
        "decision: accept|deny\n"
        "support_flag: none|anesthesist|anesthesist_icu\n"
        "reason: <texto livre ou vazio>\n"
        f"case_id: {case_id}\n\n"
        "Regras:\n"
        "- decision=deny exige support_flag=none\n"
        "- Nao use texto fora do template"
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
    return (
        "resultado: sucesso\n"
        f"case_id: {case_id}\n"
        f"decision: {decision}\n"
        f"support_flag: {support_flag}\n"
        f"reason: {reason_value}\n"
        "Reaja com +1 para confirmar ciencia do encerramento."
    )


def build_room2_decision_error_message(*, case_id: UUID, error_code: str) -> str:
    """Build deterministic Room-2 decision error feedback with correction guidance."""

    guidance = _room2_decision_error_guidance(error_code=error_code)
    return (
        "resultado: erro\n"
        f"case_id: {case_id}\n"
        f"error_code: {error_code}\n"
        f"acao: {guidance}\n\n"
        "Template obrigatorio:\n"
        "decision: accept|deny\n"
        "support_flag: none|anesthesist|anesthesist_icu\n"
        "reason: <texto livre ou vazio>\n"
        f"case_id: {case_id}"
    )


def _room2_decision_error_guidance(*, error_code: str) -> str:
    if error_code == "invalid_template":
        return "Responda novamente como reply usando exatamente o template."
    if error_code == "authorization_failed":
        return "Apenas membros autorizados da Room-2 podem decidir; verifique acesso."
    if error_code == "state_conflict":
        return "Caso nao esta em WAIT_DOCTOR; nao reenviar decisao duplicada."
    return "Revise o template e tente novamente."


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

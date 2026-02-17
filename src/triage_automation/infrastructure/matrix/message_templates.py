"""Matrix message templates for triage workflow posts."""

from __future__ import annotations

import json
from datetime import datetime
from uuid import UUID


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
    pdf_mxc_url: str,
) -> str:
    """Build Room-2 message I body containing original PDF case context."""

    return (
        "Solicitacao de triagem - contexto original\n"
        f"case_id: {case_id}\n"
        f"registro: {agency_record_number}\n"
        "PDF original:\n"
        f"{pdf_mxc_url}"
    )


def build_room2_case_summary_message(
    *,
    case_id: UUID,
    structured_data: dict[str, object],
    summary_text: str,
    suggested_action: dict[str, object],
) -> str:
    """Build Room-2 message II body with extracted artifacts and recommendation."""

    structured_json = json.dumps(structured_data, ensure_ascii=False, indent=2, sort_keys=True)
    suggestion_json = json.dumps(suggested_action, ensure_ascii=False, indent=2, sort_keys=True)
    return (
        "Resumo tecnico da triagem\n"
        f"case_id: {case_id}\n\n"
        "Dados estruturados:\n"
        f"```json\n{structured_json}\n```\n\n"
        "Resumo:\n"
        f"{summary_text}\n\n"
        "Recomendacao:\n"
        f"```json\n{suggestion_json}\n```"
    )


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

"""FastAPI router for server-rendered monitoring dashboard pages."""

from __future__ import annotations

import json
import re
from datetime import date
from math import ceil
from pathlib import Path
from typing import Literal
from urllib.parse import urlencode
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from triage_automation.application.ports.case_repository_port import CaseMonitoringTimelineItem
from triage_automation.application.ports.user_repository_port import UserRecord
from triage_automation.application.services.access_guard_service import (
    RoleNotAuthorizedError,
    UnknownRoleAuthorizationError,
)
from triage_automation.application.services.case_monitoring_service import (
    CaseMonitoringListQuery,
    CaseMonitoringService,
    InvalidMonitoringPeriodError,
)
from triage_automation.domain.auth.roles import Role
from triage_automation.domain.case_status import CaseStatus
from triage_automation.infrastructure.http.auth_guard import (
    SESSION_COOKIE_NAME,
    InvalidAuthTokenError,
    MissingAuthTokenError,
    WidgetAuthGuard,
)
from triage_automation.infrastructure.http.shell_context import build_shell_context

_TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"
_CaseDetailViewMode = Literal["thread", "pure"]
_SCHEDULE_LABEL_RE = re.compile(
    r"(?im)^\s*(?:date[_ ]?time|data[_ ]?hora|data|date)\s*[:=]\s*(.+?)\s*$"
)
_SCHEDULE_ISO_RE = re.compile(r"\b\d{4}-\d{2}-\d{2}(?:[ T]\d{2}:\d{2})?\b")
_SCHEDULE_BR_RE = re.compile(r"\b\d{2}/\d{2}/\d{4}(?:\s+\d{2}:\d{2})?\b")


def build_dashboard_router(
    *,
    monitoring_service: CaseMonitoringService,
    auth_guard: WidgetAuthGuard,
) -> APIRouter:
    """Build router exposing Jinja2 server-rendered dashboard pages."""

    templates = Jinja2Templates(directory=str(_TEMPLATE_DIR))
    router = APIRouter(tags=["dashboard"])

    @router.get("/dashboard/cases", response_class=HTMLResponse)
    async def render_case_list_page(
        request: Request,
        page: int = Query(default=1, ge=1),
        page_size: int = Query(default=10, ge=1, le=15),
        status: str | None = None,
        from_date: date | None = None,
        to_date: date | None = None,
    ) -> Response:
        """Render dashboard list page with filters and paginated case rows."""

        authenticated_user = await _require_audit_user(auth_guard=auth_guard, request=request)
        if isinstance(authenticated_user, RedirectResponse):
            return authenticated_user
        status_filter = _parse_case_status_filter(status)
        try:
            result = await monitoring_service.list_cases(
                CaseMonitoringListQuery(
                    page=page,
                    page_size=page_size,
                    status=status_filter,
                    from_date=from_date,
                    to_date=to_date,
                )
            )
        except InvalidMonitoringPeriodError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        total_pages = max(1, ceil(result.total / result.page_size)) if result.page_size else 1
        prev_page = result.page - 1 if result.page > 1 else None
        next_page = result.page + 1 if result.page < total_pages else None

        shared_filters = {
            "status": status_filter.value if status_filter is not None else "",
            "from_date": from_date.isoformat() if from_date is not None else "",
            "to_date": to_date.isoformat() if to_date is not None else "",
            "page_size": result.page_size,
        }
        context = {
            **build_shell_context(
                page_title="Dashboard de Monitoramento",
                active_nav="dashboard",
                user=authenticated_user,
            ),
            "cases": result.items,
            "status_options": [value.value for value in CaseStatus],
            "filters": shared_filters,
            "pagination": {
                "page": result.page,
                "page_size": result.page_size,
                "total": result.total,
                "total_pages": total_pages,
                "prev_url": (
                    _build_cases_url(
                        page=prev_page,
                        page_size=result.page_size,
                        status=status_filter,
                        from_date=from_date,
                        to_date=to_date,
                    )
                    if prev_page is not None
                    else None
                ),
                "next_url": (
                    _build_cases_url(
                        page=next_page,
                        page_size=result.page_size,
                        status=status_filter,
                        from_date=from_date,
                        to_date=to_date,
                    )
                    if next_page is not None
                    else None
                ),
            },
        }

        if _is_unpoly_fragment_request(request):
            return templates.TemplateResponse(
                request=request,
                name="dashboard/partials/cases_list_fragment.html",
                context=context,
            )

        return templates.TemplateResponse(
            request=request,
            name="dashboard/cases_list.html",
            context=context,
        )

    @router.get("/dashboard/cases/{case_id}", response_class=HTMLResponse)
    async def render_case_detail_page(
        request: Request,
        case_id: UUID,
        view: str = Query(default="thread"),
    ) -> Response:
        """Render dashboard detail page with chronological timeline by case."""

        authenticated_user = await _require_audit_user(auth_guard=auth_guard, request=request)
        if isinstance(authenticated_user, RedirectResponse):
            return authenticated_user

        view_mode = _parse_case_detail_view_mode(view)
        can_view_full_content = authenticated_user.role is Role.ADMIN
        detail = await monitoring_service.get_case_detail(case_id=case_id)
        if detail is None:
            raise HTTPException(status_code=404, detail="case not found")

        timeline_rows: list[dict[str, object]] = []
        for item in detail.timeline:
            full_text = _extract_full_text(content_text=item.content_text, payload=item.payload)
            excerpt_text = _build_excerpt(full_text)
            timeline_rows.append(
                {
                    "timestamp": item.timestamp.isoformat(),
                    "source": item.source,
                    "source_badge_class": _source_badge_class(item.source),
                    "channel": item.channel,
                    "channel_badge_class": _channel_badge_class(item.channel),
                    "actor": item.actor or "system",
                    "event_type": _translate_event_type(item.event_type),
                    "event_badge_class": _event_badge_class(item.event_type),
                    "excerpt_text": excerpt_text,
                    "full_text": full_text if can_view_full_content else None,
                    "can_show_full_content": can_view_full_content,
                    "is_truncated": len(excerpt_text) < len(full_text),
                }
            )

        thread_sections = _build_thread_sections(detail.timeline)

        return templates.TemplateResponse(
            request=request,
            name="dashboard/case_detail.html",
            context={
                **build_shell_context(
                    page_title="Detalhe do Caso",
                    active_nav="dashboard",
                    user=authenticated_user,
                ),
                "case_id": str(case_id),
                "status": detail.status.value,
                "view_mode": view_mode,
                "timeline_rows": timeline_rows,
                "thread_sections": thread_sections,
                "patient_name": detail.patient_name,
                "agency_record_number": detail.agency_record_number,
            },
        )

    return router


def _is_unpoly_fragment_request(request: Request) -> bool:
    """Return whether request asks for a fragment-targeted Unpoly update."""

    return bool(request.headers.get("x-up-target"))


def _parse_case_detail_view_mode(raw_mode: str) -> _CaseDetailViewMode:
    """Parse and validate dashboard detail visualization mode query value."""

    normalized = raw_mode.strip().lower()
    if normalized in {"", "thread"}:
        return "thread"
    if normalized == "pure":
        return "pure"
    raise HTTPException(status_code=422, detail=f"invalid detail view mode: {raw_mode}")


def _build_thread_sections(
    timeline_items: list[CaseMonitoringTimelineItem],
) -> list[dict[str, object]]:
    """Build compact thread-view sections for Room-1/2/3 with summary nodes."""

    grouped: dict[str, list[dict[str, str | None]]] = {
        "room1": [],
        "room2": [],
        "room3": [],
    }
    for item in timeline_items:
        node = _build_thread_node(item)
        if node is None:
            continue
        section, payload = node
        grouped[section].append(payload)

    sections: list[dict[str, object]] = []
    for key, title in (
        ("room1", "Recepção"),
        ("room2", "Avaliação"),
        ("room3", "Agendamento"),
    ):
        sections.append(
            {
                "key": key,
                "title": title,
                "items": grouped[key],
            }
        )
    return sections


def _build_thread_node(
    item: CaseMonitoringTimelineItem,
) -> tuple[str, dict[str, str | None]] | None:
    """Map one timeline event into a compact thread node when relevant."""

    event_type = item.event_type
    timestamp = item.timestamp.isoformat()
    actor = item.actor or "system"
    if item.source == "pdf" and event_type == "pdf_report_extracted":
        return (
            "room1",
            {
                "title": "PDF recebido (paciente + registro)",
                "detail": None,
                "actor": None,
                "timestamp": timestamp,
            },
        )
    if event_type == "bot_processing":
        return (
            "room1",
            {
                "title": "Confirmação de processamento",
                "detail": None,
                "actor": None,
                "timestamp": timestamp,
            },
        )
    if event_type == "room2_doctor_reply":
        decision = _extract_room2_decision(item.content_text)
        return (
            "room2",
            {
                "title": f"Resposta médica: DECISÃO = {decision}",
                "detail": None,
                "actor": actor,
                "timestamp": timestamp,
            },
        )
    if event_type == "room2_decision_ack":
        return (
            "room2",
            {
                "title": "Confirmação da decisão enviada pelo bot",
                "detail": None,
                "actor": None,
                "timestamp": timestamp,
            },
        )
    if event_type == "ROOM2_ACK_POSITIVE_RECEIVED":
        return (
            "room2",
            {
                "title": _build_reaction_title(scope="ACK", item=item),
                "detail": None,
                "actor": None,
                "timestamp": timestamp,
            },
        )
    if event_type == "room3_reply":
        schedule_at = _extract_schedule_datetime(item.content_text)
        return (
            "room3",
            {
                "title": _build_room3_reply_title(item.content_text),
                "detail": f"Agendado para: {schedule_at}" if schedule_at is not None else None,
                "actor": actor,
                "timestamp": timestamp,
            },
        )
    if event_type == "bot_ack":
        return (
            "room3",
            {
                "title": "Confirmação do agendamento enviada pelo bot",
                "detail": None,
                "actor": None,
                "timestamp": timestamp,
            },
        )
    if event_type == "ROOM3_ACK_POSITIVE_RECEIVED":
        return (
            "room3",
            {
                "title": _build_reaction_title(scope="ACK", item=item),
                "detail": None,
                "actor": None,
                "timestamp": timestamp,
            },
        )
    if event_type == "room1_final":
        return (
            "room1",
            {
                "title": "Confirmação da mensagem final",
                "detail": _build_room1_final_result(item.content_text),
                "actor": None,
                "timestamp": timestamp,
            },
        )
    if event_type == "ROOM1_FINAL_POSITIVE_RECEIVED":
        return (
            "room1",
            {
                "title": _build_reaction_title(scope="mensagem final", item=item),
                "detail": None,
                "actor": None,
                "timestamp": timestamp,
            },
        )
    return None


def _extract_room2_decision(content_text: str | None) -> str:
    """Extract compact decision label from Room-2 doctor reply text."""

    if content_text is None:
        return "INDEFINIDA"
    normalized = content_text.lower()
    if "aceitar" in normalized or "accept" in normalized:
        return "ACEITAR"
    if "negar" in normalized or "deny" in normalized:
        return "NEGAR"
    return "INDEFINIDA"


def _build_room3_reply_title(content_text: str | None) -> str:
    """Build compact status title for Room-3 scheduler reply."""

    if content_text is None:
        return "Resposta do Agendamento"
    normalized = content_text.lower()
    if (
        "status: confirmed" in normalized
        or "status=confirmed" in normalized
        or "positiv" in normalized
        or "confirmad" in normalized
    ):
        return "Resposta do Agendamento: POSITIVA"
    if (
        "status: denied" in normalized
        or "status=denied" in normalized
        or "negad" in normalized
        or "indefer" in normalized
    ):
        return "Resposta do Agendamento: NEGATIVA"
    return "Resposta do Agendamento"


def _build_room1_final_result(content_text: str | None) -> str:
    """Build compact final-result line for Room-1 final bot message."""

    if content_text is None:
        return "Resultado final registrado"

    normalized = content_text.lower()
    schedule_at = _extract_schedule_datetime(content_text)
    if "agend" in normalized and "confirm" in normalized:
        base = "Resultado final: AGENDAMENTO CONFIRMADO"
    elif "agend" in normalized and ("negad" in normalized or "deny" in normalized):
        base = "Resultado final: AGENDAMENTO NEGADO"
    elif "triagem" in normalized and ("negad" in normalized or "deny" in normalized):
        base = "Resultado final: TRIAGEM NEGADA"
    else:
        base = "Resultado final registrado"
    if schedule_at is None:
        return base
    return f"{base} para {schedule_at}"


def _build_reaction_title(*, scope: str, item: CaseMonitoringTimelineItem) -> str:
    """Build compact reaction line showing emoji and reacting user."""

    payload = item.payload or {}
    reaction_key = payload.get("reaction_key")
    reaction = reaction_key if isinstance(reaction_key, str) and reaction_key else "👍"
    actor = item.actor or "usuário"
    # Traduz scopes técnicos para termos amigáveis
    scope_label = {
        "ACK": "confirmação",
        "mensagem final": "mensagem final",
    }.get(scope, scope)
    return f"Reação à {scope_label}: {reaction} por {actor}"


def _extract_schedule_datetime(content_text: str | None) -> str | None:
    """Extract schedule date/time snippet from free-form scheduler/final text."""

    if content_text is None:
        return None
    labelled = _SCHEDULE_LABEL_RE.search(content_text)
    if labelled is not None:
        value = labelled.group(1).strip()
        if value:
            return value
    iso_match = _SCHEDULE_ISO_RE.search(content_text)
    if iso_match is not None:
        return iso_match.group(0)
    br_match = _SCHEDULE_BR_RE.search(content_text)
    if br_match is not None:
        return br_match.group(0)
    return None


def _build_cases_url(
    *,
    page: int | None,
    page_size: int,
    status: CaseStatus | None,
    from_date: date | None,
    to_date: date | None,
) -> str:
    """Build dashboard list URL preserving active filters and pagination size."""

    assert page is not None
    params: dict[str, str | int] = {
        "page": page,
        "page_size": page_size,
    }
    if status is not None:
        params["status"] = status.value
    if from_date is not None:
        params["from_date"] = from_date.isoformat()
    if to_date is not None:
        params["to_date"] = to_date.isoformat()
    return f"/dashboard/cases?{urlencode(params)}"


def _parse_case_status_filter(raw_status: str | None) -> CaseStatus | None:
    """Parse optional case status query value, treating blank as absent."""

    if raw_status is None:
        return None
    normalized = raw_status.strip()
    if not normalized:
        return None
    try:
        return CaseStatus(normalized)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"invalid status filter: {normalized}") from exc


def _translate_event_type(event_type: str) -> str:
    """Translate technical event type to user-friendly Portuguese label."""

    translations = {
        "room1_origin": "recepção",
        "bot_processing": "bot processando",
        "pdf_report_extracted": "relatório pdf extraído",
        "LLM1": "extração estruturada",
        "LLM2": "sugestão de decisão",
        "room2_case_root": "avaliação",
        "room2_case_summary": "resumo do caso",
        "room2_case_instructions": "instruções ao médico",
        "room2_case_template": "modelo de resposta da decisão",
        "room2_doctor_reply": "resposta do médico",
        "room2_decision_ack": "confirmação da decisão",
        "ROOM2_ACK_POSITIVE_EXPECTED": "aguardando reação positiva do Médico",
        "ROOM2_ACK_POSITIVE_RECEIVED": "reação positiva recebida do Médico",
        "room3_request": "solicitação de agendamento",
        "room3_template": "modelo de resposta do agendamento",
        "room3_reply": "resposta do agendamento",
        "bot_ack": "confirmação do agendamento",
        "ROOM3_ACK_POSITIVE_EXPECTED": "aguardando reação positiva do Agendamento",
        "ROOM3_ACK_POSITIVE_RECEIVED": "reação positiva recebida do Agendamento",
        "ROOM1_FINAL_POSITIVE_EXPECTED": "aguardando reação positiva da Recepção",
        "room1_final": "mensagem final à Recepção",
        "ROOM1_FINAL_POSITIVE_RECEIVED": "reação positiva recebida da Recepção",
    }
    return translations.get(event_type, event_type)


def _source_badge_class(source: str) -> str:
    """Map timeline source into a Bootstrap contextual badge class."""

    return {
        "pdf": "text-bg-secondary",
        "llm": "text-bg-info",
        "matrix": "text-bg-primary",
    }.get(source, "text-bg-secondary")


def _channel_badge_class(channel: str) -> str:
    """Map timeline channel/room id into a Bootstrap badge class."""

    if channel.startswith("!room1"):
        return "text-bg-warning"
    if channel.startswith("!room2"):
        return "text-bg-primary"
    if channel.startswith("!room3"):
        return "text-bg-success"
    if channel == "llm":
        return "text-bg-info"
    if channel == "pdf":
        return "text-bg-secondary"
    return "text-bg-secondary"


def _event_badge_class(event_type: str) -> str:
    """Map event type into a Bootstrap badge class for timeline differentiation."""

    if event_type.endswith("_POSITIVE_RECEIVED"):
        return "text-bg-success"
    if event_type.endswith("_POSITIVE_EXPECTED"):
        return "text-bg-warning"
    if "ack" in event_type or event_type.startswith("bot_"):
        return "text-bg-info"
    if "reply" in event_type:
        return "text-bg-primary"
    if event_type.startswith("LLM"):
        return "text-bg-info"
    return "text-bg-secondary"


def _extract_full_text(*, content_text: str | None, payload: dict[str, object] | None) -> str:
    """Return full event content text, using payload fallback when needed."""

    if content_text is not None and content_text.strip():
        return content_text
    if payload is None:
        return ""
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def _build_excerpt(full_text: str) -> str:
    """Return fixed-size excerpt text for timeline cards."""

    limit = 180
    normalized = " ".join(full_text.split())
    if len(normalized) <= limit:
        return normalized
    return f"{normalized[:limit].rstrip()}..."


async def _require_audit_user(
    *,
    auth_guard: WidgetAuthGuard,
    request: Request,
) -> UserRecord | RedirectResponse:
    """Resolve and authorize dashboard caller for audit-read operations."""

    try:
        return await auth_guard.require_audit_user(
            authorization_header=request.headers.get("authorization"),
            session_token=request.cookies.get(SESSION_COOKIE_NAME),
        )
    except MissingAuthTokenError:
        return RedirectResponse(url="/login", status_code=303)
    except InvalidAuthTokenError:
        return RedirectResponse(url="/login", status_code=303)
    except UnknownRoleAuthorizationError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except RoleNotAuthorizedError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc

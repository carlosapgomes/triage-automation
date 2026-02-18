"""FastAPI router for server-rendered monitoring dashboard pages."""

from __future__ import annotations

import json
from datetime import date
from math import ceil
from pathlib import Path
from urllib.parse import urlencode
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

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
    InvalidAuthTokenError,
    MissingAuthTokenError,
    WidgetAuthGuard,
)

_TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"


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
        status: CaseStatus | None = None,
        from_date: date | None = None,
        to_date: date | None = None,
    ) -> HTMLResponse:
        """Render dashboard list page with filters and paginated case rows."""

        await _require_audit_user(auth_guard=auth_guard, request=request)
        try:
            result = await monitoring_service.list_cases(
                CaseMonitoringListQuery(
                    page=page,
                    page_size=page_size,
                    status=status,
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
            "status": status.value if status is not None else "",
            "from_date": from_date.isoformat() if from_date is not None else "",
            "to_date": to_date.isoformat() if to_date is not None else "",
            "page_size": result.page_size,
        }
        context = {
            "page_title": "Dashboard de Monitoramento",
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
                        status=status,
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
                        status=status,
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
    async def render_case_detail_page(request: Request, case_id: UUID) -> HTMLResponse:
        """Render dashboard detail page with chronological timeline by case."""

        authenticated_user = await _require_audit_user(auth_guard=auth_guard, request=request)

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
                    "event_type": item.event_type,
                    "event_badge_class": _event_badge_class(item.event_type),
                    "excerpt_text": excerpt_text,
                    "full_text": full_text if can_view_full_content else None,
                    "can_show_full_content": can_view_full_content,
                    "is_truncated": len(excerpt_text) < len(full_text),
                }
            )

        return templates.TemplateResponse(
            request=request,
            name="dashboard/case_detail.html",
            context={
                "page_title": "Detalhe do Caso",
                "case_id": str(case_id),
                "status": detail.status.value,
                "timeline_rows": timeline_rows,
            },
        )

    return router


def _is_unpoly_fragment_request(request: Request) -> bool:
    """Return whether request asks for a fragment-targeted Unpoly update."""

    return bool(request.headers.get("x-up-target"))


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


async def _require_audit_user(*, auth_guard: WidgetAuthGuard, request: Request) -> UserRecord:
    """Resolve and authorize dashboard caller for audit-read operations."""

    try:
        return await auth_guard.require_audit_user(
            authorization_header=request.headers.get("authorization")
        )
    except MissingAuthTokenError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except InvalidAuthTokenError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except UnknownRoleAuthorizationError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except RoleNotAuthorizedError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc

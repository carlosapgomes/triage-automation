"""FastAPI router for server-rendered monitoring dashboard pages."""

from __future__ import annotations

from datetime import date
from math import ceil
from pathlib import Path
from urllib.parse import urlencode
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from triage_automation.application.services.case_monitoring_service import (
    CaseMonitoringListQuery,
    CaseMonitoringService,
    InvalidMonitoringPeriodError,
)
from triage_automation.domain.case_status import CaseStatus

_TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"


def build_dashboard_router(*, monitoring_service: CaseMonitoringService) -> APIRouter:
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
        """Render dashboard detail page shell for one monitoring case."""

        return templates.TemplateResponse(
            request=request,
            name="dashboard/case_detail.html",
            context={
                "page_title": "Detalhe do Caso",
                "case_id": str(case_id),
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

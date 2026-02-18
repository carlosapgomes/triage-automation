"""FastAPI router for monitoring dashboard API endpoints."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, HTTPException, Query, Request

from triage_automation.application.dto.monitoring_models import (
    MonitoringCaseListItem,
    MonitoringCaseListQueryParams,
    MonitoringCaseListResponse,
)
from triage_automation.application.services.access_guard_service import (
    RoleNotAuthorizedError,
    UnknownRoleAuthorizationError,
)
from triage_automation.application.services.case_monitoring_service import (
    CaseMonitoringListQuery,
    CaseMonitoringService,
    InvalidMonitoringPeriodError,
)
from triage_automation.domain.case_status import CaseStatus
from triage_automation.infrastructure.http.auth_guard import (
    InvalidAuthTokenError,
    MissingAuthTokenError,
    WidgetAuthGuard,
)


def build_monitoring_router(
    *,
    monitoring_service: CaseMonitoringService,
    auth_guard: WidgetAuthGuard,
) -> APIRouter:
    """Build router exposing monitoring dashboard case-list endpoint."""

    router = APIRouter(tags=["monitoring"])

    @router.get("/monitoring/cases", response_model=MonitoringCaseListResponse)
    async def list_cases(
        request: Request,
        page: int = Query(default=1, ge=1),
        page_size: int = Query(default=20, ge=1),
        status: CaseStatus | None = None,
        from_date: date | None = None,
        to_date: date | None = None,
    ) -> MonitoringCaseListResponse:
        try:
            await auth_guard.require_audit_user(
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

        query_params = MonitoringCaseListQueryParams(
            page=page,
            page_size=page_size,
            status=status,
            from_date=from_date,
            to_date=to_date,
        )
        try:
            result = await monitoring_service.list_cases(
                CaseMonitoringListQuery(
                    page=query_params.page,
                    page_size=query_params.page_size,
                    status=query_params.status,
                    from_date=query_params.from_date,
                    to_date=query_params.to_date,
                )
            )
        except InvalidMonitoringPeriodError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        return MonitoringCaseListResponse(
            items=[
                MonitoringCaseListItem(
                    case_id=item.case_id,
                    status=item.status,
                    latest_activity_at=item.latest_activity_at,
                )
                for item in result.items
            ],
            page=result.page,
            page_size=result.page_size,
            total=result.total,
        )

    return router

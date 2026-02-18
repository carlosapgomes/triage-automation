"""Pydantic models for monitoring dashboard case-list endpoint."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from triage_automation.domain.case_status import CaseStatus


class StrictModel(BaseModel):
    """Base model with strict unknown-field rejection."""

    model_config = ConfigDict(extra="forbid")


class MonitoringCaseListItem(StrictModel):
    """One case row rendered in dashboard list responses."""

    case_id: UUID
    status: CaseStatus
    latest_activity_at: datetime


class MonitoringCaseListResponse(StrictModel):
    """Paginated dashboard case-list response model."""

    items: list[MonitoringCaseListItem]
    page: int = Field(ge=1)
    page_size: int = Field(ge=1)
    total: int = Field(ge=0)


class MonitoringCaseListQueryParams(StrictModel):
    """Validated query-parameter contract for monitoring case listing."""

    page: int = Field(ge=1)
    page_size: int = Field(ge=1)
    status: CaseStatus | None = None
    from_date: date | None = None
    to_date: date | None = None


class MonitoringCaseTimelineItem(StrictModel):
    """One unified timeline event in case-detail responses."""

    source: str
    timestamp: datetime
    room_id: str | None
    actor: str | None
    event_type: str
    content_text: str | None
    payload: dict[str, Any] | None


class MonitoringCaseDetailResponse(StrictModel):
    """Case-detail response with unified chronological timeline."""

    case_id: UUID
    status: CaseStatus
    timeline: list[MonitoringCaseTimelineItem]

"""Pydantic models for Room-2 widget bootstrap and submit contracts."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field, model_validator

from triage_automation.application.dto.webhook_models import (
    Decision,
    StrictModel,
    SupportFlag,
    validate_decision_support_flag,
)

WidgetCaseStatus = Literal["WAIT_DOCTOR"]


class WidgetDecisionBootstrapRequest(StrictModel):
    """HTTP request model for loading widget decision context by case."""

    case_id: UUID


class WidgetDecisionBootstrapResponse(StrictModel):
    """HTTP response model for widget decision context bootstrap."""

    case_id: UUID
    status: WidgetCaseStatus
    doctor_decision: Decision | None = None
    doctor_reason: str | None = None


class WidgetDecisionSubmitRequest(StrictModel):
    """HTTP request model for authenticated Room-2 decision submit."""

    case_id: UUID
    doctor_user_id: str = Field(min_length=1)
    decision: Decision
    support_flag: SupportFlag = "none"
    reason: str | None = None
    submitted_at: datetime | None = None
    widget_event_id: str | None = None

    @model_validator(mode="after")
    def _validate_decision_specific_rules(self) -> WidgetDecisionSubmitRequest:
        """Enforce support flag semantics shared with callback decision payloads."""

        validate_decision_support_flag(
            decision=self.decision,
            support_flag=self.support_flag,
        )
        return self


class WidgetDecisionSubmitResponse(StrictModel):
    """HTTP response model for widget decision submit endpoint."""

    ok: bool

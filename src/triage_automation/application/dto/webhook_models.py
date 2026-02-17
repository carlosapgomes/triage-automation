"""Pydantic models for webhook callback payloads."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    """Base model with strict unknown-field rejection."""

    model_config = ConfigDict(extra="forbid")


SupportFlag = Literal["none", "anesthesist", "anesthesist_icu"]
Decision = Literal["accept", "deny"]


def validate_decision_support_flag(*, decision: Decision, support_flag: SupportFlag) -> None:
    """Enforce decision/support_flag invariants shared by webhook and widget contracts."""

    if decision == "deny" and support_flag != "none":
        raise ValueError("decision=deny requires support_flag=none")

    if decision == "accept" and support_flag not in {
        "none",
        "anesthesist",
        "anesthesist_icu",
    }:
        raise ValueError("decision=accept requires a valid support_flag")


class TriageDecisionWebhookPayload(StrictModel):
    """Doctor widget callback payload contract."""

    case_id: UUID
    doctor_user_id: str = Field(min_length=1)
    decision: Decision
    support_flag: SupportFlag = "none"
    reason: str | None = None
    submitted_at: datetime | None = None
    widget_event_id: str | None = None

    @model_validator(mode="after")
    def _validate_decision_specific_rules(self) -> TriageDecisionWebhookPayload:
        validate_decision_support_flag(
            decision=self.decision,
            support_flag=self.support_flag,
        )
        return self


class TriageDecisionWebhookResponse(StrictModel):
    """HTTP response model for webhook callback endpoint."""

    ok: bool

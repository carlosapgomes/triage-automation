"""Port for case persistence operations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from triage_automation.domain.case_status import CaseStatus


class DuplicateCaseOriginEventError(ValueError):
    """Raised when a case with the same room1 origin event already exists."""


@dataclass(frozen=True)
class CaseCreateInput:
    """Input payload for creating a case row."""

    case_id: UUID
    status: CaseStatus
    room1_origin_room_id: str
    room1_origin_event_id: str
    room1_sender_user_id: str


@dataclass(frozen=True)
class CaseRecord:
    """Case persistence model used across repository boundaries."""

    case_id: UUID
    status: CaseStatus
    room1_origin_room_id: str
    room1_origin_event_id: str
    room1_sender_user_id: str
    created_at: datetime
    updated_at: datetime


class CaseRepositoryPort(Protocol):
    """Async case repository contract."""

    async def create_case(self, payload: CaseCreateInput) -> CaseRecord:
        """Create a case row or raise DuplicateCaseOriginEventError."""

    async def get_case_by_origin_event_id(self, origin_event_id: str) -> CaseRecord | None:
        """Retrieve case by Room-1 origin event id."""

"""Port for case message tracking used by cleanup/redaction."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID


class DuplicateCaseMessageError(ValueError):
    """Raised when the same room/event pair is inserted more than once."""


@dataclass(frozen=True)
class CaseMessageCreateInput:
    """Input payload for inserting a case message mapping."""

    case_id: UUID
    room_id: str
    event_id: str
    kind: str
    sender_user_id: str | None = None


class MessageRepositoryPort(Protocol):
    """Async case message repository contract."""

    async def add_message(self, payload: CaseMessageCreateInput) -> int:
        """Insert a case message mapping and return its numeric id."""

"""Port for append-only case audit events."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol
from uuid import UUID


@dataclass(frozen=True)
class AuditEventCreateInput:
    """Input payload for inserting an audit event."""

    case_id: UUID
    actor_type: str
    event_type: str
    payload: dict[str, Any] = field(default_factory=dict)
    actor_user_id: str | None = None
    room_id: str | None = None
    matrix_event_id: str | None = None


class AuditRepositoryPort(Protocol):
    """Async audit repository contract."""

    async def append_event(self, payload: AuditEventCreateInput) -> int:
        """Append an audit event and return its numeric id."""

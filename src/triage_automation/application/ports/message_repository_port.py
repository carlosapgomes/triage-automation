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


@dataclass(frozen=True)
class CaseMessageLookup:
    """Resolved case message mapping for room/event lookups."""

    case_id: UUID
    kind: str


@dataclass(frozen=True)
class CaseMessageRef:
    """Room/event pair used by cleanup redaction execution."""

    room_id: str
    event_id: str


@dataclass(frozen=True)
class CaseMatrixMessageTranscriptCreateInput:
    """Append-only payload for full Matrix message transcript persistence."""

    case_id: UUID
    room_id: str
    event_id: str
    sender: str
    message_type: str
    message_text: str
    reply_to_event_id: str | None = None


class MessageRepositoryPort(Protocol):
    """Async case message repository contract."""

    async def add_message(self, payload: CaseMessageCreateInput) -> int:
        """Insert a case message mapping and return its numeric id."""

    async def append_case_matrix_message_transcript(
        self,
        payload: CaseMatrixMessageTranscriptCreateInput,
    ) -> int:
        """Insert one full Matrix transcript row and return its numeric id."""

    async def has_message_kind(self, *, case_id: UUID, room_id: str, kind: str) -> bool:
        """Return whether a message mapping exists for case/room/kind."""

    async def find_case_id_by_room_event_kind(
        self,
        *,
        room_id: str,
        event_id: str,
        kind: str,
    ) -> UUID | None:
        """Resolve case_id for a known room/event/kind mapping."""

    async def get_case_message_by_room_event(
        self,
        *,
        room_id: str,
        event_id: str,
    ) -> CaseMessageLookup | None:
        """Resolve case_id and kind for a room/event mapping."""

    async def list_message_refs_for_case(self, *, case_id: UUID) -> list[CaseMessageRef]:
        """List room/event mappings for case cleanup redaction."""

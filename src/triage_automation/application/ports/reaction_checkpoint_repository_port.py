"""Port for persisting expected and received reaction checkpoints per case."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol
from uuid import UUID

ReactionCheckpointStage = Literal["ROOM2_ACK", "ROOM3_ACK", "ROOM1_FINAL"]


@dataclass(frozen=True)
class ReactionCheckpointCreateInput:
    """Input payload for registering an expected positive reaction checkpoint."""

    case_id: UUID
    stage: ReactionCheckpointStage
    room_id: str
    target_event_id: str


@dataclass(frozen=True)
class ReactionCheckpointPositiveInput:
    """Input payload for marking one expected checkpoint as positively reacted."""

    stage: ReactionCheckpointStage
    room_id: str
    target_event_id: str
    reaction_event_id: str
    reactor_user_id: str
    reaction_key: str


class ReactionCheckpointRepositoryPort(Protocol):
    """Async repository contract for reaction checkpoints."""

    async def ensure_expected_checkpoint(self, payload: ReactionCheckpointCreateInput) -> None:
        """Insert one expected checkpoint if not already present for room/event target."""

    async def mark_positive_reaction(self, payload: ReactionCheckpointPositiveInput) -> bool:
        """Mark checkpoint as positive reaction received; return whether state changed."""

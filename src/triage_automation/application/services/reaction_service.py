"""Service for routing reactions and claiming cleanup trigger via CAS."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from triage_automation.application.ports.audit_repository_port import (
    AuditEventCreateInput,
    AuditRepositoryPort,
)
from triage_automation.application.ports.case_repository_port import CaseRepositoryPort
from triage_automation.application.ports.job_queue_port import JobEnqueueInput, JobQueuePort
from triage_automation.application.ports.message_repository_port import MessageRepositoryPort
from triage_automation.domain.case_status import CaseStatus

logger = logging.getLogger(__name__)
_ACCEPTED_REACTION_KEYS = frozenset({"👍", "✅"})
_VARIATION_SELECTOR_TRANSLATION = {
    ord("\uFE0E"): None,  # text presentation selector
    ord("\uFE0F"): None,  # emoji presentation selector
}


@dataclass(frozen=True)
class ReactionEvent:
    """Normalized Matrix reaction payload used by reaction routing service."""

    room_id: str
    reaction_event_id: str
    reactor_user_id: str
    related_event_id: str
    reaction_key: str


@dataclass(frozen=True)
class ReactionResult:
    """Outcome model for reaction handling."""

    processed: bool
    reason: str | None = None


class ReactionService:
    """Route Room-1 cleanup thumbs and Room-2/3 audit-only ack thumbs."""

    def __init__(
        self,
        *,
        room1_id: str,
        room2_id: str,
        room3_id: str,
        case_repository: CaseRepositoryPort,
        audit_repository: AuditRepositoryPort,
        message_repository: MessageRepositoryPort,
        job_queue: JobQueuePort,
    ) -> None:
        self._room1_id = room1_id
        self._room2_id = room2_id
        self._room3_id = room3_id
        self._case_repository = case_repository
        self._audit_repository = audit_repository
        self._message_repository = message_repository
        self._job_queue = job_queue

    async def handle(self, event: ReactionEvent) -> ReactionResult:
        """Handle reaction event according to room-specific policy semantics."""

        logger.info(
            (
                "reaction_received room_id=%s reaction_event_id=%s related_event_id=%s "
                "reactor_user_id=%s reaction_key=%s"
            ),
            event.room_id,
            event.reaction_event_id,
            event.related_event_id,
            event.reactor_user_id,
            event.reaction_key,
        )
        normalized_key = _normalize_reaction_key(event.reaction_key)
        if normalized_key not in _ACCEPTED_REACTION_KEYS:
            return ReactionResult(processed=False, reason="not_thumbs_up")

        if event.room_id == self._room1_id:
            return await self._handle_room1_final_thumbs(event)

        if event.room_id in {self._room2_id, self._room3_id}:
            return await self._handle_room2_or_room3_ack_thumbs(event)

        return ReactionResult(processed=False, reason="unknown_room")

    async def _handle_room1_final_thumbs(self, event: ReactionEvent) -> ReactionResult:
        snapshot = await self._case_repository.get_by_room1_final_reply_event_id(
            room1_final_reply_event_id=event.related_event_id,
        )
        if snapshot is None:
            return ReactionResult(processed=False, reason="not_final_reply_target")

        await self._audit_repository.append_event(
            AuditEventCreateInput(
                case_id=snapshot.case_id,
                actor_type="human",
                actor_user_id=event.reactor_user_id,
                room_id=event.room_id,
                matrix_event_id=event.reaction_event_id,
                event_type="ROOM1_FINAL_THUMBS_UP_RECEIVED",
                payload={
                    "related_event_id": event.related_event_id,
                    "reaction_key": event.reaction_key,
                },
            )
        )

        if snapshot.status != CaseStatus.WAIT_R1_CLEANUP_THUMBS:
            await self._audit_repository.append_event(
                AuditEventCreateInput(
                    case_id=snapshot.case_id,
                    actor_type="system",
                    room_id=event.room_id,
                    matrix_event_id=event.reaction_event_id,
                    event_type="ROOM1_FINAL_REACTION_IGNORED_WRONG_STATE",
                    payload={"status": snapshot.status.value},
                )
            )
            return ReactionResult(processed=False, reason="wrong_state")

        claimed = await self._case_repository.claim_cleanup_trigger_if_first(
            case_id=snapshot.case_id,
            reactor_user_id=event.reactor_user_id,
        )
        if not claimed:
            await self._audit_repository.append_event(
                AuditEventCreateInput(
                    case_id=snapshot.case_id,
                    actor_type="system",
                    room_id=event.room_id,
                    matrix_event_id=event.reaction_event_id,
                    event_type="ROOM1_FINAL_THUMBS_UP_IGNORED_ALREADY_TRIGGERED",
                    payload={"related_event_id": event.related_event_id},
                )
            )
            return ReactionResult(processed=False, reason="already_triggered")

        await self._audit_repository.append_event(
            AuditEventCreateInput(
                case_id=snapshot.case_id,
                actor_type="system",
                room_id=event.room_id,
                matrix_event_id=event.reaction_event_id,
                event_type="ROOM1_FINAL_THUMBS_UP_TRIGGERED_CLEANUP",
                payload={"reactor_user_id": event.reactor_user_id},
            )
        )

        await self._job_queue.enqueue(
            JobEnqueueInput(
                case_id=snapshot.case_id,
                job_type="execute_cleanup",
                payload={},
            )
        )
        logger.info("reaction_triggered_cleanup case_id=%s", snapshot.case_id)
        return ReactionResult(processed=True)

    async def _handle_room2_or_room3_ack_thumbs(self, event: ReactionEvent) -> ReactionResult:
        mapping = await self._message_repository.get_case_message_by_room_event(
            room_id=event.room_id,
            event_id=event.related_event_id,
        )
        if mapping is None:
            return ReactionResult(processed=False, reason="not_ack_target")

        required_kind = "room2_decision_ack"
        event_type = "ROOM2_ACK_POSITIVE_RECEIVED"
        if event.room_id == self._room3_id:
            required_kind = "bot_ack"
            event_type = "ROOM3_ACK_THUMBS_UP_RECEIVED"
        if mapping.kind != required_kind:
            return ReactionResult(processed=False, reason="not_ack_target")

        await self._audit_repository.append_event(
            AuditEventCreateInput(
                case_id=mapping.case_id,
                actor_type="human",
                actor_user_id=event.reactor_user_id,
                room_id=event.room_id,
                matrix_event_id=event.reaction_event_id,
                event_type=event_type,
                payload={"related_event_id": event.related_event_id},
            )
        )
        logger.info("reaction_ack_recorded case_id=%s room_id=%s", mapping.case_id, event.room_id)
        return ReactionResult(processed=True)


def _normalize_reaction_key(value: str) -> str:
    """Normalize reaction key by dropping variation selectors and trimming spaces."""

    return value.translate(_VARIATION_SELECTOR_TRANSLATION).strip()

"""Service for handling Room-3 scheduler replies and strict re-prompts."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Protocol

from triage_automation.application.ports.audit_repository_port import (
    AuditEventCreateInput,
    AuditRepositoryPort,
)
from triage_automation.application.ports.case_repository_port import (
    CaseRepositoryPort,
    SchedulerDecisionUpdateInput,
)
from triage_automation.application.ports.job_queue_port import JobEnqueueInput, JobQueuePort
from triage_automation.application.ports.message_repository_port import (
    CaseMessageCreateInput,
    MessageRepositoryPort,
)
from triage_automation.domain.case_status import CaseStatus
from triage_automation.domain.scheduler_parser import SchedulerParseError, parse_scheduler_reply
from triage_automation.infrastructure.matrix.message_templates import (
    build_room3_invalid_format_reprompt,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Room3ReplyEvent:
    """Normalized Room-3 reply event payload for scheduler handling."""

    room_id: str
    event_id: str
    sender_user_id: str
    body: str
    reply_to_event_id: str | None


@dataclass(frozen=True)
class Room3ReplyResult:
    """Outcome model for Room-3 reply handling."""

    processed: bool
    reason: str | None = None


class MatrixRoomReplyPosterPort(Protocol):
    """Port used to post reply text to Matrix events."""

    async def reply_text(self, *, room_id: str, event_id: str, body: str) -> str:
        """Post a reply-to event and return matrix event id."""


class Room3ReplyService:
    """Validate, parse, persist, and branch scheduler reply workflow."""

    def __init__(
        self,
        *,
        room3_id: str,
        case_repository: CaseRepositoryPort,
        audit_repository: AuditRepositoryPort,
        message_repository: MessageRepositoryPort,
        job_queue: JobQueuePort,
        matrix_poster: MatrixRoomReplyPosterPort,
    ) -> None:
        self._room3_id = room3_id
        self._case_repository = case_repository
        self._audit_repository = audit_repository
        self._message_repository = message_repository
        self._job_queue = job_queue
        self._matrix_poster = matrix_poster

    async def handle_reply(self, event: Room3ReplyEvent) -> Room3ReplyResult:
        """Handle a Room-3 scheduler reply event using strict template rules."""

        logger.info(
            "room3_reply_received room_id=%s event_id=%s sender_user_id=%s reply_to=%s",
            event.room_id,
            event.event_id,
            event.sender_user_id,
            event.reply_to_event_id,
        )
        if event.room_id != self._room3_id:
            return Room3ReplyResult(processed=False, reason="wrong_room")

        if event.reply_to_event_id is None:
            return Room3ReplyResult(processed=False, reason="not_reply")

        case_id = await self._message_repository.find_case_id_by_room_event_kind(
            room_id=event.room_id,
            event_id=event.reply_to_event_id,
            kind="room3_request",
        )
        if case_id is None:
            return Room3ReplyResult(processed=False, reason="unknown_reply_target")
        logger.info("room3_reply_mapped_to_case case_id=%s", case_id)

        snapshot = await self._case_repository.get_case_doctor_decision_snapshot(case_id=case_id)
        if snapshot is None:
            return Room3ReplyResult(processed=False, reason="case_not_found")

        if snapshot.status != CaseStatus.WAIT_APPT:
            await self._audit_repository.append_event(
                AuditEventCreateInput(
                    case_id=case_id,
                    actor_type="system",
                    room_id=event.room_id,
                    matrix_event_id=event.event_id,
                    event_type="ROOM3_MESSAGE_IGNORED_CASE_NOT_WAITING",
                    payload={"status": snapshot.status.value},
                )
            )
            logger.info(
                "room3_reply_ignored_case_not_waiting case_id=%s status=%s",
                case_id,
                snapshot.status.value,
            )
            return Room3ReplyResult(processed=False, reason="case_not_waiting")

        try:
            parsed = parse_scheduler_reply(body=event.body, expected_case_id=case_id)
        except SchedulerParseError as error:
            if error.reason in {"missing_case_line", "invalid_case_line", "case_id_mismatch"}:
                await self._audit_repository.append_event(
                    AuditEventCreateInput(
                        case_id=case_id,
                        actor_type="system",
                        room_id=event.room_id,
                        matrix_event_id=event.event_id,
                        event_type="ROOM3_TEMPLATE_INVALID_CASE_LINE",
                        payload={"reason": error.reason},
                    )
                )

            await self._audit_repository.append_event(
                AuditEventCreateInput(
                    case_id=case_id,
                    actor_type="system",
                    room_id=event.room_id,
                    matrix_event_id=event.event_id,
                    event_type="ROOM3_TEMPLATE_PARSE_FAILED",
                    payload={"reason": error.reason, "sender_user_id": event.sender_user_id},
                )
            )

            reprompt = build_room3_invalid_format_reprompt(case_id=case_id)
            reprompt_event_id = await self._matrix_poster.reply_text(
                room_id=event.room_id,
                event_id=event.event_id,
                body=reprompt,
            )
            await self._message_repository.add_message(
                CaseMessageCreateInput(
                    case_id=case_id,
                    room_id=event.room_id,
                    event_id=reprompt_event_id,
                    sender_user_id=None,
                    kind="bot_reformat_prompt_room3",
                )
            )
            logger.warning(
                "room3_reply_parse_failed case_id=%s reason=%s reprompt_event_id=%s",
                case_id,
                error.reason,
                reprompt_event_id,
            )
            return Room3ReplyResult(processed=False, reason="invalid_template")

        applied = await self._case_repository.apply_scheduler_decision_if_waiting(
            SchedulerDecisionUpdateInput(
                case_id=case_id,
                scheduler_user_id=event.sender_user_id,
                appointment_status=parsed.appointment_status,
                appointment_at=parsed.appointment_at,
                appointment_location=parsed.location,
                appointment_instructions=parsed.instructions,
                appointment_reason=parsed.reason,
            )
        )
        if not applied:
            logger.info("room3_reply_duplicate_or_race case_id=%s", case_id)
            return Room3ReplyResult(processed=False, reason="duplicate_or_race")

        await self._message_repository.add_message(
            CaseMessageCreateInput(
                case_id=case_id,
                room_id=event.room_id,
                event_id=event.event_id,
                sender_user_id=event.sender_user_id,
                kind="room3_reply",
            )
        )

        if parsed.appointment_status == "confirmed":
            event_type = "ROOM3_APPOINTMENT_CONFIRMED"
            next_job = "post_room1_final_appt"
        else:
            event_type = "ROOM3_APPOINTMENT_DENIED"
            next_job = "post_room1_final_appt_denied"

        await self._audit_repository.append_event(
            AuditEventCreateInput(
                case_id=case_id,
                actor_type="system",
                room_id=event.room_id,
                matrix_event_id=event.event_id,
                event_type=event_type,
                payload={"appointment_status": parsed.appointment_status},
            )
        )

        await self._job_queue.enqueue(
            JobEnqueueInput(
                case_id=case_id,
                job_type=next_job,
                payload={},
            )
        )

        logger.info(
            "room3_reply_applied case_id=%s appointment_status=%s enqueued_job=%s",
            case_id,
            parsed.appointment_status,
            next_job,
        )
        return Room3ReplyResult(processed=True)

"""Service for posting Room-3 scheduling request and ack messages."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from triage_automation.application.ports.audit_repository_port import (
    AuditEventCreateInput,
    AuditRepositoryPort,
)
from triage_automation.application.ports.case_repository_port import CaseRepositoryPort
from triage_automation.application.ports.message_repository_port import (
    CaseMessageCreateInput,
    MessageRepositoryPort,
)
from triage_automation.domain.case_status import CaseStatus
from triage_automation.infrastructure.matrix.message_templates import (
    build_room3_ack_message,
    build_room3_request_message,
)

logger = logging.getLogger(__name__)


class MatrixRoomPosterPort(Protocol):
    """Port used to post standard text messages into Matrix rooms."""

    async def send_text(self, *, room_id: str, body: str) -> str:
        """Post text body to a room and return generated matrix event id."""


@dataclass
class PostRoom3RequestRetriableError(RuntimeError):
    """Retriable posting error with explicit failure cause category."""

    cause: str
    details: str

    def __str__(self) -> str:
        return f"{self.cause}: {self.details}"


@dataclass(frozen=True)
class PostRoom3RequestResult:
    """Outcome model for Room-3 request posting."""

    posted: bool
    reason: str | None = None


class PostRoom3RequestService:
    """Post Room-3 request and ack while transitioning case to WAIT_APPT."""

    def __init__(
        self,
        *,
        room3_id: str,
        case_repository: CaseRepositoryPort,
        audit_repository: AuditRepositoryPort,
        message_repository: MessageRepositoryPort,
        matrix_poster: MatrixRoomPosterPort,
    ) -> None:
        self._room3_id = room3_id
        self._case_repository = case_repository
        self._audit_repository = audit_repository
        self._message_repository = message_repository
        self._matrix_poster = matrix_poster

    async def post_request(self, *, case_id: UUID) -> PostRoom3RequestResult:
        """Post scheduling request + ack for doctor-accepted cases."""

        logger.info("room3_request_post_started case_id=%s", case_id)
        snapshot = await self._case_repository.get_case_doctor_decision_snapshot(case_id=case_id)
        if snapshot is None:
            raise PostRoom3RequestRetriableError(cause="room3", details="Case not found")

        if snapshot.status == CaseStatus.WAIT_APPT:
            await self._audit_repository.append_event(
                AuditEventCreateInput(
                    case_id=case_id,
                    actor_type="system",
                    event_type="ROOM3_REQUEST_POST_SKIPPED_ALREADY_POSTED",
                    payload={"status": snapshot.status.value},
                )
            )
            logger.info("room3_request_post_skipped case_id=%s reason=already_wait_appt", case_id)
            return PostRoom3RequestResult(posted=False, reason="already_wait_appt")

        if snapshot.status not in {CaseStatus.DOCTOR_ACCEPTED, CaseStatus.R3_POST_REQUEST}:
            raise PostRoom3RequestRetriableError(
                cause="room3",
                details=(
                    f"Case status {snapshot.status.value} is not ready for Room-3 request post"
                ),
            )

        existing_request = await self._message_repository.has_message_kind(
            case_id=case_id,
            room_id=self._room3_id,
            kind="room3_request",
        )
        if existing_request:
            await self._audit_repository.append_event(
                AuditEventCreateInput(
                    case_id=case_id,
                    actor_type="system",
                    event_type="ROOM3_REQUEST_POST_SKIPPED_ALREADY_POSTED",
                    payload={"status": snapshot.status.value},
                )
            )
            if snapshot.status == CaseStatus.R3_POST_REQUEST:
                await self._case_repository.update_status(
                    case_id=case_id,
                    status=CaseStatus.WAIT_APPT,
                )
            logger.info("room3_request_post_skipped case_id=%s reason=already_posted", case_id)
            return PostRoom3RequestResult(posted=False, reason="already_posted")

        if snapshot.status == CaseStatus.DOCTOR_ACCEPTED:
            await self._case_repository.update_status(
                case_id=case_id,
                status=CaseStatus.R3_POST_REQUEST,
            )

        request_body = build_room3_request_message(case_id=case_id)
        request_event_id = await self._matrix_poster.send_text(
            room_id=self._room3_id,
            body=request_body,
        )
        logger.info(
            "room3_request_posted case_id=%s room_id=%s event_id=%s",
            case_id,
            self._room3_id,
            request_event_id,
        )
        await self._message_repository.add_message(
            CaseMessageCreateInput(
                case_id=case_id,
                room_id=self._room3_id,
                event_id=request_event_id,
                sender_user_id=None,
                kind="room3_request",
            )
        )

        await self._audit_repository.append_event(
            AuditEventCreateInput(
                case_id=case_id,
                actor_type="bot",
                room_id=self._room3_id,
                matrix_event_id=request_event_id,
                event_type="ROOM3_REQUEST_POSTED",
                payload={},
            )
        )

        ack_body = build_room3_ack_message(case_id=case_id)
        ack_event_id = await self._matrix_poster.send_text(room_id=self._room3_id, body=ack_body)
        logger.info(
            "room3_ack_posted case_id=%s room_id=%s event_id=%s",
            case_id,
            self._room3_id,
            ack_event_id,
        )
        await self._message_repository.add_message(
            CaseMessageCreateInput(
                case_id=case_id,
                room_id=self._room3_id,
                event_id=ack_event_id,
                sender_user_id=None,
                kind="bot_ack",
            )
        )

        await self._audit_repository.append_event(
            AuditEventCreateInput(
                case_id=case_id,
                actor_type="bot",
                room_id=self._room3_id,
                matrix_event_id=ack_event_id,
                event_type="ROOM3_ACK_POSTED",
                payload={},
            )
        )

        await self._case_repository.update_status(
            case_id=case_id,
            status=CaseStatus.WAIT_APPT,
        )
        await self._audit_repository.append_event(
            AuditEventCreateInput(
                case_id=case_id,
                actor_type="system",
                event_type="CASE_STATUS_CHANGED",
                payload={
                    "from_status": CaseStatus.R3_POST_REQUEST.value,
                    "to_status": CaseStatus.WAIT_APPT.value,
                },
            )
        )

        logger.info(
            "room3_request_post_completed case_id=%s to_status=%s",
            case_id,
            CaseStatus.WAIT_APPT.value,
        )
        return PostRoom3RequestResult(posted=True)

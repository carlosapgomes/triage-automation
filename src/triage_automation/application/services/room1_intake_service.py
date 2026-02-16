"""Room-1 intake service for PDF case creation and job enqueue."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Protocol
from uuid import uuid4

from triage_automation.application.ports.audit_repository_port import (
    AuditEventCreateInput,
    AuditRepositoryPort,
)
from triage_automation.application.ports.case_repository_port import (
    CaseCreateInput,
    CaseRepositoryPort,
    DuplicateCaseOriginEventError,
)
from triage_automation.application.ports.job_queue_port import JobEnqueueInput, JobQueuePort
from triage_automation.application.ports.message_repository_port import (
    CaseMessageCreateInput,
    MessageRepositoryPort,
)
from triage_automation.domain.case_status import CaseStatus
from triage_automation.infrastructure.matrix.event_parser import ParsedRoom1PdfIntakeEvent

logger = logging.getLogger(__name__)


class MatrixMessagePosterPort(Protocol):
    """Port used to post reply messages into Matrix rooms."""

    async def reply_text(self, *, room_id: str, event_id: str, body: str) -> str:
        """Post reply text and return generated matrix event id."""


@dataclass(frozen=True)
class Room1IntakeResult:
    """Outcome model for room1 intake handling."""

    processed: bool
    case_id: str | None = None
    reason: str | None = None


class Room1IntakeService:
    """Create case/audit/message/job records for valid Room-1 PDF intake events."""

    def __init__(
        self,
        *,
        case_repository: CaseRepositoryPort,
        audit_repository: AuditRepositoryPort,
        message_repository: MessageRepositoryPort,
        job_queue: JobQueuePort,
        matrix_poster: MatrixMessagePosterPort,
    ) -> None:
        self._case_repository = case_repository
        self._audit_repository = audit_repository
        self._message_repository = message_repository
        self._job_queue = job_queue
        self._matrix_poster = matrix_poster

    async def ingest_pdf_event(self, parsed: ParsedRoom1PdfIntakeEvent) -> Room1IntakeResult:
        """Persist intake artifacts and enqueue process job once per unique origin event."""

        logger.info(
            "room1_intake_received room_id=%s event_id=%s sender_user_id=%s",
            parsed.room_id,
            parsed.event_id,
            parsed.sender_user_id,
        )
        case_id = uuid4()

        try:
            created_case = await self._case_repository.create_case(
                CaseCreateInput(
                    case_id=case_id,
                    status=CaseStatus.R1_ACK_PROCESSING,
                    room1_origin_room_id=parsed.room_id,
                    room1_origin_event_id=parsed.event_id,
                    room1_sender_user_id=parsed.sender_user_id,
                )
            )
        except DuplicateCaseOriginEventError:
            logger.info("room1_intake_duplicate_origin_event event_id=%s", parsed.event_id)
            return Room1IntakeResult(processed=False, reason="duplicate_origin_event")

        await self._audit_repository.append_event(
            AuditEventCreateInput(
                case_id=created_case.case_id,
                actor_type="system",
                event_type="ROOM1_PDF_ACCEPTED",
                room_id=parsed.room_id,
                matrix_event_id=parsed.event_id,
                payload={
                    "mxc_url": parsed.mxc_url,
                    "filename": parsed.filename,
                    "mimetype": parsed.mimetype,
                },
            )
        )

        await self._message_repository.add_message(
            CaseMessageCreateInput(
                case_id=created_case.case_id,
                room_id=parsed.room_id,
                event_id=parsed.event_id,
                sender_user_id=parsed.sender_user_id,
                kind="room1_origin",
            )
        )

        processing_event_id = await self._matrix_poster.reply_text(
            room_id=parsed.room_id,
            event_id=parsed.event_id,
            body="processando...",
        )

        await self._message_repository.add_message(
            CaseMessageCreateInput(
                case_id=created_case.case_id,
                room_id=parsed.room_id,
                event_id=processing_event_id,
                sender_user_id=None,
                kind="bot_processing",
            )
        )

        await self._audit_repository.append_event(
            AuditEventCreateInput(
                case_id=created_case.case_id,
                actor_type="bot",
                event_type="ROOM1_PROCESSING_ACK_POSTED",
                room_id=parsed.room_id,
                matrix_event_id=processing_event_id,
                payload={},
            )
        )

        await self._job_queue.enqueue(
            JobEnqueueInput(
                case_id=created_case.case_id,
                job_type="process_pdf_case",
                payload={
                    "room1_origin_event_id": parsed.event_id,
                    "pdf_mxc_url": parsed.mxc_url,
                    "filename": parsed.filename,
                    "mimetype": parsed.mimetype,
                },
            )
        )
        logger.info(
            "room1_intake_enqueued_next_job case_id=%s job_type=process_pdf_case",
            created_case.case_id,
        )

        await self._audit_repository.append_event(
            AuditEventCreateInput(
                case_id=created_case.case_id,
                actor_type="system",
                event_type="JOB_ENQUEUED_PROCESS_PDF_CASE",
                payload={"job_type": "process_pdf_case"},
            )
        )

        logger.info("room1_intake_processed case_id=%s", created_case.case_id)
        return Room1IntakeResult(processed=True, case_id=str(created_case.case_id))

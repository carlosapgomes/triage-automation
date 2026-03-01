"""Service for authenticated doctor decision callback handling."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Protocol

from triage_automation.application.dto.webhook_models import TriageDecisionWebhookPayload
from triage_automation.application.ports.audit_repository_port import (
    AuditEventCreateInput,
    AuditRepositoryPort,
)
from triage_automation.application.ports.case_repository_port import (
    CaseRepositoryPort,
    DoctorDecisionUpdateInput,
)
from triage_automation.application.ports.job_queue_port import JobEnqueueInput, JobQueuePort
from triage_automation.application.ports.message_repository_port import (
    CaseMatrixMessageTranscriptCreateInput,
    CaseMessageCreateInput,
    MessageRepositoryPort,
)
from triage_automation.application.ports.reaction_checkpoint_repository_port import (
    ReactionCheckpointCreateInput,
    ReactionCheckpointRepositoryPort,
)
from triage_automation.application.services.patient_context import extract_patient_name_age
from triage_automation.domain.case_status import CaseStatus
from triage_automation.infrastructure.matrix.message_templates import (
    build_room2_decision_ack_message,
)

logger = logging.getLogger(__name__)


class HandleDoctorDecisionOutcome(StrEnum):
    """Outcomes returned by decision callback handling service."""

    APPLIED = "applied"
    NOT_FOUND = "not_found"
    WRONG_STATE = "wrong_state"
    DUPLICATE_OR_RACE = "duplicate_or_race"


@dataclass(frozen=True)
class HandleDoctorDecisionResult:
    """Service outcome model for webhook API response mapping."""

    outcome: HandleDoctorDecisionOutcome


class MatrixRoomDecisionPosterPort(Protocol):
    """Port used to emit Room-2 decision confirmation messages."""

    async def send_text(self, *, room_id: str, body: str) -> str:
        """Post text body to a room and return generated matrix event id."""

    async def reply_text(self, *, room_id: str, event_id: str, body: str) -> str:
        """Post reply text to a Matrix event and return generated matrix event id."""


class HandleDoctorDecisionService:
    """Persist doctor decision callback and enqueue next workflow job."""

    def __init__(
        self,
        *,
        case_repository: CaseRepositoryPort,
        audit_repository: AuditRepositoryPort,
        job_queue: JobQueuePort,
        message_repository: MessageRepositoryPort | None = None,
        matrix_poster: MatrixRoomDecisionPosterPort | None = None,
        room2_id: str | None = None,
        reaction_checkpoint_repository: ReactionCheckpointRepositoryPort | None = None,
    ) -> None:
        self._case_repository = case_repository
        self._audit_repository = audit_repository
        self._job_queue = job_queue
        self._message_repository = message_repository
        self._matrix_poster = matrix_poster
        self._room2_id = room2_id
        self._reaction_checkpoint_repository = reaction_checkpoint_repository

    async def handle(
        self,
        payload: TriageDecisionWebhookPayload,
    ) -> HandleDoctorDecisionResult:
        """Apply a signed doctor decision payload when case is in WAIT_DOCTOR."""

        logger.info(
            (
                "doctor_decision_received case_id=%s doctor_user_id=%s "
                "decision=%s support_flag=%s"
            ),
            payload.case_id,
            payload.doctor_user_id,
            payload.decision,
            payload.support_flag,
        )
        snapshot = await self._case_repository.get_case_doctor_decision_snapshot(
            case_id=payload.case_id
        )
        if snapshot is None:
            logger.info("doctor_decision_ignored_not_found case_id=%s", payload.case_id)
            return HandleDoctorDecisionResult(outcome=HandleDoctorDecisionOutcome.NOT_FOUND)

        if snapshot.status != CaseStatus.WAIT_DOCTOR:
            await self._audit_repository.append_event(
                AuditEventCreateInput(
                    case_id=payload.case_id,
                    actor_type="system",
                    event_type="ROOM2_DECISION_IGNORED_WRONG_STATE",
                    payload={
                        "current_status": snapshot.status.value,
                        "decision": payload.decision,
                    },
                )
            )
            logger.info(
                "doctor_decision_ignored_wrong_state case_id=%s current_status=%s",
                payload.case_id,
                snapshot.status.value,
            )
            return HandleDoctorDecisionResult(outcome=HandleDoctorDecisionOutcome.WRONG_STATE)

        applied = await self._case_repository.apply_doctor_decision_if_waiting(
            DoctorDecisionUpdateInput(
                case_id=payload.case_id,
                doctor_user_id=payload.doctor_user_id,
                decision=payload.decision,
                support_flag=payload.support_flag,
                reason=payload.reason,
            )
        )
        if not applied:
            await self._audit_repository.append_event(
                AuditEventCreateInput(
                    case_id=payload.case_id,
                    actor_type="system",
                    event_type="ROOM2_DECISION_DUPLICATE_OR_RACE_IGNORED",
                    payload={"decision": payload.decision},
                )
            )
            return HandleDoctorDecisionResult(
                outcome=HandleDoctorDecisionOutcome.DUPLICATE_OR_RACE
            )

        await self._audit_repository.append_event(
            AuditEventCreateInput(
                case_id=payload.case_id,
                actor_type="system",
                event_type="ROOM2_WIDGET_SUBMITTED",
                payload={
                    "doctor_user_id": payload.doctor_user_id,
                    "decision": payload.decision,
                    "support_flag": payload.support_flag,
                    "reason": payload.reason,
                    "submitted_at": (
                        payload.submitted_at.isoformat()
                        if payload.submitted_at is not None
                        else None
                    ),
                    "widget_event_id": payload.widget_event_id,
                },
            )
        )

        job_type = _next_job_type(payload.decision)
        await self._job_queue.enqueue(
            JobEnqueueInput(case_id=payload.case_id, job_type=job_type, payload={})
        )
        logger.info(
            "doctor_decision_applied case_id=%s next_job=%s",
            payload.case_id,
            job_type,
        )

        await self._audit_repository.append_event(
            AuditEventCreateInput(
                case_id=payload.case_id,
                actor_type="system",
                event_type="JOB_ENQUEUED_NEXT_STEP",
                payload={"job_type": job_type, "decision": payload.decision},
            )
        )

        await self._post_room2_decision_ack(
            payload=payload,
            agency_record_number=snapshot.agency_record_number,
            structured_data_json=snapshot.structured_data_json,
        )

        return HandleDoctorDecisionResult(outcome=HandleDoctorDecisionOutcome.APPLIED)

    async def _post_room2_decision_ack(
        self,
        *,
        payload: TriageDecisionWebhookPayload,
        agency_record_number: str | None,
        structured_data_json: dict[str, Any] | None,
    ) -> None:
        """Post and persist Room-2 decision acknowledgment target when configured."""

        if (
            self._message_repository is None
            or self._matrix_poster is None
            or self._room2_id is None
        ):
            return

        patient_name, _ = extract_patient_name_age(structured_data_json)
        body = build_room2_decision_ack_message(
            case_id=payload.case_id,
            decision=payload.decision,
            support_flag=payload.support_flag,
            reason=payload.reason,
            agency_record_number=agency_record_number,
            patient_name=patient_name,
        )
        related_event_id = payload.widget_event_id
        try:
            if related_event_id is not None:
                ack_event_id = await self._matrix_poster.reply_text(
                    room_id=self._room2_id,
                    event_id=related_event_id,
                    body=body,
                )
            else:
                ack_event_id = await self._matrix_poster.send_text(
                    room_id=self._room2_id,
                    body=body,
                )
        except Exception as exc:  # pragma: no cover - defensive resilience path
            logger.warning(
                "room2_decision_ack_post_failed case_id=%s error=%s",
                payload.case_id,
                exc,
            )
            await self._audit_repository.append_event(
                AuditEventCreateInput(
                    case_id=payload.case_id,
                    actor_type="system",
                    event_type="ROOM2_DECISION_ACK_POST_FAILED",
                    payload={"error": str(exc)},
                )
            )
            return

        await self._message_repository.add_message(
            CaseMessageCreateInput(
                case_id=payload.case_id,
                room_id=self._room2_id,
                event_id=ack_event_id,
                sender_user_id=None,
                kind="room2_decision_ack",
            )
        )
        await self._message_repository.append_case_matrix_message_transcript(
            CaseMatrixMessageTranscriptCreateInput(
                case_id=payload.case_id,
                room_id=self._room2_id,
                event_id=ack_event_id,
                sender="bot",
                message_type="room2_decision_ack",
                message_text=body,
                reply_to_event_id=related_event_id,
            )
        )
        await self._audit_repository.append_event(
            AuditEventCreateInput(
                case_id=payload.case_id,
                actor_type="bot",
                room_id=self._room2_id,
                matrix_event_id=ack_event_id,
                event_type="ROOM2_DECISION_ACK_POSTED",
                payload={"related_event_id": related_event_id},
            )
        )
        if self._reaction_checkpoint_repository is not None:
            await self._reaction_checkpoint_repository.ensure_expected_checkpoint(
                ReactionCheckpointCreateInput(
                    case_id=payload.case_id,
                    stage="ROOM2_ACK",
                    room_id=self._room2_id,
                    target_event_id=ack_event_id,
                )
            )


def _next_job_type(decision: str) -> str:
    if decision == "deny":
        return "post_room1_final_denial_triage"
    return "post_room3_request"

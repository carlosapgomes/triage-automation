"""Service for authenticated doctor decision callback handling."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import StrEnum

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
from triage_automation.domain.case_status import CaseStatus

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


class HandleDoctorDecisionService:
    """Persist doctor decision callback and enqueue next workflow job."""

    def __init__(
        self,
        *,
        case_repository: CaseRepositoryPort,
        audit_repository: AuditRepositoryPort,
        job_queue: JobQueuePort,
    ) -> None:
        self._case_repository = case_repository
        self._audit_repository = audit_repository
        self._job_queue = job_queue

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

        return HandleDoctorDecisionResult(outcome=HandleDoctorDecisionOutcome.APPLIED)


def _next_job_type(decision: str) -> str:
    if decision == "deny":
        return "post_room1_final_denial_triage"
    return "post_room3_request"

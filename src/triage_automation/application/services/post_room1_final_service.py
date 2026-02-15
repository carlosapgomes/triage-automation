"""Service for posting final Room-1 reply variants."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from triage_automation.application.ports.audit_repository_port import (
    AuditEventCreateInput,
    AuditRepositoryPort,
)
from triage_automation.application.ports.case_repository_port import (
    CaseFinalReplySnapshot,
    CaseRepositoryPort,
)
from triage_automation.application.ports.message_repository_port import (
    CaseMessageCreateInput,
    MessageRepositoryPort,
)
from triage_automation.domain.case_status import CaseStatus
from triage_automation.infrastructure.matrix.message_templates import (
    build_room1_final_accepted_message,
    build_room1_final_denied_appointment_message,
    build_room1_final_denied_triage_message,
    build_room1_final_failure_message,
)


class MatrixReplyPosterPort(Protocol):
    """Port used to post reply text in Matrix rooms."""

    async def reply_text(self, *, room_id: str, event_id: str, body: str) -> str:
        """Post reply text and return generated matrix event id."""


@dataclass
class PostRoom1FinalRetriableError(RuntimeError):
    """Retriable posting error with explicit failure cause category."""

    cause: str
    details: str

    def __str__(self) -> str:
        return f"{self.cause}: {self.details}"


@dataclass(frozen=True)
class PostRoom1FinalResult:
    """Outcome model for final Room-1 reply posting."""

    posted: bool
    reason: str | None = None


class PostRoom1FinalService:
    """Post final Room-1 reply and transition to WAIT_R1_CLEANUP_THUMBS."""

    def __init__(
        self,
        *,
        case_repository: CaseRepositoryPort,
        audit_repository: AuditRepositoryPort,
        message_repository: MessageRepositoryPort,
        matrix_poster: MatrixReplyPosterPort,
    ) -> None:
        self._case_repository = case_repository
        self._audit_repository = audit_repository
        self._message_repository = message_repository
        self._matrix_poster = matrix_poster

    async def post(
        self,
        *,
        case_id: UUID,
        job_type: str,
        payload: dict[str, object] | None = None,
    ) -> PostRoom1FinalResult:
        """Post one final-reply variant according to job type."""

        case = await self._case_repository.get_case_final_reply_snapshot(case_id=case_id)
        if case is None:
            raise PostRoom1FinalRetriableError(cause="room1_final", details="Case not found")

        if case.room1_final_reply_event_id is not None:
            await self._audit_repository.append_event(
                AuditEventCreateInput(
                    case_id=case_id,
                    actor_type="system",
                    event_type="ROOM1_FINAL_REPLY_POST_SKIPPED_ALREADY_EXISTS",
                    payload={"job_type": job_type},
                )
            )
            return PostRoom1FinalResult(posted=False, reason="already_posted")

        body = _render_final_message(case=case, job_type=job_type, payload=payload or {})

        event_id = await self._matrix_poster.reply_text(
            room_id=case.room1_origin_room_id,
            event_id=case.room1_origin_event_id,
            body=body,
        )

        marked = await self._case_repository.mark_room1_final_reply_posted(
            case_id=case_id,
            room1_final_reply_event_id=event_id,
        )
        if not marked:
            return PostRoom1FinalResult(posted=False, reason="race_already_posted")

        await self._message_repository.add_message(
            CaseMessageCreateInput(
                case_id=case_id,
                room_id=case.room1_origin_room_id,
                event_id=event_id,
                sender_user_id=None,
                kind="room1_final",
            )
        )

        await self._audit_repository.append_event(
            AuditEventCreateInput(
                case_id=case_id,
                actor_type="bot",
                room_id=case.room1_origin_room_id,
                matrix_event_id=event_id,
                event_type="ROOM1_FINAL_REPLY_POSTED",
                payload={"job_type": job_type},
            )
        )
        await self._audit_repository.append_event(
            AuditEventCreateInput(
                case_id=case_id,
                actor_type="system",
                event_type="CASE_STATUS_CHANGED",
                payload={
                    "from_status": case.status.value,
                    "to_status": CaseStatus.WAIT_R1_CLEANUP_THUMBS.value,
                },
            )
        )

        return PostRoom1FinalResult(posted=True)


def _render_final_message(
    *,
    case: CaseFinalReplySnapshot,
    job_type: str,
    payload: dict[str, object],
) -> str:
    if job_type == "post_room1_final_denial_triage":
        _require_status(case=case, expected=CaseStatus.DOCTOR_DENIED, job_type=job_type)
        reason = case.doctor_reason or "not provided"
        return build_room1_final_denied_triage_message(case_id=case.case_id, reason=reason)

    if job_type == "post_room1_final_appt":
        _require_status(case=case, expected=CaseStatus.APPT_CONFIRMED, job_type=job_type)
        if (
            case.appointment_at is None
            or case.appointment_location is None
            or case.appointment_instructions is None
        ):
            raise PostRoom1FinalRetriableError(
                cause="room1_final",
                details="Missing appointment fields for accepted final reply",
            )
        return build_room1_final_accepted_message(
            case_id=case.case_id,
            appointment_at=case.appointment_at,
            location=case.appointment_location,
            instructions=case.appointment_instructions,
        )

    if job_type == "post_room1_final_appt_denied":
        _require_status(case=case, expected=CaseStatus.APPT_DENIED, job_type=job_type)
        reason = case.appointment_reason or "not provided"
        return build_room1_final_denied_appointment_message(case_id=case.case_id, reason=reason)

    if job_type == "post_room1_final_failure":
        _require_status(case=case, expected=CaseStatus.FAILED, job_type=job_type)
        cause = _payload_string(payload=payload, key="cause", default="other")
        details = _payload_string(payload=payload, key="details", default="not provided")
        return build_room1_final_failure_message(
            case_id=case.case_id,
            cause=cause,
            details=details,
        )

    raise PostRoom1FinalRetriableError(
        cause="room1_final",
        details=f"Unsupported final reply job type: {job_type}",
    )


def _require_status(
    *,
    case: CaseFinalReplySnapshot,
    expected: CaseStatus,
    job_type: str,
) -> None:
    if case.status != expected:
        raise PostRoom1FinalRetriableError(
            cause="room1_final",
            details=(
                f"Case status {case.status.value} is invalid for {job_type}; "
                f"expected {expected.value}"
            ),
        )


def _payload_string(*, payload: dict[str, object], key: str, default: str) -> str:
    value = payload.get(key)
    if isinstance(value, str) and value.strip():
        return value.strip()
    return default

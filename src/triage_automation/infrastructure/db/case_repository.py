"""SQLAlchemy adapter for case repository operations."""

from __future__ import annotations

from datetime import datetime
from typing import Any, cast
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.engine import CursorResult, RowMapping
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from triage_automation.application.ports.case_repository_port import (
    CaseCreateInput,
    CaseDoctorDecisionSnapshot,
    CaseFinalReplySnapshot,
    CaseRecord,
    CaseRecoverySnapshot,
    CaseRepositoryPort,
    CaseRoom2WidgetSnapshot,
    DoctorDecisionUpdateInput,
    DuplicateCaseOriginEventError,
    Room1FinalReplyReactionSnapshot,
    SchedulerDecisionUpdateInput,
)
from triage_automation.domain.case_status import CaseStatus
from triage_automation.infrastructure.db.metadata import cases


def _is_duplicate_origin_error(error: IntegrityError) -> bool:
    message = str(error.orig).lower()
    return "room1_origin_event_id" in message


def _to_case_record(row: RowMapping) -> CaseRecord:
    return CaseRecord(
        case_id=cast("Any", row["case_id"]),
        status=CaseStatus(cast(str, row["status"])),
        room1_origin_room_id=cast(str, row["room1_origin_room_id"]),
        room1_origin_event_id=cast(str, row["room1_origin_event_id"]),
        room1_sender_user_id=cast(str, row["room1_sender_user_id"]),
        created_at=cast("Any", row["created_at"]),
        updated_at=cast("Any", row["updated_at"]),
    )


class SqlAlchemyCaseRepository(CaseRepositoryPort):
    """Case repository backed by SQLAlchemy async sessions."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def create_case(self, payload: CaseCreateInput) -> CaseRecord:
        """Insert a new case row and return the created case record."""

        statement = (
            sa.insert(cases)
            .values(
                case_id=payload.case_id,
                status=payload.status.value,
                room1_origin_room_id=payload.room1_origin_room_id,
                room1_origin_event_id=payload.room1_origin_event_id,
                room1_sender_user_id=payload.room1_sender_user_id,
            )
            .returning(
                cases.c.case_id,
                cases.c.status,
                cases.c.room1_origin_room_id,
                cases.c.room1_origin_event_id,
                cases.c.room1_sender_user_id,
                cases.c.created_at,
                cases.c.updated_at,
            )
        )

        async with self._session_factory() as session:
            try:
                result = await session.execute(statement)
                await session.commit()
            except IntegrityError as error:
                await session.rollback()
                if _is_duplicate_origin_error(error):
                    raise DuplicateCaseOriginEventError(
                        "Duplicate room1_origin_event_id"
                    ) from error
                raise

        row = result.mappings().one()
        return _to_case_record(row)

    async def get_case_by_origin_event_id(self, origin_event_id: str) -> CaseRecord | None:
        """Return case by Room-1 origin event id when present."""

        statement = sa.select(
            cases.c.case_id,
            cases.c.status,
            cases.c.room1_origin_room_id,
            cases.c.room1_origin_event_id,
            cases.c.room1_sender_user_id,
            cases.c.created_at,
            cases.c.updated_at,
        ).where(cases.c.room1_origin_event_id == origin_event_id)

        async with self._session_factory() as session:
            result = await session.execute(statement)

        row = result.mappings().first()
        if row is None:
            return None
        return _to_case_record(row)

    async def get_case_room2_widget_snapshot(
        self,
        *,
        case_id: UUID,
    ) -> CaseRoom2WidgetSnapshot | None:
        """Return fields required to render the Room-2 doctor widget."""

        statement = sa.select(
            cases.c.case_id,
            cases.c.status,
            cases.c.agency_record_number,
            cases.c.structured_data_json,
            cases.c.summary_text,
            cases.c.suggested_action_json,
        ).where(cases.c.case_id == case_id)

        async with self._session_factory() as session:
            result = await session.execute(statement)

        row = result.mappings().first()
        if row is None:
            return None

        return CaseRoom2WidgetSnapshot(
            case_id=cast("Any", row["case_id"]),
            status=CaseStatus(cast(str, row["status"])),
            agency_record_number=cast(str | None, row["agency_record_number"]),
            structured_data_json=cast(dict[str, Any] | None, row["structured_data_json"]),
            summary_text=cast(str | None, row["summary_text"]),
            suggested_action_json=cast(dict[str, Any] | None, row["suggested_action_json"]),
        )

    async def get_case_doctor_decision_snapshot(
        self,
        *,
        case_id: UUID,
    ) -> CaseDoctorDecisionSnapshot | None:
        """Return status and doctor decision timestamp for webhook handling."""

        statement = sa.select(
            cases.c.case_id,
            cases.c.status,
            cases.c.doctor_decided_at,
        ).where(cases.c.case_id == case_id)

        async with self._session_factory() as session:
            result = await session.execute(statement)

        row = result.mappings().first()
        if row is None:
            return None

        return CaseDoctorDecisionSnapshot(
            case_id=cast("Any", row["case_id"]),
            status=CaseStatus(cast(str, row["status"])),
            doctor_decided_at=cast(datetime | None, row["doctor_decided_at"]),
        )

    async def apply_doctor_decision_if_waiting(
        self,
        payload: DoctorDecisionUpdateInput,
    ) -> bool:
        """Apply doctor decision only when case is still waiting for doctor input."""

        target_status = (
            CaseStatus.DOCTOR_DENIED
            if payload.decision == "deny"
            else CaseStatus.DOCTOR_ACCEPTED
        )
        statement = (
            sa.update(cases)
            .where(
                cases.c.case_id == payload.case_id,
                cases.c.status == CaseStatus.WAIT_DOCTOR.value,
                cases.c.doctor_decided_at.is_(None),
            )
            .values(
                doctor_user_id=payload.doctor_user_id,
                doctor_decision=payload.decision,
                doctor_support_flag=payload.support_flag,
                doctor_reason=payload.reason,
                doctor_decided_at=sa.func.current_timestamp(),
                status=target_status.value,
                updated_at=sa.func.current_timestamp(),
            )
        )

        async with self._session_factory() as session:
            result = cast(CursorResult[Any], await session.execute(statement))
            await session.commit()

        return int(result.rowcount or 0) == 1

    async def apply_scheduler_decision_if_waiting(
        self,
        payload: SchedulerDecisionUpdateInput,
    ) -> bool:
        """Apply scheduler decision only when case is in WAIT_APPT state."""

        target_status = (
            CaseStatus.APPT_CONFIRMED
            if payload.appointment_status == "confirmed"
            else CaseStatus.APPT_DENIED
        )
        statement = (
            sa.update(cases)
            .where(
                cases.c.case_id == payload.case_id,
                cases.c.status == CaseStatus.WAIT_APPT.value,
            )
            .values(
                scheduler_user_id=payload.scheduler_user_id,
                appointment_status=payload.appointment_status,
                appointment_at=payload.appointment_at,
                appointment_location=payload.appointment_location,
                appointment_instructions=payload.appointment_instructions,
                appointment_reason=payload.appointment_reason,
                appointment_decided_at=sa.func.current_timestamp(),
                status=target_status.value,
                updated_at=sa.func.current_timestamp(),
            )
        )

        async with self._session_factory() as session:
            result = cast(CursorResult[Any], await session.execute(statement))
            await session.commit()

        return int(result.rowcount or 0) == 1

    async def get_case_final_reply_snapshot(
        self,
        *,
        case_id: UUID,
    ) -> CaseFinalReplySnapshot | None:
        """Return final-reply context fields used to compose Room-1 responses."""

        statement = sa.select(
            cases.c.case_id,
            cases.c.status,
            cases.c.room1_origin_room_id,
            cases.c.room1_origin_event_id,
            cases.c.room1_final_reply_event_id,
            cases.c.doctor_reason,
            cases.c.appointment_at,
            cases.c.appointment_location,
            cases.c.appointment_instructions,
            cases.c.appointment_reason,
        ).where(cases.c.case_id == case_id)

        async with self._session_factory() as session:
            result = await session.execute(statement)

        row = result.mappings().first()
        if row is None:
            return None

        return CaseFinalReplySnapshot(
            case_id=cast("Any", row["case_id"]),
            status=CaseStatus(cast(str, row["status"])),
            room1_origin_room_id=cast(str, row["room1_origin_room_id"]),
            room1_origin_event_id=cast(str, row["room1_origin_event_id"]),
            room1_final_reply_event_id=cast(str | None, row["room1_final_reply_event_id"]),
            doctor_reason=cast(str | None, row["doctor_reason"]),
            appointment_at=cast(datetime | None, row["appointment_at"]),
            appointment_location=cast(str | None, row["appointment_location"]),
            appointment_instructions=cast(str | None, row["appointment_instructions"]),
            appointment_reason=cast(str | None, row["appointment_reason"]),
        )

    async def mark_room1_final_reply_posted(
        self,
        *,
        case_id: UUID,
        room1_final_reply_event_id: str,
    ) -> bool:
        """Store Room-1 final reply event id and transition to cleanup-wait state."""

        statement = (
            sa.update(cases)
            .where(
                cases.c.case_id == case_id,
                cases.c.room1_final_reply_event_id.is_(None),
            )
            .values(
                room1_final_reply_event_id=room1_final_reply_event_id,
                room1_final_reply_posted_at=sa.func.current_timestamp(),
                status=CaseStatus.WAIT_R1_CLEANUP_THUMBS.value,
                updated_at=sa.func.current_timestamp(),
            )
        )

        async with self._session_factory() as session:
            result = cast(CursorResult[Any], await session.execute(statement))
            await session.commit()

        return int(result.rowcount or 0) == 1

    async def get_by_room1_final_reply_event_id(
        self,
        *,
        room1_final_reply_event_id: str,
    ) -> Room1FinalReplyReactionSnapshot | None:
        """Return cleanup-trigger snapshot by Room-1 final reply event id."""

        statement = sa.select(
            cases.c.case_id,
            cases.c.status,
            cases.c.cleanup_triggered_at,
        ).where(cases.c.room1_final_reply_event_id == room1_final_reply_event_id)

        async with self._session_factory() as session:
            result = await session.execute(statement)

        row = result.mappings().first()
        if row is None:
            return None

        return Room1FinalReplyReactionSnapshot(
            case_id=cast("Any", row["case_id"]),
            status=CaseStatus(cast(str, row["status"])),
            cleanup_triggered_at=cast(datetime | None, row["cleanup_triggered_at"]),
        )

    async def claim_cleanup_trigger_if_first(
        self,
        *,
        case_id: UUID,
        reactor_user_id: str,
    ) -> bool:
        """Atomically claim first cleanup trigger and transition to CLEANUP_RUNNING."""

        statement = (
            sa.update(cases)
            .where(
                cases.c.case_id == case_id,
                cases.c.status == CaseStatus.WAIT_R1_CLEANUP_THUMBS.value,
                cases.c.cleanup_triggered_at.is_(None),
            )
            .values(
                cleanup_triggered_at=sa.func.current_timestamp(),
                cleanup_triggered_by_user_id=reactor_user_id,
                status=CaseStatus.CLEANUP_RUNNING.value,
                updated_at=sa.func.current_timestamp(),
            )
        )

        async with self._session_factory() as session:
            result = cast(CursorResult[Any], await session.execute(statement))
            await session.commit()

        return int(result.rowcount or 0) == 1

    async def mark_cleanup_completed(self, *, case_id: UUID) -> None:
        """Mark cleanup completion timestamp and transition case to CLEANED."""

        statement = (
            sa.update(cases)
            .where(cases.c.case_id == case_id)
            .values(
                cleanup_completed_at=sa.func.current_timestamp(),
                status=CaseStatus.CLEANED.value,
                updated_at=sa.func.current_timestamp(),
            )
        )

        async with self._session_factory() as session:
            await session.execute(statement)
            await session.commit()

    async def list_non_terminal_cases_for_recovery(self) -> list[CaseRecoverySnapshot]:
        """List non-cleaned cases for startup recovery reconciliation."""

        statement = sa.select(
            cases.c.case_id,
            cases.c.status,
            cases.c.room1_final_reply_event_id,
            cases.c.cleanup_triggered_at,
            cases.c.cleanup_completed_at,
        ).where(cases.c.status != CaseStatus.CLEANED.value)

        async with self._session_factory() as session:
            result = await session.execute(statement)

        snapshots: list[CaseRecoverySnapshot] = []
        for row in result.mappings().all():
            snapshots.append(
                CaseRecoverySnapshot(
                    case_id=cast("Any", row["case_id"]),
                    status=CaseStatus(cast(str, row["status"])),
                    room1_final_reply_event_id=cast(str | None, row["room1_final_reply_event_id"]),
                    cleanup_triggered_at=cast(datetime | None, row["cleanup_triggered_at"]),
                    cleanup_completed_at=cast(datetime | None, row["cleanup_completed_at"]),
                )
            )
        return snapshots

    async def update_status(self, *, case_id: UUID, status: CaseStatus) -> None:
        """Update case status and touch updated_at timestamp."""

        statement = (
            sa.update(cases)
            .where(cases.c.case_id == case_id)
            .values(status=status.value, updated_at=sa.func.current_timestamp())
        )

        async with self._session_factory() as session:
            await session.execute(statement)
            await session.commit()

    async def store_pdf_extraction(
        self,
        *,
        case_id: UUID,
        pdf_mxc_url: str,
        extracted_text: str,
        agency_record_number: str | None = None,
        agency_record_extracted_at: datetime | None = None,
    ) -> None:
        """Persist extracted PDF text and optional agency record metadata."""

        statement = (
            sa.update(cases)
            .where(cases.c.case_id == case_id)
            .values(
                pdf_mxc_url=pdf_mxc_url,
                extracted_text=extracted_text,
                agency_record_number=agency_record_number,
                agency_record_extracted_at=agency_record_extracted_at,
                updated_at=sa.func.current_timestamp(),
            )
        )

        async with self._session_factory() as session:
            await session.execute(statement)
            await session.commit()

    async def store_llm1_artifacts(
        self,
        *,
        case_id: UUID,
        structured_data_json: dict[str, Any],
        summary_text: str,
    ) -> None:
        """Persist validated LLM1 structured payload and summary text."""

        statement = (
            sa.update(cases)
            .where(cases.c.case_id == case_id)
            .values(
                structured_data_json=structured_data_json,
                summary_text=summary_text,
                updated_at=sa.func.current_timestamp(),
            )
        )

        async with self._session_factory() as session:
            await session.execute(statement)
            await session.commit()

    async def store_llm2_artifacts(
        self,
        *,
        case_id: UUID,
        suggested_action_json: dict[str, Any],
    ) -> None:
        """Persist validated and reconciled LLM2 suggestion payload."""

        statement = (
            sa.update(cases)
            .where(cases.c.case_id == case_id)
            .values(
                suggested_action_json=suggested_action_json,
                updated_at=sa.func.current_timestamp(),
            )
        )

        async with self._session_factory() as session:
            await session.execute(statement)
            await session.commit()

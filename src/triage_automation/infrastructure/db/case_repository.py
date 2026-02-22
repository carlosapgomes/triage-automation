"""SQLAlchemy adapter for case repository operations."""

from __future__ import annotations

import logging
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
    CaseLlmInteractionCreateInput,
    CaseMonitoringDetail,
    CaseMonitoringListFilter,
    CaseMonitoringListItem,
    CaseMonitoringListPage,
    CaseMonitoringTimelineItem,
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

logger = logging.getLogger(__name__)

case_report_transcripts = sa.table(
    "case_report_transcripts",
    sa.column("id", sa.Integer()),
    sa.column("case_id", sa.Uuid()),
    sa.column("extracted_text", sa.Text()),
    sa.column("captured_at", sa.DateTime(timezone=True)),
)
case_llm_interactions = sa.table(
    "case_llm_interactions",
    sa.column("id", sa.Integer()),
    sa.column("case_id", sa.Uuid()),
    sa.column("stage", sa.Text()),
    sa.column("input_payload", sa.JSON()),
    sa.column("output_payload", sa.JSON()),
    sa.column("prompt_system_name", sa.Text()),
    sa.column("prompt_system_version", sa.Integer()),
    sa.column("prompt_user_name", sa.Text()),
    sa.column("prompt_user_version", sa.Integer()),
    sa.column("model_name", sa.Text()),
    sa.column("captured_at", sa.DateTime(timezone=True)),
)
case_matrix_message_transcripts = sa.table(
    "case_matrix_message_transcripts",
    sa.column("id", sa.Integer()),
    sa.column("case_id", sa.Uuid()),
    sa.column("room_id", sa.Text()),
    sa.column("event_id", sa.Text()),
    sa.column("sender", sa.Text()),
    sa.column("sender_display_name", sa.Text()),
    sa.column("message_type", sa.Text()),
    sa.column("message_text", sa.Text()),
    sa.column("reply_to_event_id", sa.Text()),
    sa.column("captured_at", sa.DateTime(timezone=True)),
)
case_reaction_checkpoints = sa.table(
    "case_reaction_checkpoints",
    sa.column("id", sa.BigInteger()),
    sa.column("case_id", sa.Uuid()),
    sa.column("stage", sa.Text()),
    sa.column("room_id", sa.Text()),
    sa.column("target_event_id", sa.Text()),
    sa.column("expected_at", sa.DateTime(timezone=True)),
    sa.column("outcome", sa.Text()),
    sa.column("reaction_event_id", sa.Text()),
    sa.column("reactor_user_id", sa.Text()),
    sa.column("reactor_display_name", sa.Text()),
    sa.column("reaction_key", sa.Text()),
    sa.column("reacted_at", sa.DateTime(timezone=True)),
)


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


def _extract_patient_name_from_structured_data(
    structured_data_json: dict[str, Any] | None,
) -> str | None:
    """Extract normalized patient name from structured case payload."""

    if not isinstance(structured_data_json, dict):
        return None
    patient_raw = structured_data_json.get("patient")
    if not isinstance(patient_raw, dict):
        patient_raw = structured_data_json.get("paciente")
    if not isinstance(patient_raw, dict):
        return None
    candidate = patient_raw.get("name")
    if not isinstance(candidate, str) or not candidate.strip():
        candidate = patient_raw.get("nome")
    if not isinstance(candidate, str):
        return None
    normalized = candidate.strip()
    if not normalized:
        return None
    return normalized


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
        created = _to_case_record(row)
        logger.info(
            "case_created case_id=%s status=%s origin_event_id=%s",
            created.case_id,
            created.status.value,
            created.room1_origin_event_id,
        )
        return created

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
            cases.c.pdf_mxc_url,
            cases.c.extracted_text,
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
            pdf_mxc_url=cast(str | None, row["pdf_mxc_url"]),
            extracted_text=cast(str | None, row["extracted_text"]),
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
        """Return status and decision context used by doctor/scheduler flows."""

        statement = sa.select(
            cases.c.case_id,
            cases.c.status,
            cases.c.doctor_decided_at,
            cases.c.agency_record_number,
            cases.c.structured_data_json,
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
            agency_record_number=cast(str | None, row["agency_record_number"]),
            structured_data_json=cast(dict[str, Any] | None, row["structured_data_json"]),
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

        applied = int(result.rowcount or 0) == 1
        logger.info(
            (
                "case_doctor_decision_applied=%s case_id=%s from_status=%s to_status=%s "
                "decision=%s support_flag=%s doctor_user_id=%s"
            ),
            applied,
            payload.case_id,
            CaseStatus.WAIT_DOCTOR.value,
            target_status.value,
            payload.decision,
            payload.support_flag,
            payload.doctor_user_id,
        )
        return applied

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

        applied = int(result.rowcount or 0) == 1
        logger.info(
            (
                "case_scheduler_decision_applied=%s case_id=%s from_status=%s to_status=%s "
                "appointment_status=%s scheduler_user_id=%s"
            ),
            applied,
            payload.case_id,
            CaseStatus.WAIT_APPT.value,
            target_status.value,
            payload.appointment_status,
            payload.scheduler_user_id,
        )
        return applied

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
            cases.c.agency_record_number,
            cases.c.structured_data_json,
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
            agency_record_number=cast(str | None, row["agency_record_number"]),
            structured_data_json=cast(dict[str, Any] | None, row["structured_data_json"]),
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

        applied = int(result.rowcount or 0) == 1
        logger.info(
            (
                "case_final_reply_marked=%s case_id=%s to_status=%s "
                "room1_final_reply_event_id=%s"
            ),
            applied,
            case_id,
            CaseStatus.WAIT_R1_CLEANUP_THUMBS.value,
            room1_final_reply_event_id,
        )
        return applied

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

        claimed = int(result.rowcount or 0) == 1
        logger.info(
            (
                "case_cleanup_trigger_claimed=%s case_id=%s from_status=%s to_status=%s "
                "reactor_user_id=%s"
            ),
            claimed,
            case_id,
            CaseStatus.WAIT_R1_CLEANUP_THUMBS.value,
            CaseStatus.CLEANUP_RUNNING.value,
            reactor_user_id,
        )
        return claimed

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
        logger.info(
            "case_cleanup_completed case_id=%s to_status=%s",
            case_id,
            CaseStatus.CLEANED.value,
        )

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

    async def list_cases_for_monitoring(
        self,
        *,
        filters: CaseMonitoringListFilter,
    ) -> CaseMonitoringListPage:
        """List cases ordered by latest activity with period/status filtering."""

        activity_rows = sa.union_all(
            sa.select(
                cases.c.case_id.label("case_id"),
                cases.c.updated_at.label("activity_at"),
            ),
            sa.select(
                case_report_transcripts.c.case_id.label("case_id"),
                case_report_transcripts.c.captured_at.label("activity_at"),
            ),
            sa.select(
                case_llm_interactions.c.case_id.label("case_id"),
                case_llm_interactions.c.captured_at.label("activity_at"),
            ),
            sa.select(
                case_matrix_message_transcripts.c.case_id.label("case_id"),
                case_matrix_message_transcripts.c.captured_at.label("activity_at"),
            ),
            sa.select(
                case_reaction_checkpoints.c.case_id.label("case_id"),
                case_reaction_checkpoints.c.expected_at.label("activity_at"),
            ),
            sa.select(
                case_reaction_checkpoints.c.case_id.label("case_id"),
                case_reaction_checkpoints.c.reacted_at.label("activity_at"),
            ).where(case_reaction_checkpoints.c.reacted_at.is_not(None)),
        ).subquery("case_activity_rows")

        latest_activity = (
            sa.select(
                activity_rows.c.case_id,
                sa.func.max(activity_rows.c.activity_at).label("latest_activity_at"),
            )
            .group_by(activity_rows.c.case_id)
            .subquery("case_latest_activity")
        )
        from_clause = cases.join(latest_activity, latest_activity.c.case_id == cases.c.case_id)
        where_clauses: list[sa.ColumnElement[bool]] = []
        if filters.status is not None:
            where_clauses.append(cases.c.status == filters.status.value)
        if filters.activity_from is not None:
            where_clauses.append(latest_activity.c.latest_activity_at >= filters.activity_from)
        if filters.activity_to is not None:
            where_clauses.append(latest_activity.c.latest_activity_at < filters.activity_to)

        total_statement = sa.select(sa.func.count()).select_from(from_clause)
        if where_clauses:
            total_statement = total_statement.where(*where_clauses)

        offset = (filters.page - 1) * filters.page_size
        statement = (
            sa.select(
                cases.c.case_id,
                cases.c.status,
                latest_activity.c.latest_activity_at,
                cases.c.agency_record_number,
                cases.c.structured_data_json,
            )
            .select_from(from_clause)
            .order_by(
                latest_activity.c.latest_activity_at.desc(),
                cases.c.case_id.desc(),
            )
            .offset(offset)
            .limit(filters.page_size)
        )
        if where_clauses:
            statement = statement.where(*where_clauses)

        async with self._session_factory() as session:
            total_result = await session.execute(total_statement)
            result = await session.execute(statement)

        total = int(total_result.scalar_one())
        items: list[CaseMonitoringListItem] = []
        for row in result.mappings().all():
            structured_data_json = cast(dict[str, Any] | None, row["structured_data_json"])
            items.append(
                CaseMonitoringListItem(
                    case_id=cast("Any", row["case_id"]),
                    status=CaseStatus(cast(str, row["status"])),
                    latest_activity_at=cast(datetime, row["latest_activity_at"]),
                    patient_name=_extract_patient_name_from_structured_data(structured_data_json),
                    agency_record_number=cast(str | None, row["agency_record_number"]),
                )
            )
        return CaseMonitoringListPage(
            items=items,
            page=filters.page,
            page_size=filters.page_size,
            total=total,
        )

    async def get_case_monitoring_detail(
        self,
        *,
        case_id: UUID,
    ) -> CaseMonitoringDetail | None:
        """Return one case status with unified timeline events ordered chronologically."""

        case_statement = sa.select(
            cases.c.case_id,
            cases.c.status,
            cases.c.structured_data_json,
            cases.c.agency_record_number,
        ).where(cases.c.case_id == case_id)
        report_statement = (
            sa.select(
                case_report_transcripts.c.id,
                case_report_transcripts.c.captured_at,
                case_report_transcripts.c.extracted_text,
            )
            .where(case_report_transcripts.c.case_id == case_id)
            .order_by(
                case_report_transcripts.c.captured_at.asc(),
                case_report_transcripts.c.id.asc(),
            )
        )
        llm_statement = (
            sa.select(
                case_llm_interactions.c.id,
                case_llm_interactions.c.captured_at,
                case_llm_interactions.c.stage,
                case_llm_interactions.c.input_payload,
                case_llm_interactions.c.output_payload,
                case_llm_interactions.c.prompt_system_name,
                case_llm_interactions.c.prompt_system_version,
                case_llm_interactions.c.prompt_user_name,
                case_llm_interactions.c.prompt_user_version,
                case_llm_interactions.c.model_name,
            )
            .where(case_llm_interactions.c.case_id == case_id)
            .order_by(case_llm_interactions.c.captured_at.asc(), case_llm_interactions.c.id.asc())
        )
        matrix_statement = (
            sa.select(
                case_matrix_message_transcripts.c.id,
                case_matrix_message_transcripts.c.captured_at,
                case_matrix_message_transcripts.c.room_id,
                case_matrix_message_transcripts.c.event_id,
                case_matrix_message_transcripts.c.sender,
                case_matrix_message_transcripts.c.sender_display_name,
                case_matrix_message_transcripts.c.message_type,
                case_matrix_message_transcripts.c.message_text,
                case_matrix_message_transcripts.c.reply_to_event_id,
            )
            .where(case_matrix_message_transcripts.c.case_id == case_id)
            .order_by(
                case_matrix_message_transcripts.c.captured_at.asc(),
                case_matrix_message_transcripts.c.id.asc(),
            )
        )
        reaction_checkpoints_statement = (
            sa.select(
                case_reaction_checkpoints.c.id,
                case_reaction_checkpoints.c.stage,
                case_reaction_checkpoints.c.room_id,
                case_reaction_checkpoints.c.target_event_id,
                case_reaction_checkpoints.c.expected_at,
                case_reaction_checkpoints.c.outcome,
                case_reaction_checkpoints.c.reaction_event_id,
                case_reaction_checkpoints.c.reactor_user_id,
                case_reaction_checkpoints.c.reactor_display_name,
                case_reaction_checkpoints.c.reaction_key,
                case_reaction_checkpoints.c.reacted_at,
            )
            .where(case_reaction_checkpoints.c.case_id == case_id)
            .order_by(
                case_reaction_checkpoints.c.expected_at.asc(),
                case_reaction_checkpoints.c.id.asc(),
            )
        )

        async with self._session_factory() as session:
            case_result = await session.execute(case_statement)
            case_row = case_result.mappings().first()
            if case_row is None:
                return None

            report_rows = (await session.execute(report_statement)).mappings().all()
            llm_rows = (await session.execute(llm_statement)).mappings().all()
            matrix_rows = (await session.execute(matrix_statement)).mappings().all()
            reaction_checkpoint_rows = (
                await session.execute(reaction_checkpoints_statement)
            ).mappings().all()

        sortable_events: list[tuple[datetime, int, int, CaseMonitoringTimelineItem]] = []
        for row in report_rows:
            sortable_events.append(
                (
                    cast(datetime, row["captured_at"]),
                    0,
                    int(row["id"]),
                    CaseMonitoringTimelineItem(
                        source="pdf",
                        channel="pdf",
                        timestamp=cast(datetime, row["captured_at"]),
                        room_id=None,
                        actor="system",
                        event_type="pdf_report_extracted",
                        content_text=cast(str, row["extracted_text"]),
                        payload=None,
                    ),
                )
            )
        for row in llm_rows:
            sortable_events.append(
                (
                    cast(datetime, row["captured_at"]),
                    1,
                    int(row["id"]),
                    CaseMonitoringTimelineItem(
                        source="llm",
                        channel="llm",
                        timestamp=cast(datetime, row["captured_at"]),
                        room_id=None,
                        actor="llm",
                        event_type=cast(str, row["stage"]),
                        content_text=None,
                        payload={
                            "input_payload": cast(dict[str, Any], row["input_payload"]),
                            "output_payload": cast(dict[str, Any], row["output_payload"]),
                            "prompt_system_name": cast(str | None, row["prompt_system_name"]),
                            "prompt_system_version": cast(
                                int | None, row["prompt_system_version"]
                            ),
                            "prompt_user_name": cast(str | None, row["prompt_user_name"]),
                            "prompt_user_version": cast(int | None, row["prompt_user_version"]),
                            "model_name": cast(str | None, row["model_name"]),
                        },
                    ),
                )
            )
        for row in matrix_rows:
            sortable_events.append(
                (
                    cast(datetime, row["captured_at"]),
                    2,
                    int(row["id"]),
                    CaseMonitoringTimelineItem(
                        source="matrix",
                        channel=cast(str, row["room_id"]),
                        timestamp=cast(datetime, row["captured_at"]),
                        room_id=cast(str, row["room_id"]),
                        actor=cast(str | None, row["sender_display_name"])
                        or cast(str, row["sender"]),
                        event_type=cast(str, row["message_type"]),
                        content_text=cast(str, row["message_text"]),
                        payload={
                            "event_id": cast(str, row["event_id"]),
                            "reply_to_event_id": cast(str | None, row["reply_to_event_id"]),
                        },
                    ),
                )
            )
        for row in reaction_checkpoint_rows:
            stage = cast(str, row["stage"])
            room_id = cast(str, row["room_id"])
            target_event_id = cast(str, row["target_event_id"])
            expected_at = cast(datetime, row["expected_at"])
            outcome = cast(str, row["outcome"])
            sortable_events.append(
                (
                    expected_at,
                    3,
                    int(row["id"]),
                    CaseMonitoringTimelineItem(
                        source="matrix",
                        channel=room_id,
                        timestamp=expected_at,
                        room_id=room_id,
                        actor="system",
                        event_type=f"{stage}_POSITIVE_EXPECTED",
                        content_text=None,
                        payload={
                            "stage": stage,
                            "target_event_id": target_event_id,
                            "outcome": outcome,
                        },
                    ),
                )
            )
            if outcome != "POSITIVE_RECEIVED":
                continue
            reacted_at = cast(datetime | None, row["reacted_at"])
            if reacted_at is None:
                continue
            sortable_events.append(
                (
                    reacted_at,
                    4,
                    int(row["id"]),
                    CaseMonitoringTimelineItem(
                        source="matrix",
                        channel=room_id,
                        timestamp=reacted_at,
                        room_id=room_id,
                        actor=cast(str | None, row["reactor_display_name"])
                        or cast(str | None, row["reactor_user_id"])
                        or "human",
                        event_type=f"{stage}_POSITIVE_RECEIVED",
                        content_text=None,
                        payload={
                            "stage": stage,
                            "target_event_id": target_event_id,
                            "reaction_event_id": cast(str | None, row["reaction_event_id"]),
                            "reaction_key": cast(str | None, row["reaction_key"]),
                            "expected_at": expected_at.isoformat(),
                        },
                    ),
                )
            )

        sortable_events.sort(key=lambda item: (item[0], item[1], item[2]))
        timeline = [item[3] for item in sortable_events]
        structured_data_json = cast(dict[str, Any] | None, case_row["structured_data_json"])
        return CaseMonitoringDetail(
            case_id=cast("Any", case_row["case_id"]),
            status=CaseStatus(cast(str, case_row["status"])),
            timeline=timeline,
            patient_name=_extract_patient_name_from_structured_data(structured_data_json),
            agency_record_number=cast(str | None, case_row["agency_record_number"]),
        )

    async def update_status(self, *, case_id: UUID, status: CaseStatus) -> None:
        """Update case status and touch updated_at timestamp."""

        statement = (
            sa.update(cases)
            .where(cases.c.case_id == case_id)
            .values(status=status.value, updated_at=sa.func.current_timestamp())
        )

        async with self._session_factory() as session:
            result = cast(CursorResult[Any], await session.execute(statement))
            await session.commit()
        logger.info(
            "case_status_updated case_id=%s to_status=%s affected_rows=%s",
            case_id,
            status.value,
            int(result.rowcount or 0),
        )

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
            result = cast(CursorResult[Any], await session.execute(statement))
            await session.commit()
        logger.info(
            (
                "case_pdf_extraction_stored case_id=%s agency_record_number=%s "
                "extracted_text_chars=%s affected_rows=%s"
            ),
            case_id,
            agency_record_number,
            len(extracted_text),
            int(result.rowcount or 0),
        )

    async def append_case_report_transcript(
        self,
        *,
        case_id: UUID,
        extracted_text: str,
    ) -> None:
        """Append full extracted report text for audit timeline reconstruction."""

        statement = sa.insert(case_report_transcripts).values(
            case_id=case_id,
            extracted_text=extracted_text,
        )

        async with self._session_factory() as session:
            await session.execute(statement)
            await session.commit()
        logger.info(
            "case_report_transcript_appended case_id=%s extracted_text_chars=%s",
            case_id,
            len(extracted_text),
        )

    async def append_case_llm_interaction(self, payload: CaseLlmInteractionCreateInput) -> None:
        """Append one LLM interaction transcript row for later timeline retrieval."""

        statement = sa.insert(case_llm_interactions).values(
            case_id=payload.case_id,
            stage=payload.stage,
            input_payload=payload.input_payload,
            output_payload=payload.output_payload,
            prompt_system_name=payload.prompt_system_name,
            prompt_system_version=payload.prompt_system_version,
            prompt_user_name=payload.prompt_user_name,
            prompt_user_version=payload.prompt_user_version,
            model_name=payload.model_name,
        )

        async with self._session_factory() as session:
            await session.execute(statement)
            await session.commit()
        logger.info(
            (
                "case_llm_interaction_appended case_id=%s stage=%s "
                "prompt_system=%s@%s prompt_user=%s@%s model_name=%s"
            ),
            payload.case_id,
            payload.stage,
            payload.prompt_system_name,
            payload.prompt_system_version,
            payload.prompt_user_name,
            payload.prompt_user_version,
            payload.model_name,
        )

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
            result = cast(CursorResult[Any], await session.execute(statement))
            await session.commit()
        logger.info(
            "case_llm1_artifacts_stored case_id=%s summary_chars=%s affected_rows=%s",
            case_id,
            len(summary_text),
            int(result.rowcount or 0),
        )

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
            result = cast(CursorResult[Any], await session.execute(statement))
            await session.commit()
        logger.info(
            "case_llm2_artifacts_stored case_id=%s suggestion=%s affected_rows=%s",
            case_id,
            suggested_action_json.get("suggestion"),
            int(result.rowcount or 0),
        )

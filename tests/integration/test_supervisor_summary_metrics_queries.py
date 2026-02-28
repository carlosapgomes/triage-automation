from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
import sqlalchemy as sa
from alembic.config import Config

from alembic import command
from triage_automation.application.ports.case_repository_port import CaseCreateInput
from triage_automation.domain.case_status import CaseStatus
from triage_automation.infrastructure.db.case_repository import SqlAlchemyCaseRepository
from triage_automation.infrastructure.db.session import create_session_factory
from triage_automation.infrastructure.db.supervisor_summary_metrics_queries import (
    SqlAlchemySupervisorSummaryMetricsQueries,
)


def _upgrade_head(tmp_path: Path, filename: str) -> tuple[str, str]:
    db_path = tmp_path / filename
    sync_url = f"sqlite+pysqlite:///{db_path}"
    async_url = f"sqlite+aiosqlite:///{db_path}"

    alembic_config = Config("alembic.ini")
    alembic_config.set_main_option("sqlalchemy.url", sync_url)
    command.upgrade(alembic_config, "head")

    return sync_url, async_url


@pytest.mark.asyncio
async def test_metrics_query_counts_patients_reports_and_evaluated_in_window(
    tmp_path: Path,
) -> None:
    sync_url, async_url = _upgrade_head(tmp_path, "supervisor_summary_metrics.db")
    session_factory = create_session_factory(async_url)
    case_repository = SqlAlchemyCaseRepository(session_factory)
    queries = SqlAlchemySupervisorSummaryMetricsQueries(session_factory)

    in_window_case_id = uuid4()
    out_window_case_id = uuid4()
    await case_repository.create_case(
        CaseCreateInput(
            case_id=in_window_case_id,
            status=CaseStatus.WAIT_DOCTOR,
            room1_origin_room_id="!room1:example.org",
            room1_origin_event_id="$origin-in-window",
            room1_sender_user_id="@human:example.org",
        )
    )
    await case_repository.create_case(
        CaseCreateInput(
            case_id=out_window_case_id,
            status=CaseStatus.WAIT_DOCTOR,
            room1_origin_room_id="!room1:example.org",
            room1_origin_event_id="$origin-out-window",
            room1_sender_user_id="@human:example.org",
        )
    )

    window_start = datetime(2026, 2, 16, 10, 0, tzinfo=UTC)
    window_end = datetime(2026, 2, 16, 22, 0, tzinfo=UTC)

    engine = sa.create_engine(sync_url)
    with engine.begin() as connection:
        connection.execute(
            sa.text(
                "UPDATE cases SET created_at = :ts, doctor_decided_at = :doctor_ts "
                "WHERE case_id = :case_id"
            ),
            {
                "ts": datetime(2026, 2, 16, 11, 0, tzinfo=UTC),
                "doctor_ts": datetime(2026, 2, 16, 12, 0, tzinfo=UTC),
                "case_id": in_window_case_id.hex,
            },
        )
        connection.execute(
            sa.text(
                "UPDATE cases SET created_at = :ts, doctor_decided_at = :doctor_ts "
                "WHERE case_id = :case_id"
            ),
            {
                "ts": datetime(2026, 2, 16, 9, 59, tzinfo=UTC),
                "doctor_ts": datetime(2026, 2, 16, 22, 1, tzinfo=UTC),
                "case_id": out_window_case_id.hex,
            },
        )
        connection.execute(
            sa.text(
                "INSERT INTO case_report_transcripts (case_id, extracted_text, captured_at) "
                "VALUES (:case_id, :extracted_text, :captured_at)"
            ),
            {
                "case_id": in_window_case_id.hex,
                "extracted_text": "texto-1",
                "captured_at": datetime(2026, 2, 16, 13, 0, tzinfo=UTC),
            },
        )
        connection.execute(
            sa.text(
                "INSERT INTO case_report_transcripts (case_id, extracted_text, captured_at) "
                "VALUES (:case_id, :extracted_text, :captured_at)"
            ),
            {
                "case_id": out_window_case_id.hex,
                "extracted_text": "texto-2",
                "captured_at": datetime(2026, 2, 16, 21, 59, tzinfo=UTC),
            },
        )
        connection.execute(
            sa.text(
                "INSERT INTO case_report_transcripts (case_id, extracted_text, captured_at) "
                "VALUES (:case_id, :extracted_text, :captured_at)"
            ),
            {
                "case_id": out_window_case_id.hex,
                "extracted_text": "texto-outside",
                "captured_at": datetime(2026, 2, 16, 22, 1, tzinfo=UTC),
            },
        )

    metrics = await queries.aggregate_metrics(
        window_start=window_start,
        window_end=window_end,
    )

    assert metrics.patients_received == 1
    assert metrics.reports_processed == 2
    assert metrics.cases_evaluated == 1


@pytest.mark.asyncio
async def test_metrics_query_counts_final_outcomes_for_accepted_and_refused(
    tmp_path: Path,
) -> None:
    sync_url, async_url = _upgrade_head(tmp_path, "supervisor_summary_metrics_outcomes.db")
    session_factory = create_session_factory(async_url)
    case_repository = SqlAlchemyCaseRepository(session_factory)
    queries = SqlAlchemySupervisorSummaryMetricsQueries(session_factory)

    accepted_case_id = uuid4()
    doctor_denied_case_id = uuid4()
    appt_denied_case_id = uuid4()
    accepted_outside_case_id = uuid4()
    denied_outside_case_id = uuid4()
    doctor_accepted_in_window_case_id = uuid4()

    for case_id in (
        accepted_case_id,
        doctor_denied_case_id,
        appt_denied_case_id,
        accepted_outside_case_id,
        denied_outside_case_id,
        doctor_accepted_in_window_case_id,
    ):
        await case_repository.create_case(
            CaseCreateInput(
                case_id=case_id,
                status=CaseStatus.WAIT_DOCTOR,
                room1_origin_room_id="!room1:example.org",
                room1_origin_event_id=f"$origin-{case_id}",
                room1_sender_user_id="@human:example.org",
            )
        )

    window_start = datetime(2026, 2, 16, 10, 0, tzinfo=UTC)
    window_end = datetime(2026, 2, 16, 22, 0, tzinfo=UTC)

    engine = sa.create_engine(sync_url)
    with engine.begin() as connection:
        connection.execute(
            sa.text(
                "UPDATE cases SET status = :status, appointment_status = :appointment_status, "
                "appointment_decided_at = :appointment_decided_at WHERE case_id = :case_id"
            ),
            {
                "status": CaseStatus.APPT_CONFIRMED.value,
                "appointment_status": "confirmed",
                "appointment_decided_at": datetime(2026, 2, 16, 11, 0, tzinfo=UTC),
                "case_id": accepted_case_id.hex,
            },
        )
        connection.execute(
            sa.text(
                "UPDATE cases SET status = :status, doctor_decision = :doctor_decision, "
                "doctor_decided_at = :doctor_decided_at WHERE case_id = :case_id"
            ),
            {
                "status": CaseStatus.DOCTOR_DENIED.value,
                "doctor_decision": "deny",
                "doctor_decided_at": datetime(2026, 2, 16, 12, 0, tzinfo=UTC),
                "case_id": doctor_denied_case_id.hex,
            },
        )
        connection.execute(
            sa.text(
                "UPDATE cases SET status = :status, appointment_status = :appointment_status, "
                "appointment_decided_at = :appointment_decided_at WHERE case_id = :case_id"
            ),
            {
                "status": CaseStatus.APPT_DENIED.value,
                "appointment_status": "denied",
                "appointment_decided_at": datetime(2026, 2, 16, 13, 0, tzinfo=UTC),
                "case_id": appt_denied_case_id.hex,
            },
        )
        connection.execute(
            sa.text(
                "UPDATE cases SET status = :status, appointment_status = :appointment_status, "
                "appointment_decided_at = :appointment_decided_at WHERE case_id = :case_id"
            ),
            {
                "status": CaseStatus.APPT_CONFIRMED.value,
                "appointment_status": "confirmed",
                "appointment_decided_at": datetime(2026, 2, 16, 22, 1, tzinfo=UTC),
                "case_id": accepted_outside_case_id.hex,
            },
        )
        connection.execute(
            sa.text(
                "UPDATE cases SET status = :status, doctor_decision = :doctor_decision, "
                "doctor_decided_at = :doctor_decided_at WHERE case_id = :case_id"
            ),
            {
                "status": CaseStatus.DOCTOR_DENIED.value,
                "doctor_decision": "deny",
                "doctor_decided_at": datetime(2026, 2, 16, 9, 59, tzinfo=UTC),
                "case_id": denied_outside_case_id.hex,
            },
        )
        connection.execute(
            sa.text(
                "UPDATE cases SET status = :status, doctor_decision = :doctor_decision, "
                "doctor_decided_at = :doctor_decided_at WHERE case_id = :case_id"
            ),
            {
                "status": CaseStatus.DOCTOR_ACCEPTED.value,
                "doctor_decision": "accept",
                "doctor_decided_at": datetime(2026, 2, 16, 14, 0, tzinfo=UTC),
                "case_id": doctor_accepted_in_window_case_id.hex,
            },
        )

    metrics = await queries.aggregate_metrics(
        window_start=window_start,
        window_end=window_end,
    )

    assert metrics.accepted == 1
    assert metrics.refused == 2

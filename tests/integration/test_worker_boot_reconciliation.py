from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
import sqlalchemy as sa
from alembic.config import Config

from alembic import command
from apps.worker.main import run_worker_startup
from triage_automation.application.ports.case_repository_port import CaseCreateInput
from triage_automation.domain.case_status import CaseStatus
from triage_automation.infrastructure.db.case_repository import SqlAlchemyCaseRepository
from triage_automation.infrastructure.db.session import create_session_factory
from triage_automation.infrastructure.db.worker_bootstrap import reconcile_running_jobs


def _upgrade_head(tmp_path: Path, filename: str) -> tuple[str, str]:
    db_path = tmp_path / filename
    sync_url = f"sqlite+pysqlite:///{db_path}"
    async_url = f"sqlite+aiosqlite:///{db_path}"

    alembic_config = Config("alembic.ini")
    alembic_config.set_main_option("sqlalchemy.url", sync_url)
    command.upgrade(alembic_config, "head")

    return sync_url, async_url


def _insert_job(connection: sa.Connection, *, status: str, attempts: int) -> int:
    job_id = connection.execute(
        sa.text(
            """
            INSERT INTO jobs (job_type, status, attempts, max_attempts)
            VALUES ('process_pdf_case', :status, :attempts, 5)
            RETURNING job_id
            """
        ),
        {"status": status, "attempts": attempts},
    ).scalar_one()
    return int(job_id)


@pytest.mark.asyncio
async def test_reconcile_resets_running_to_queued_with_same_attempts(tmp_path: Path) -> None:
    sync_url, async_url = _upgrade_head(tmp_path, "reconcile.db")

    engine = sa.create_engine(sync_url)
    with engine.begin() as connection:
        running_zero = _insert_job(connection, status="running", attempts=0)
        running_two = _insert_job(connection, status="running", attempts=2)
        done_job = _insert_job(connection, status="done", attempts=3)

    session_factory = create_session_factory(async_url)
    updated_count = await reconcile_running_jobs(session_factory)

    assert updated_count == 2

    with engine.begin() as connection:
        rows = connection.execute(
            sa.text(
                "SELECT job_id, status, attempts FROM jobs ORDER BY job_id"
            )
        ).mappings().all()

    by_id = {int(row["job_id"]): row for row in rows}

    assert by_id[running_zero]["status"] == "queued"
    assert int(by_id[running_zero]["attempts"]) == 0

    assert by_id[running_two]["status"] == "queued"
    assert int(by_id[running_two]["attempts"]) == 2

    assert by_id[done_job]["status"] == "done"
    assert int(by_id[done_job]["attempts"]) == 3


@pytest.mark.asyncio
async def test_worker_startup_reconciles_running_jobs_before_recovery_scan(
    tmp_path: Path,
) -> None:
    sync_url, async_url = _upgrade_head(tmp_path, "worker_startup_reconcile_then_recover.db")

    engine = sa.create_engine(sync_url)
    with engine.begin() as connection:
        running_job_id = _insert_job(connection, status="running", attempts=2)

    session_factory = create_session_factory(async_url)
    case_repo = SqlAlchemyCaseRepository(session_factory)
    doctor_accepted_case = await case_repo.create_case(
        CaseCreateInput(
            case_id=uuid4(),
            status=CaseStatus.DOCTOR_ACCEPTED,
            room1_origin_room_id="!room1:example.org",
            room1_origin_event_id="$origin-startup-recover",
            room1_sender_user_id="@human:example.org",
        )
    )

    startup_result = await run_worker_startup(session_factory=session_factory)

    assert startup_result.reconciled_jobs == 1
    assert startup_result.recovery.enqueued_jobs == 1

    with engine.begin() as connection:
        running_row = connection.execute(
            sa.text("SELECT status, attempts FROM jobs WHERE job_id = :job_id"),
            {"job_id": running_job_id},
        ).mappings().one()
        recovery_jobs = connection.execute(
            sa.text(
                "SELECT job_type FROM jobs WHERE case_id = :case_id ORDER BY job_id"
            ),
            {"case_id": doctor_accepted_case.case_id.hex},
        ).scalars().all()

    assert running_row["status"] == "queued"
    assert int(running_row["attempts"]) == 2
    assert list(recovery_jobs) == ["post_room3_request"]

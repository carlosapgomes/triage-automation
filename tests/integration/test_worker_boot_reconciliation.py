from __future__ import annotations

from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.config import Config

from alembic import command
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

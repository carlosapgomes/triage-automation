from __future__ import annotations

from pathlib import Path
from uuid import UUID, uuid4

import pytest
import sqlalchemy as sa
from alembic.config import Config

from alembic import command
from apps.worker.main import build_worker_runtime
from triage_automation.application.ports.case_repository_port import CaseCreateInput
from triage_automation.application.ports.job_queue_port import JobEnqueueInput, JobRecord
from triage_automation.application.services.job_failure_service import JobFailureService
from triage_automation.application.services.recovery_service import RecoveryService
from triage_automation.application.services.worker_runtime import WorkerRuntime
from triage_automation.config.settings import Settings
from triage_automation.domain.case_status import CaseStatus
from triage_automation.infrastructure.db.audit_repository import SqlAlchemyAuditRepository
from triage_automation.infrastructure.db.case_repository import SqlAlchemyCaseRepository
from triage_automation.infrastructure.db.job_queue_repository import SqlAlchemyJobQueueRepository
from triage_automation.infrastructure.db.session import create_session_factory


def _upgrade_head(tmp_path: Path, filename: str) -> tuple[str, str]:
    db_path = tmp_path / filename
    sync_url = f"sqlite+pysqlite:///{db_path}"
    async_url = f"sqlite+aiosqlite:///{db_path}"

    alembic_config = Config("alembic.ini")
    alembic_config.set_main_option("sqlalchemy.url", sync_url)
    command.upgrade(alembic_config, "head")

    return sync_url, async_url


async def _create_case(
    case_repo: SqlAlchemyCaseRepository,
    *,
    status: CaseStatus,
    origin_event_id: str,
) -> UUID:
    created = await case_repo.create_case(
        CaseCreateInput(
            case_id=uuid4(),
            status=status,
            room1_origin_room_id="!room1:example.org",
            room1_origin_event_id=origin_event_id,
            room1_sender_user_id="@human:example.org",
        )
    )
    return created.case_id


def _runtime_settings(*, database_url: str) -> Settings:
    return Settings.model_construct(
        room1_id="!room1:example.org",
        room2_id="!room2:example.org",
        room3_id="!room3:example.org",
        matrix_homeserver_url="https://matrix.example.org",
        matrix_bot_user_id="@bot:example.org",
        matrix_access_token="matrix-token",
        matrix_sync_timeout_ms=30_000,
        matrix_poll_interval_seconds=0.0,
        worker_poll_interval_seconds=0.0,
        webhook_public_url="https://webhook.example.org",
        database_url=database_url,
        webhook_hmac_secret="secret",
        llm_runtime_mode="deterministic",
        openai_api_key=None,
        log_level="INFO",
    )


@pytest.mark.asyncio
async def test_max_retries_marks_job_dead_marks_case_failed_and_enqueues_failure_final_reply(
    tmp_path: Path,
) -> None:
    sync_url, async_url = _upgrade_head(tmp_path, "max_retries_failure.db")
    session_factory = create_session_factory(async_url)

    case_repo = SqlAlchemyCaseRepository(session_factory)
    audit_repo = SqlAlchemyAuditRepository(session_factory)
    queue_repo = SqlAlchemyJobQueueRepository(session_factory)
    failure_service = JobFailureService(
        case_repository=case_repo,
        audit_repository=audit_repo,
        job_queue=queue_repo,
    )

    case_id = await _create_case(
        case_repo,
        status=CaseStatus.EXTRACTING,
        origin_event_id="$origin-max-retry-1",
    )
    await queue_repo.enqueue(
        JobEnqueueInput(
            case_id=case_id,
            job_type="process_pdf_case",
            payload={"pdf_mxc_url": "mxc://example.org/a.pdf"},
            max_attempts=1,
        )
    )

    async def always_fail(_: JobRecord) -> None:
        raise RuntimeError("llm1 downstream timeout")

    runtime = WorkerRuntime(
        queue=queue_repo,
        handlers={"process_pdf_case": always_fail},
        audit_repository=audit_repo,
        job_failure_service=failure_service,
        poll_interval_seconds=0,
    )

    claimed_count = await runtime.run_once()

    assert claimed_count == 1

    engine = sa.create_engine(sync_url)
    with engine.begin() as connection:
        failed_job = connection.execute(
            sa.text(
                "SELECT status, attempts, last_error FROM jobs "
                "WHERE case_id = :case_id AND job_type = 'process_pdf_case'"
            ),
            {"case_id": case_id.hex},
        ).mappings().one()
        case_row = connection.execute(
            sa.text("SELECT status FROM cases WHERE case_id = :case_id"),
            {"case_id": case_id.hex},
        ).mappings().one()
        failure_job_count = connection.execute(
            sa.text(
                "SELECT COUNT(*) FROM jobs "
                "WHERE case_id = :case_id AND job_type = 'post_room1_final_failure'"
            ),
            {"case_id": case_id.hex},
        ).scalar_one()
        audit_types = connection.execute(
            sa.text(
                "SELECT event_type FROM case_events "
                "WHERE case_id = :case_id ORDER BY id"
            ),
            {"case_id": case_id.hex},
        ).scalars().all()

    assert failed_job["status"] == "dead"
    assert int(failed_job["attempts"]) == 1
    assert "llm1 downstream timeout" in str(failed_job["last_error"])
    assert case_row["status"] == "FAILED"
    assert int(failure_job_count) == 1
    assert "JOB_MAX_RETRIES_EXCEEDED" in list(audit_types)
    assert "CASE_FAILED_MAX_RETRIES" in list(audit_types)
    assert "JOB_ENQUEUED_POST_ROOM1_FAILURE" in list(audit_types)


@pytest.mark.asyncio
async def test_recovery_scan_enqueues_missing_jobs_once_without_duplicates(tmp_path: Path) -> None:
    sync_url, async_url = _upgrade_head(tmp_path, "recovery_scan.db")
    session_factory = create_session_factory(async_url)

    case_repo = SqlAlchemyCaseRepository(session_factory)
    audit_repo = SqlAlchemyAuditRepository(session_factory)
    queue_repo = SqlAlchemyJobQueueRepository(session_factory)

    doctor_accepted_case = await _create_case(
        case_repo,
        status=CaseStatus.DOCTOR_ACCEPTED,
        origin_event_id="$origin-recovery-1",
    )
    failed_case = await _create_case(
        case_repo,
        status=CaseStatus.FAILED,
        origin_event_id="$origin-recovery-2",
    )
    cleanup_running_case = await _create_case(
        case_repo,
        status=CaseStatus.CLEANUP_RUNNING,
        origin_event_id="$origin-recovery-3",
    )

    await queue_repo.enqueue(
        JobEnqueueInput(
            case_id=cleanup_running_case,
            job_type="execute_cleanup",
            payload={},
        )
    )

    service = RecoveryService(
        case_repository=case_repo,
        audit_repository=audit_repo,
        job_queue=queue_repo,
    )
    first_run = await service.recover()
    second_run = await service.recover()

    assert first_run.enqueued_jobs == 2
    assert second_run.enqueued_jobs == 0

    engine = sa.create_engine(sync_url)
    with engine.begin() as connection:
        jobs = connection.execute(
            sa.text(
                "SELECT case_id, job_type FROM jobs "
                "WHERE case_id IN (:doctor_accepted_case, :failed_case, :cleanup_running_case) "
                "ORDER BY job_id"
            ),
            {
                "doctor_accepted_case": doctor_accepted_case.hex,
                "failed_case": failed_case.hex,
                "cleanup_running_case": cleanup_running_case.hex,
            },
        ).mappings().all()

    by_case: dict[str, list[str]] = {}
    for row in jobs:
        case_key = str(row["case_id"])
        by_case.setdefault(case_key, []).append(str(row["job_type"]))

    assert by_case[doctor_accepted_case.hex] == ["post_room3_request"]
    assert by_case[failed_case.hex] == ["post_room1_final_failure"]
    assert by_case[cleanup_running_case.hex] == ["execute_cleanup"]


@pytest.mark.asyncio
async def test_runtime_wiring_dead_letters_at_max_attempts_boundary(tmp_path: Path) -> None:
    sync_url, async_url = _upgrade_head(tmp_path, "runtime_dead_letter_boundary.db")
    session_factory = create_session_factory(async_url)

    case_repo = SqlAlchemyCaseRepository(session_factory)
    queue_repo = SqlAlchemyJobQueueRepository(session_factory)

    case_id = await _create_case(
        case_repo,
        status=CaseStatus.WAIT_DOCTOR,
        origin_event_id="$origin-runtime-dead-letter",
    )
    job = await queue_repo.enqueue(
        JobEnqueueInput(
            case_id=case_id,
            job_type="post_room3_request",
            payload={},
            max_attempts=1,
        )
    )

    runtime = build_worker_runtime(
        settings=_runtime_settings(database_url=async_url),
        session_factory=session_factory,
    )

    claimed_count = await runtime.run_once()

    assert claimed_count == 1

    engine = sa.create_engine(sync_url)
    with engine.begin() as connection:
        job_row = connection.execute(
            sa.text("SELECT status, attempts, last_error FROM jobs WHERE job_id = :job_id"),
            {"job_id": job.job_id},
        ).mappings().one()
        case_row = connection.execute(
            sa.text("SELECT status FROM cases WHERE case_id = :case_id"),
            {"case_id": case_id.hex},
        ).mappings().one()
        failure_job_count = connection.execute(
            sa.text(
                "SELECT COUNT(*) FROM jobs "
                "WHERE case_id = :case_id AND job_type = 'post_room1_final_failure'"
            ),
            {"case_id": case_id.hex},
        ).scalar_one()

    assert job_row["status"] == "dead"
    assert int(job_row["attempts"]) == 1
    assert "not ready for Room-3 request post" in str(job_row["last_error"])
    assert case_row["status"] == "FAILED"
    assert int(failure_job_count) == 1

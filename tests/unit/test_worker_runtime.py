from __future__ import annotations

import logging
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from triage_automation.application.ports.audit_repository_port import AuditEventCreateInput
from triage_automation.application.ports.job_queue_port import JobRecord
from triage_automation.application.services.worker_runtime import WorkerRuntime


class FakeQueue:
    def __init__(self, claimed_jobs: list[JobRecord]) -> None:
        self._claimed_jobs = claimed_jobs
        self._jobs = list(claimed_jobs)
        self.mark_done_calls: list[int] = []
        self.mark_failed_calls: list[tuple[int, str]] = []
        self.schedule_retry_calls: list[tuple[int, str]] = []
        self.mark_dead_calls: list[tuple[int, str]] = []
        self.claim_limits: list[int] = []

    async def claim_due_jobs(self, *, limit: int) -> list[JobRecord]:
        self.claim_limits.append(limit)
        jobs = self._claimed_jobs
        self._claimed_jobs = []
        return jobs

    async def enqueue(self, payload):  # pragma: no cover - not used by runtime unit tests
        raise NotImplementedError

    async def mark_done(self, *, job_id: int) -> None:
        self.mark_done_calls.append(job_id)

    async def mark_failed(self, *, job_id: int, last_error: str) -> None:
        self.mark_failed_calls.append((job_id, last_error))

    async def schedule_retry(
        self,
        *,
        job_id: int,
        run_after: datetime,
        last_error: str,
    ) -> JobRecord:
        self.schedule_retry_calls.append((job_id, last_error))
        for job in self._jobs:
            if job.job_id == job_id:
                return JobRecord(
                    job_id=job.job_id,
                    case_id=job.case_id,
                    job_type=job.job_type,
                    status="queued",
                    run_after=run_after,
                    attempts=job.attempts + 1,
                    max_attempts=job.max_attempts,
                    last_error=last_error,
                    payload=job.payload,
                    created_at=job.created_at,
                    updated_at=job.updated_at,
                )
        raise AssertionError("job not found")

    async def mark_dead(self, *, job_id: int, last_error: str) -> JobRecord:
        self.mark_dead_calls.append((job_id, last_error))
        for job in self._jobs:
            if job.job_id == job_id:
                return JobRecord(
                    job_id=job.job_id,
                    case_id=job.case_id,
                    job_type=job.job_type,
                    status="dead",
                    run_after=job.run_after,
                    attempts=job.attempts + 1,
                    max_attempts=job.max_attempts,
                    last_error=last_error,
                    payload=job.payload,
                    created_at=job.created_at,
                    updated_at=job.updated_at,
                )
        raise AssertionError("job not found")

    async def has_active_job(self, *, case_id, job_type):  # pragma: no cover - not used here
        _ = case_id, job_type
        return False


class FakeAuditRepository:
    def __init__(self) -> None:
        self.events: list[AuditEventCreateInput] = []

    async def append_event(self, payload: AuditEventCreateInput) -> int:
        self.events.append(payload)
        return len(self.events)


class FakeJobFailureService:
    def __init__(self) -> None:
        self.calls: list[JobRecord] = []

    async def handle_max_retries(self, *, job: JobRecord) -> None:
        self.calls.append(job)


class SleepSpy:
    def __init__(self) -> None:
        self.calls: list[float] = []

    async def __call__(self, seconds: float) -> None:
        self.calls.append(seconds)


def _job(job_id: int, job_type: str, *, attempts: int = 0, max_attempts: int = 5) -> JobRecord:
    now = datetime.now(tz=UTC)
    return JobRecord(
        job_id=job_id,
        case_id=uuid4(),
        job_type=job_type,
        status="running",
        run_after=now,
        attempts=attempts,
        max_attempts=max_attempts,
        last_error=None,
        payload={},
        created_at=now,
        updated_at=now,
    )


@pytest.mark.asyncio
async def test_empty_queue_sleeps_without_busy_loop() -> None:
    queue = FakeQueue(claimed_jobs=[])
    sleep_spy = SleepSpy()
    runtime = WorkerRuntime(
        queue=queue,
        handlers={},
        poll_interval_seconds=0.25,
        claim_limit=5,
        sleep=sleep_spy,
    )

    claimed_count = await runtime.run_once()

    assert claimed_count == 0
    assert queue.claim_limits == [5]
    assert sleep_spy.calls == [0.25]


@pytest.mark.asyncio
async def test_unknown_job_type_schedules_retry_deterministically() -> None:
    queue = FakeQueue(claimed_jobs=[_job(11, "unknown-type")])
    runtime = WorkerRuntime(queue=queue, handlers={})

    claimed_count = await runtime.run_once()

    assert claimed_count == 1
    assert queue.mark_done_calls == []
    assert len(queue.schedule_retry_calls) == 1
    assert queue.schedule_retry_calls[0][0] == 11
    assert "Unknown job type" in queue.schedule_retry_calls[0][1]
    assert "unknown-type" in queue.schedule_retry_calls[0][1]
    assert queue.mark_dead_calls == []


@pytest.mark.asyncio
async def test_known_handler_marks_done() -> None:
    queue = FakeQueue(claimed_jobs=[_job(12, "process_pdf_case")])
    handled: list[int] = []

    async def handler(job: JobRecord) -> None:
        handled.append(job.job_id)

    runtime = WorkerRuntime(queue=queue, handlers={"process_pdf_case": handler})

    claimed_count = await runtime.run_once()

    assert claimed_count == 1
    assert handled == [12]
    assert queue.mark_done_calls == [12]
    assert queue.mark_failed_calls == []


@pytest.mark.asyncio
async def test_known_handler_emits_job_lifecycle_logs(caplog: pytest.LogCaptureFixture) -> None:
    queue = FakeQueue(claimed_jobs=[_job(13, "process_pdf_case")])

    async def handler(_: JobRecord) -> None:
        return None

    runtime = WorkerRuntime(queue=queue, handlers={"process_pdf_case": handler})

    with caplog.at_level(logging.INFO):
        claimed_count = await runtime.run_once()

    assert claimed_count == 1
    assert "claimed_due_jobs count=1" in caplog.text
    assert "job_started job_id=13 job_type=process_pdf_case" in caplog.text
    assert "job_done job_id=13 job_type=process_pdf_case" in caplog.text


@pytest.mark.asyncio
async def test_handler_error_dead_letters_and_calls_failure_finalization() -> None:
    queue = FakeQueue(claimed_jobs=[_job(99, "process_pdf_case", attempts=0, max_attempts=1)])
    audit_repo = FakeAuditRepository()
    failure_service = FakeJobFailureService()

    async def handler(_: JobRecord) -> None:
        raise RuntimeError("boom")

    runtime = WorkerRuntime(
        queue=queue,
        handlers={"process_pdf_case": handler},
        audit_repository=audit_repo,
        job_failure_service=failure_service,
    )

    claimed_count = await runtime.run_once()

    assert claimed_count == 1
    assert queue.mark_done_calls == []
    assert len(queue.mark_dead_calls) == 1
    assert queue.mark_dead_calls[0][0] == 99
    assert "Handler error for process_pdf_case: boom" in queue.mark_dead_calls[0][1]
    assert len(audit_repo.events) == 1
    assert audit_repo.events[0].event_type == "JOB_MAX_RETRIES_EXCEEDED"
    assert len(failure_service.calls) == 1
    assert failure_service.calls[0].status == "dead"

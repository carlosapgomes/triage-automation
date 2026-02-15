from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from triage_automation.application.ports.job_queue_port import JobRecord
from triage_automation.application.services.worker_runtime import WorkerRuntime


class FakeQueue:
    def __init__(self, claimed_jobs: list[JobRecord]) -> None:
        self._claimed_jobs = claimed_jobs
        self.mark_done_calls: list[int] = []
        self.mark_failed_calls: list[tuple[int, str]] = []
        self.claim_limits: list[int] = []

    async def claim_due_jobs(self, *, limit: int) -> list[JobRecord]:
        self.claim_limits.append(limit)
        jobs = self._claimed_jobs
        self._claimed_jobs = []
        return jobs

    async def mark_done(self, *, job_id: int) -> None:
        self.mark_done_calls.append(job_id)

    async def mark_failed(self, *, job_id: int, last_error: str) -> None:
        self.mark_failed_calls.append((job_id, last_error))


class SleepSpy:
    def __init__(self) -> None:
        self.calls: list[float] = []

    async def __call__(self, seconds: float) -> None:
        self.calls.append(seconds)


def _job(job_id: int, job_type: str) -> JobRecord:
    now = datetime.now(tz=UTC)
    return JobRecord(
        job_id=job_id,
        case_id=uuid4(),
        job_type=job_type,
        status="running",
        run_after=now,
        attempts=0,
        max_attempts=5,
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
async def test_unknown_job_type_marked_failed_deterministically() -> None:
    queue = FakeQueue(claimed_jobs=[_job(11, "unknown-type")])
    runtime = WorkerRuntime(queue=queue, handlers={})

    claimed_count = await runtime.run_once()

    assert claimed_count == 1
    assert queue.mark_done_calls == []
    assert len(queue.mark_failed_calls) == 1
    assert queue.mark_failed_calls[0][0] == 11
    assert "Unknown job type" in queue.mark_failed_calls[0][1]
    assert "unknown-type" in queue.mark_failed_calls[0][1]


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

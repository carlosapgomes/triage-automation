"""Worker runtime loop for polling and dispatching queued jobs."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

from triage_automation.application.ports.job_queue_port import JobQueuePort, JobRecord

JobHandler = Callable[[JobRecord], Awaitable[None]]
SleepCallable = Callable[[float], Awaitable[None]]


class WorkerRuntime:
    """Polling worker runtime with explicit job dispatch and failure marking."""

    def __init__(
        self,
        *,
        queue: JobQueuePort,
        handlers: dict[str, JobHandler],
        claim_limit: int = 10,
        poll_interval_seconds: float = 1.0,
        sleep: SleepCallable = asyncio.sleep,
    ) -> None:
        self._queue = queue
        self._handlers = handlers
        self._claim_limit = claim_limit
        self._poll_interval_seconds = poll_interval_seconds
        self._sleep = sleep

    async def run_once(self) -> int:
        """Poll queue once and process claimed jobs."""

        claimed_jobs = await self._queue.claim_due_jobs(limit=self._claim_limit)
        if not claimed_jobs:
            await self._sleep(self._poll_interval_seconds)
            return 0

        for job in claimed_jobs:
            await self._process_job(job)

        return len(claimed_jobs)

    async def run_until_stopped(self, stop_event: asyncio.Event) -> None:
        """Continuously run polling loop until stop_event is set."""

        while not stop_event.is_set():
            await self.run_once()

    async def _process_job(self, job: JobRecord) -> None:
        handler = self._handlers.get(job.job_type)
        if handler is None:
            await self._queue.mark_failed(
                job_id=job.job_id,
                last_error=f"Unknown job type: {job.job_type}",
            )
            return

        try:
            await handler(job)
        except Exception as error:  # noqa: BLE001
            await self._queue.mark_failed(
                job_id=job.job_id,
                last_error=f"Handler error for {job.job_type}: {error}",
            )
            return

        await self._queue.mark_done(job_id=job.job_id)

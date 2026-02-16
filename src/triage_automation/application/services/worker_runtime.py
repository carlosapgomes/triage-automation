"""Worker runtime loop for polling and dispatching queued jobs."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from uuid import UUID

from triage_automation.application.ports.audit_repository_port import (
    AuditEventCreateInput,
    AuditRepositoryPort,
)
from triage_automation.application.ports.job_queue_port import JobQueuePort, JobRecord
from triage_automation.application.services.backoff import compute_retry_delay
from triage_automation.application.services.job_failure_service import JobFailureService

JobHandler = Callable[[JobRecord], Awaitable[None]]
SleepCallable = Callable[[float], Awaitable[None]]
NowCallable = Callable[[], datetime]
logger = logging.getLogger(__name__)


def _utc_now() -> datetime:
    return datetime.now(tz=UTC)


class WorkerRuntime:
    """Polling worker runtime with retries, dead-lettering, and failure finalization."""

    def __init__(
        self,
        *,
        queue: JobQueuePort,
        handlers: dict[str, JobHandler],
        audit_repository: AuditRepositoryPort | None = None,
        job_failure_service: JobFailureService | None = None,
        claim_limit: int = 10,
        poll_interval_seconds: float = 1.0,
        sleep: SleepCallable = asyncio.sleep,
        now: NowCallable = _utc_now,
    ) -> None:
        self._queue = queue
        self._handlers = handlers
        self._audit_repository = audit_repository
        self._job_failure_service = job_failure_service
        self._claim_limit = claim_limit
        self._poll_interval_seconds = poll_interval_seconds
        self._sleep = sleep
        self._now = now

    async def run_once(self) -> int:
        """Poll queue once and process claimed jobs."""

        claimed_jobs = await self._queue.claim_due_jobs(limit=self._claim_limit)
        if not claimed_jobs:
            await self._sleep(self._poll_interval_seconds)
            return 0

        logger.info("claimed_due_jobs count=%s", len(claimed_jobs))
        for job in claimed_jobs:
            await self._process_job(job)

        return len(claimed_jobs)

    async def run_until_stopped(self, stop_event: asyncio.Event) -> None:
        """Continuously run polling loop until stop_event is set."""

        while not stop_event.is_set():
            await self.run_once()

    async def _process_job(self, job: JobRecord) -> None:
        logger.info(
            "job_started job_id=%s job_type=%s case_id=%s attempts=%s max_attempts=%s",
            job.job_id,
            job.job_type,
            job.case_id,
            job.attempts,
            job.max_attempts,
        )
        handler = self._handlers.get(job.job_type)
        if handler is None:
            await self._handle_job_error(
                job=job,
                error_summary=f"Unknown job type: {job.job_type}",
            )
            return

        try:
            await handler(job)
        except Exception as error:  # noqa: BLE001
            await self._handle_job_error(
                job=job,
                error_summary=f"Handler error for {job.job_type}: {error}",
            )
            return

        await self._queue.mark_done(job_id=job.job_id)
        logger.info(
            "job_done job_id=%s job_type=%s case_id=%s",
            job.job_id,
            job.job_type,
            job.case_id,
        )

    async def _handle_job_error(self, *, job: JobRecord, error_summary: str) -> None:
        retry_attempt = job.attempts + 1

        if retry_attempt < job.max_attempts:
            run_after = self._now() + compute_retry_delay(retry_attempt)
            retried_job = await self._queue.schedule_retry(
                job_id=job.job_id,
                run_after=run_after,
                last_error=error_summary,
            )
            await self._audit_retry_scheduled(
                case_id=job.case_id,
                job_type=job.job_type,
                attempts=retried_job.attempts,
                run_after=retried_job.run_after,
                error_summary=error_summary,
            )
            logger.warning(
                (
                    "job_retry_scheduled job_id=%s job_type=%s case_id=%s "
                    "attempts=%s max_attempts=%s run_after=%s error=%s"
                ),
                job.job_id,
                job.job_type,
                job.case_id,
                retried_job.attempts,
                job.max_attempts,
                retried_job.run_after.isoformat(),
                error_summary,
            )
            return

        dead_job = await self._queue.mark_dead(
            job_id=job.job_id,
            last_error=error_summary,
        )
        await self._audit_max_retries_exceeded(
            case_id=job.case_id,
            job_type=job.job_type,
            attempts=dead_job.attempts,
            error_summary=error_summary,
        )
        logger.error(
            (
                "job_dead job_id=%s job_type=%s case_id=%s attempts=%s "
                "max_attempts=%s error=%s"
            ),
            job.job_id,
            job.job_type,
            job.case_id,
            dead_job.attempts,
            job.max_attempts,
            error_summary,
        )

        if self._job_failure_service is not None:
            await self._job_failure_service.handle_max_retries(job=dead_job)

    async def _audit_retry_scheduled(
        self,
        *,
        case_id: UUID | None,
        job_type: str,
        attempts: int,
        run_after: datetime,
        error_summary: str,
    ) -> None:
        if case_id is None or self._audit_repository is None:
            return

        await self._audit_repository.append_event(
            AuditEventCreateInput(
                case_id=case_id,
                actor_type="system",
                event_type="JOB_RETRY_SCHEDULED",
                payload={
                    "job_type": job_type,
                    "attempts": attempts,
                    "run_after": run_after.isoformat(),
                    "error_summary": error_summary,
                },
            )
        )

    async def _audit_max_retries_exceeded(
        self,
        *,
        case_id: UUID | None,
        job_type: str,
        attempts: int,
        error_summary: str,
    ) -> None:
        if case_id is None or self._audit_repository is None:
            return

        await self._audit_repository.append_event(
            AuditEventCreateInput(
                case_id=case_id,
                actor_type="system",
                event_type="JOB_MAX_RETRIES_EXCEEDED",
                payload={
                    "job_type": job_type,
                    "attempts": attempts,
                    "last_error": error_summary,
                },
            )
        )

"""SQLAlchemy adapter for jobs queue operations."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, cast
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.engine import RowMapping
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from triage_automation.application.ports.job_queue_port import (
    JobEnqueueInput,
    JobQueuePort,
    JobRecord,
)
from triage_automation.infrastructure.db.metadata import jobs


class SqlAlchemyJobQueueRepository(JobQueuePort):
    """Postgres-backed queue repository with SQLite-safe fallback for tests."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def enqueue(self, payload: JobEnqueueInput) -> JobRecord:
        """Insert queued job row and return persisted job record."""

        values: dict[str, Any] = {
            "case_id": payload.case_id,
            "job_type": payload.job_type,
            "payload": payload.payload,
            "max_attempts": payload.max_attempts,
        }
        if payload.run_after is not None:
            values["run_after"] = payload.run_after

        statement = sa.insert(jobs).values(**values).returning(*jobs.c)

        async with self._session_factory() as session:
            result = await session.execute(statement)
            await session.commit()

        return _to_job_record(result.mappings().one())

    async def claim_due_jobs(self, *, limit: int) -> list[JobRecord]:
        """Claim due queued jobs, marking them running, and return claimed rows."""

        if limit < 1:
            return []

        async with self._session_factory() as session:
            dialect_name = session.get_bind().dialect.name

            if dialect_name == "postgresql":
                statement = sa.text(
                    """
                    WITH claim AS (
                        SELECT job_id
                        FROM jobs
                        WHERE status = 'queued' AND run_after <= now()
                        ORDER BY job_id
                        FOR UPDATE SKIP LOCKED
                        LIMIT :limit
                    )
                    UPDATE jobs
                    SET status = 'running',
                        updated_at = now()
                    WHERE job_id IN (SELECT job_id FROM claim)
                    RETURNING *
                    """
                )
            else:
                statement = sa.text(
                    """
                    UPDATE jobs
                    SET status = 'running',
                        updated_at = CURRENT_TIMESTAMP
                    WHERE job_id IN (
                        SELECT job_id
                        FROM jobs
                        WHERE status = 'queued' AND run_after <= CURRENT_TIMESTAMP
                        ORDER BY job_id
                        LIMIT :limit
                    )
                    RETURNING *
                    """
                )

            result = await session.execute(statement, {"limit": limit})
            await session.commit()

        return [_to_job_record(row) for row in result.mappings().all()]

    async def mark_done(self, *, job_id: int) -> None:
        """Mark a job as done."""

        statement = (
            sa.update(jobs)
            .where(jobs.c.job_id == job_id)
            .values(status="done", updated_at=sa.func.current_timestamp())
        )

        async with self._session_factory() as session:
            await session.execute(statement)
            await session.commit()

    async def mark_failed(self, *, job_id: int, last_error: str) -> None:
        """Mark a job as failed without retry scheduling."""

        statement = (
            sa.update(jobs)
            .where(jobs.c.job_id == job_id)
            .values(
                status="failed",
                last_error=last_error,
                updated_at=sa.func.current_timestamp(),
            )
        )

        async with self._session_factory() as session:
            await session.execute(statement)
            await session.commit()

    async def schedule_retry(
        self,
        *,
        job_id: int,
        run_after: datetime,
        last_error: str,
    ) -> JobRecord:
        """Requeue job with incremented attempts and next run_after timestamp."""

        statement = (
            sa.update(jobs)
            .where(jobs.c.job_id == job_id)
            .values(
                status="queued",
                run_after=run_after,
                attempts=jobs.c.attempts + 1,
                last_error=last_error,
                updated_at=sa.func.current_timestamp(),
            )
            .returning(*jobs.c)
        )

        async with self._session_factory() as session:
            result = await session.execute(statement)
            await session.commit()

        return _to_job_record(result.mappings().one())

    async def mark_dead(self, *, job_id: int, last_error: str) -> JobRecord:
        """Dead-letter a job with incremented attempts and error context."""

        statement = (
            sa.update(jobs)
            .where(jobs.c.job_id == job_id)
            .values(
                status="dead",
                attempts=jobs.c.attempts + 1,
                last_error=last_error,
                updated_at=sa.func.current_timestamp(),
            )
            .returning(*jobs.c)
        )

        async with self._session_factory() as session:
            result = await session.execute(statement)
            await session.commit()

        return _to_job_record(result.mappings().one())

    async def has_active_job(self, *, case_id: UUID, job_type: str) -> bool:
        """Return whether case has queued/running job of the given type."""

        statement = sa.select(sa.literal(True)).where(
            jobs.c.case_id == case_id,
            jobs.c.job_type == job_type,
            jobs.c.status.in_(("queued", "running")),
        ).limit(1)

        async with self._session_factory() as session:
            result = await session.execute(statement)

        return result.scalar_one_or_none() is True


def _to_job_record(row: RowMapping) -> JobRecord:
    raw_payload = row["payload"]
    if isinstance(raw_payload, str):
        payload_value = cast(dict[str, Any], json.loads(raw_payload))
    else:
        payload_value = cast(dict[str, Any], raw_payload)
    raw_case_id = row["case_id"]
    case_id = None
    if raw_case_id is not None:
        case_id = raw_case_id if isinstance(raw_case_id, UUID) else UUID(str(raw_case_id))

    return JobRecord(
        job_id=cast(int, row["job_id"]),
        case_id=case_id,
        job_type=cast(str, row["job_type"]),
        status=cast(str, row["status"]),
        run_after=cast(datetime, row["run_after"]),
        attempts=cast(int, row["attempts"]),
        max_attempts=cast(int, row["max_attempts"]),
        last_error=cast(str | None, row["last_error"]),
        payload=payload_value,
        created_at=cast(datetime, row["created_at"]),
        updated_at=cast(datetime, row["updated_at"]),
    )

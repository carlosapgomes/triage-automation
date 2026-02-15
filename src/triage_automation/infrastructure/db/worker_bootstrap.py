"""Startup reconciliation queries for worker runtime."""

from __future__ import annotations

from typing import Any, cast

import sqlalchemy as sa
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from triage_automation.infrastructure.db.metadata import jobs


async def reconcile_running_jobs(session_factory: async_sessionmaker[AsyncSession]) -> int:
    """Reset stale running jobs back to queued while keeping attempts unchanged."""

    statement = (
        sa.update(jobs)
        .where(jobs.c.status == "running")
        .values(status="queued", updated_at=sa.func.current_timestamp())
    )

    async with session_factory() as session:
        result = cast(CursorResult[Any], await session.execute(statement))
        await session.commit()

    return int(result.rowcount or 0)

"""SQLAlchemy adapter for append-only case audit events."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from triage_automation.application.ports.audit_repository_port import (
    AuditEventCreateInput,
    AuditRepositoryPort,
)
from triage_automation.infrastructure.db.metadata import case_events


class SqlAlchemyAuditRepository(AuditRepositoryPort):
    """Audit repository backed by SQLAlchemy async sessions."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def append_event(self, payload: AuditEventCreateInput) -> int:
        """Insert an audit event row and return its numeric id."""

        statement = sa.insert(case_events).values(
            case_id=payload.case_id,
            actor_type=payload.actor_type,
            actor_user_id=payload.actor_user_id,
            room_id=payload.room_id,
            matrix_event_id=payload.matrix_event_id,
            event_type=payload.event_type,
            payload=payload.payload,
        ).returning(case_events.c.id)

        async with self._session_factory() as session:
            result = await session.execute(statement)
            await session.commit()

        inserted_id = result.scalar_one()
        return int(inserted_id)

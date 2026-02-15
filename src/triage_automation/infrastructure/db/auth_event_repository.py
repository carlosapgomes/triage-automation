"""SQLAlchemy adapter for auth event append operations."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from triage_automation.application.ports.auth_event_repository_port import (
    AuthEventCreateInput,
    AuthEventRepositoryPort,
)
from triage_automation.infrastructure.db.metadata import auth_events


class SqlAlchemyAuthEventRepository(AuthEventRepositoryPort):
    """Auth event repository backed by SQLAlchemy async sessions."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def append_event(self, payload: AuthEventCreateInput) -> int:
        """Insert an auth audit event row and return its numeric id."""

        statement = sa.insert(auth_events).values(
            user_id=payload.user_id,
            event_type=payload.event_type,
            ip_address=payload.ip_address,
            user_agent=payload.user_agent,
            payload=payload.payload,
        ).returning(auth_events.c.id)

        async with self._session_factory() as session:
            result = await session.execute(statement)
            await session.commit()

        inserted_id = result.scalar_one()
        return int(inserted_id)

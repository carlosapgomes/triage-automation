"""SQLAlchemy adapter for user lookup queries."""

from __future__ import annotations

from datetime import datetime
from typing import cast
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from triage_automation.application.ports.user_repository_port import UserRecord, UserRepositoryPort
from triage_automation.domain.auth.roles import Role
from triage_automation.infrastructure.db.metadata import users


class SqlAlchemyUserRepository(UserRepositoryPort):
    """User repository backed by SQLAlchemy async sessions."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def get_by_id(self, *, user_id: UUID) -> UserRecord | None:
        """Return user by id, including inactive users."""

        statement = sa.select(
            users.c.id,
            users.c.email,
            users.c.password_hash,
            users.c.role,
            users.c.is_active,
            users.c.created_at,
            users.c.updated_at,
        ).where(users.c.id == user_id).limit(1)

        async with self._session_factory() as session:
            result = await session.execute(statement)

        row = result.mappings().first()
        if row is None:
            return None
        return _to_user_record(row)

    async def get_by_email(self, *, email: str) -> UserRecord | None:
        """Return user by normalized email, including inactive users."""

        statement = sa.select(
            users.c.id,
            users.c.email,
            users.c.password_hash,
            users.c.role,
            users.c.is_active,
            users.c.created_at,
            users.c.updated_at,
        ).where(users.c.email == email).limit(1)

        async with self._session_factory() as session:
            result = await session.execute(statement)

        row = result.mappings().first()
        if row is None:
            return None
        return _to_user_record(row)

    async def get_active_by_email(self, *, email: str) -> UserRecord | None:
        """Return active user by normalized email or None."""

        user = await self.get_by_email(email=email)
        if user is None or not user.is_active:
            return None
        return user


def _to_user_record(row: sa.RowMapping) -> UserRecord:
    raw_user_id = row["id"]
    user_id = raw_user_id if isinstance(raw_user_id, UUID) else UUID(str(raw_user_id))
    return UserRecord(
        user_id=user_id,
        email=cast(str, row["email"]),
        password_hash=cast(str, row["password_hash"]),
        role=Role(cast(str, row["role"])),
        is_active=bool(row["is_active"]),
        created_at=cast(datetime, row["created_at"]),
        updated_at=cast(datetime, row["updated_at"]),
    )

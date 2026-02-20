"""SQLAlchemy adapter for opaque auth token persistence."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, cast
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from triage_automation.application.ports.auth_token_repository_port import (
    AuthTokenCreateInput,
    AuthTokenRecord,
    AuthTokenRepositoryPort,
)
from triage_automation.infrastructure.db.metadata import auth_tokens


class SqlAlchemyAuthTokenRepository(AuthTokenRepositoryPort):
    """Auth token repository backed by SQLAlchemy async sessions."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def create_token(self, payload: AuthTokenCreateInput) -> AuthTokenRecord:
        """Persist a token hash row and return the inserted token record."""

        statement = sa.insert(auth_tokens).values(
            user_id=payload.user_id,
            token_hash=payload.token_hash,
            expires_at=payload.expires_at,
        ).returning(*auth_tokens.c)

        async with self._session_factory() as session:
            result = await session.execute(statement)
            await session.commit()

        row = result.mappings().one()
        return _to_auth_token_record(row)

    async def get_active_by_hash(self, *, token_hash: str) -> AuthTokenRecord | None:
        """Return active token by hash when not revoked and not expired."""

        now = datetime.now(tz=UTC)
        statement = sa.select(*auth_tokens.c).where(
            auth_tokens.c.token_hash == token_hash,
            auth_tokens.c.revoked_at.is_(None),
            auth_tokens.c.expires_at > now,
        ).limit(1)

        async with self._session_factory() as session:
            result = await session.execute(statement)

        row = result.mappings().first()
        if row is None:
            return None
        return _to_auth_token_record(row)

    async def revoke_active_tokens_for_user(self, *, user_id: UUID) -> int:
        """Revoke all currently non-revoked tokens for one user."""

        statement = (
            sa.update(auth_tokens)
            .where(
                auth_tokens.c.user_id == user_id,
                auth_tokens.c.revoked_at.is_(None),
            )
            .values(revoked_at=sa.text("CURRENT_TIMESTAMP"))
        )

        async with self._session_factory() as session:
            result = cast(CursorResult[Any], await session.execute(statement))
            await session.commit()

        return int(result.rowcount or 0)


def _to_auth_token_record(row: sa.RowMapping) -> AuthTokenRecord:
    raw_user_id = row["user_id"]
    user_id = raw_user_id if isinstance(raw_user_id, UUID) else UUID(str(raw_user_id))
    return AuthTokenRecord(
        id=int(row["id"]),
        user_id=user_id,
        token_hash=cast(str, row["token_hash"]),
        issued_at=cast(datetime, row["issued_at"]),
        expires_at=cast(datetime, row["expires_at"]),
        revoked_at=cast(datetime | None, row["revoked_at"]),
        last_used_at=cast(datetime | None, row["last_used_at"]),
    )

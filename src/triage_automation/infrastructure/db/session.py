"""Async SQLAlchemy session factory helpers."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


def create_session_factory(database_url: str) -> async_sessionmaker[AsyncSession]:
    """Create a reusable async session factory for the provided database URL."""

    engine = create_async_engine(database_url)
    return async_sessionmaker(engine, expire_on_commit=False)

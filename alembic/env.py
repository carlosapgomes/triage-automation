"""Alembic environment configuration."""

from __future__ import annotations

import asyncio
import os
from logging.config import fileConfig
from pathlib import Path

import sqlalchemy as sa
from dotenv import load_dotenv
from sqlalchemy import engine_from_config, pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context
from triage_automation.infrastructure.db.metadata import metadata

config = context.config

_DEFAULT_ALEMBIC_URL = "sqlite:///./triage.db"

# Ensure Alembic picks DATABASE_URL from local .env during development,
# but do not override explicit URLs set by callers (tests/programmatic config).
load_dotenv(Path(__file__).resolve().parents[1] / ".env")
database_url = os.getenv("DATABASE_URL")
configured_url = config.get_main_option("sqlalchemy.url")
if database_url and configured_url == _DEFAULT_ALEMBIC_URL:
    config.set_main_option("sqlalchemy.url", database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = metadata


def run_migrations_offline() -> None:
    """Run migrations in offline mode."""

    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in online mode."""

    configured_url = config.get_main_option("sqlalchemy.url") or _DEFAULT_ALEMBIC_URL
    if _is_async_driver_url(configured_url):
        asyncio.run(run_async_migrations())
        return
    run_sync_migrations()


def run_sync_migrations() -> None:
    """Run migrations with SQLAlchemy sync engine for sync DB drivers."""

    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        do_run_migrations(connection)


def do_run_migrations(connection: Connection) -> None:
    """Configure and run migrations for an active DB connection."""

    _ensure_postgres_version_table_capacity(connection)
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Create async connection and run migrations synchronously via run_sync."""

    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def _is_async_driver_url(url: str) -> bool:
    """Return whether a SQLAlchemy URL uses an async driver."""

    return "+asyncpg" in url or "+aiosqlite" in url


def _ensure_postgres_version_table_capacity(connection: Connection) -> None:
    """Ensure Postgres alembic_version table accepts long revision identifiers."""

    if connection.dialect.name != "postgresql":
        return

    inspector = sa.inspect(connection)
    if "alembic_version" not in inspector.get_table_names():
        connection.execute(
            sa.text(
                "CREATE TABLE alembic_version ("
                "version_num VARCHAR(191) NOT NULL, "
                "CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)"
                ")"
            )
        )
        return

    columns = {column["name"]: column for column in inspector.get_columns("alembic_version")}
    version_column = columns.get("version_num")
    if version_column is None:
        return

    length = getattr(version_column["type"], "length", None)
    if isinstance(length, int) and length < 191:
        connection.execute(
            sa.text(
                "ALTER TABLE alembic_version "
                "ALTER COLUMN version_num TYPE VARCHAR(191)"
            )
        )


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

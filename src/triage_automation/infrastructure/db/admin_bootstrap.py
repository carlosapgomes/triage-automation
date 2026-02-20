"""Bootstrap helper for creating an initial admin account at startup."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from uuid import uuid4

import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from triage_automation.application.ports.password_hasher_port import PasswordHasherPort
from triage_automation.domain.auth.credentials import normalize_user_email, normalize_user_password
from triage_automation.domain.auth.roles import Role
from triage_automation.infrastructure.db.metadata import users


class AdminBootstrapConfigError(ValueError):
    """Raised when bootstrap-admin environment configuration is invalid."""


@dataclass(frozen=True)
class AdminBootstrapConfig:
    """Runtime configuration for one-time admin bootstrap."""

    email: str
    password: str


class AdminBootstrapOutcome(StrEnum):
    """Outcome states for initial admin bootstrap execution."""

    CREATED = "created"
    SKIPPED_USERS_PRESENT = "skipped_users_present"
    SKIPPED_CONCURRENT_INSERT = "skipped_concurrent_insert"


@dataclass(frozen=True)
class AdminBootstrapResult:
    """Result model for one initial-admin bootstrap attempt."""

    outcome: AdminBootstrapOutcome
    email: str


def resolve_admin_bootstrap_config(
    *,
    email: str | None,
    password: str | None,
    password_file: str | None,
) -> AdminBootstrapConfig | None:
    """Resolve bootstrap-admin config from env values or return None when disabled."""

    any_value_set = any(value is not None for value in (email, password, password_file))
    if email is None:
        if any_value_set:
            raise AdminBootstrapConfigError(
                "BOOTSTRAP_ADMIN_EMAIL is required when bootstrap-admin variables are set"
            )
        return None

    if password is not None and password_file is not None:
        raise AdminBootstrapConfigError(
            "set only one of BOOTSTRAP_ADMIN_PASSWORD or BOOTSTRAP_ADMIN_PASSWORD_FILE"
        )

    resolved_password: str | None = None
    if password_file is not None:
        path = Path(password_file)
        try:
            resolved_password = path.read_text(encoding="utf-8").strip()
        except OSError as exc:
            raise AdminBootstrapConfigError(
                "failed to read BOOTSTRAP_ADMIN_PASSWORD_FILE"
            ) from exc
    elif password is not None:
        resolved_password = password

    if resolved_password is None:
        raise AdminBootstrapConfigError(
            "set BOOTSTRAP_ADMIN_PASSWORD or BOOTSTRAP_ADMIN_PASSWORD_FILE "
            "when BOOTSTRAP_ADMIN_EMAIL is set"
        )

    try:
        normalized_email = normalize_user_email(email=email)
    except ValueError as exc:
        raise AdminBootstrapConfigError("BOOTSTRAP_ADMIN_EMAIL cannot be blank") from exc
    try:
        normalized_password = normalize_user_password(password=resolved_password)
    except ValueError as exc:
        raise AdminBootstrapConfigError("bootstrap admin password cannot be blank") from exc

    return AdminBootstrapConfig(email=normalized_email, password=normalized_password)


async def ensure_initial_admin_user(
    *,
    session_factory: async_sessionmaker[AsyncSession],
    password_hasher: PasswordHasherPort,
    config: AdminBootstrapConfig,
) -> AdminBootstrapResult:
    """Create initial `admin` user when user table is empty, otherwise skip."""

    async with session_factory() as session:
        user_count = await _read_user_count(session)
        if user_count > 0:
            return AdminBootstrapResult(
                outcome=AdminBootstrapOutcome.SKIPPED_USERS_PRESENT,
                email=config.email,
            )

        try:
            await session.execute(
                sa.insert(users).values(
                    id=uuid4(),
                    email=config.email,
                    password_hash=password_hasher.hash_password(config.password),
                    role=Role.ADMIN.value,
                    is_active=True,
                )
            )
            await session.commit()
        except IntegrityError:
            await session.rollback()
            return AdminBootstrapResult(
                outcome=AdminBootstrapOutcome.SKIPPED_CONCURRENT_INSERT,
                email=config.email,
            )

    return AdminBootstrapResult(outcome=AdminBootstrapOutcome.CREATED, email=config.email)


async def _read_user_count(session: AsyncSession) -> int:
    """Return the total number of persisted users."""

    result = await session.execute(sa.select(sa.func.count()).select_from(users))
    return int(result.scalar_one())

"""Port for user lookup operations used by authentication services."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from triage_automation.domain.auth.roles import Role


@dataclass(frozen=True)
class UserRecord:
    """User persistence model."""

    user_id: UUID
    email: str
    password_hash: str
    role: Role
    is_active: bool
    created_at: datetime
    updated_at: datetime


class UserRepositoryPort(Protocol):
    """User repository contract."""

    async def get_by_id(self, *, user_id: UUID) -> UserRecord | None:
        """Return user by id, including inactive users."""

    async def get_by_email(self, *, email: str) -> UserRecord | None:
        """Return user by normalized email, including inactive users."""

    async def get_active_by_email(self, *, email: str) -> UserRecord | None:
        """Return active user by normalized email or None."""

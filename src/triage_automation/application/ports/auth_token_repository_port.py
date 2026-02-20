"""Port for opaque auth token persistence operations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True)
class AuthTokenCreateInput:
    """Input payload for inserting an opaque auth token record."""

    user_id: UUID
    token_hash: str
    expires_at: datetime


@dataclass(frozen=True)
class AuthTokenRecord:
    """Persisted opaque auth token model."""

    id: int
    user_id: UUID
    token_hash: str
    issued_at: datetime
    expires_at: datetime
    revoked_at: datetime | None
    last_used_at: datetime | None


class AuthTokenRepositoryPort(Protocol):
    """Opaque auth token persistence contract."""

    async def create_token(self, payload: AuthTokenCreateInput) -> AuthTokenRecord:
        """Persist a new opaque token record."""

    async def get_active_by_hash(self, *, token_hash: str) -> AuthTokenRecord | None:
        """Return active token record by hash (not revoked and not expired)."""

    async def revoke_active_tokens_for_user(self, *, user_id: UUID) -> int:
        """Revoke all currently non-revoked tokens for one user and return affected count."""

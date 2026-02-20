"""Application service for admin user-management operations."""

from __future__ import annotations

from uuid import UUID

from triage_automation.application.ports.auth_token_repository_port import AuthTokenRepositoryPort
from triage_automation.application.ports.user_repository_port import (
    UserCreateInput,
    UserRecord,
    UserRepositoryPort,
)
from triage_automation.domain.auth.account_status import AccountStatus


class UserNotFoundError(LookupError):
    """Raised when a target user cannot be found for one management action."""

    def __init__(self, *, user_id: UUID) -> None:
        super().__init__(f"user not found: {user_id}")
        self.user_id = user_id


class UserManagementService:
    """Expose user listing and lifecycle management use-cases."""

    def __init__(
        self,
        *,
        users: UserRepositoryPort,
        auth_tokens: AuthTokenRepositoryPort,
    ) -> None:
        self._users = users
        self._auth_tokens = auth_tokens

    async def list_users(self) -> list[UserRecord]:
        """Return deterministic user listing for admin surfaces."""

        return await self._users.list_users()

    async def create_user(self, *, payload: UserCreateInput) -> UserRecord:
        """Create one user account and return persisted row."""

        return await self._users.create_user(payload)

    async def block_user(self, *, user_id: UUID) -> UserRecord:
        """Transition one user to blocked state and revoke active sessions."""

        blocked = await self._users.set_account_status(
            user_id=user_id,
            account_status=AccountStatus.BLOCKED,
        )
        if blocked is None:
            raise UserNotFoundError(user_id=user_id)
        await self._auth_tokens.revoke_active_tokens_for_user(user_id=user_id)
        return blocked

    async def reactivate_user(self, *, user_id: UUID) -> UserRecord:
        """Transition one user to active state."""

        active = await self._users.set_account_status(
            user_id=user_id,
            account_status=AccountStatus.ACTIVE,
        )
        if active is None:
            raise UserNotFoundError(user_id=user_id)
        return active

    async def remove_user(self, *, user_id: UUID) -> UserRecord:
        """Transition one user to removed state and revoke active sessions."""

        removed = await self._users.set_account_status(
            user_id=user_id,
            account_status=AccountStatus.REMOVED,
        )
        if removed is None:
            raise UserNotFoundError(user_id=user_id)
        await self._auth_tokens.revoke_active_tokens_for_user(user_id=user_id)
        return removed

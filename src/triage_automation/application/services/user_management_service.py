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
from triage_automation.domain.auth.roles import Role


class UserNotFoundError(LookupError):
    """Raised when a target user cannot be found for one management action."""

    def __init__(self, *, user_id: UUID) -> None:
        super().__init__(f"user not found: {user_id}")
        self.user_id = user_id


class SelfUserManagementError(PermissionError):
    """Raised when admin attempts to block/remove their own account."""

    def __init__(self) -> None:
        super().__init__("self-block/self-remove is not allowed")


class LastActiveAdminError(PermissionError):
    """Raised when operation would leave the system with zero active admins."""

    def __init__(self) -> None:
        super().__init__("at least one active admin must remain")


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

    async def block_user(self, *, actor_user_id: UUID, user_id: UUID) -> UserRecord:
        """Transition one user to blocked state and revoke active sessions."""

        target = await self._require_existing_user(user_id=user_id)
        self._require_not_self_action(actor_user_id=actor_user_id, user_id=user_id)
        await self._require_not_disabling_last_active_admin(target=target)

        blocked = await self._users.set_account_status(
            user_id=user_id,
            account_status=AccountStatus.BLOCKED,
        )
        if blocked is None:  # pragma: no cover - defensive; target already loaded.
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

    async def remove_user(self, *, actor_user_id: UUID, user_id: UUID) -> UserRecord:
        """Transition one user to removed state and revoke active sessions."""

        target = await self._require_existing_user(user_id=user_id)
        self._require_not_self_action(actor_user_id=actor_user_id, user_id=user_id)
        await self._require_not_disabling_last_active_admin(target=target)

        removed = await self._users.set_account_status(
            user_id=user_id,
            account_status=AccountStatus.REMOVED,
        )
        if removed is None:  # pragma: no cover - defensive; target already loaded.
            raise UserNotFoundError(user_id=user_id)
        await self._auth_tokens.revoke_active_tokens_for_user(user_id=user_id)
        return removed

    async def _require_existing_user(self, *, user_id: UUID) -> UserRecord:
        """Return target user or raise deterministic not-found error."""

        target = await self._users.get_by_id(user_id=user_id)
        if target is None:
            raise UserNotFoundError(user_id=user_id)
        return target

    def _require_not_self_action(self, *, actor_user_id: UUID, user_id: UUID) -> None:
        """Reject self block/remove administrative actions."""

        if actor_user_id == user_id:
            raise SelfUserManagementError()

    async def _require_not_disabling_last_active_admin(self, *, target: UserRecord) -> None:
        """Reject actions that would remove the final active admin account."""

        if target.role is not Role.ADMIN or not target.is_active:
            return

        active_admin_count = sum(
            1
            for user in await self._users.list_users()
            if user.role is Role.ADMIN and user.is_active
        )
        if active_admin_count <= 1:
            raise LastActiveAdminError()

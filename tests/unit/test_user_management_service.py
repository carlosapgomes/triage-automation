from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from triage_automation.application.ports.auth_token_repository_port import (
    AuthTokenCreateInput,
    AuthTokenRecord,
)
from triage_automation.application.ports.user_repository_port import UserCreateInput, UserRecord
from triage_automation.application.services.user_management_service import (
    UserManagementService,
    UserNotFoundError,
)
from triage_automation.domain.auth.account_status import AccountStatus
from triage_automation.domain.auth.roles import Role


def _make_user(
    *,
    user_id: UUID | None = None,
    email: str = "reader@example.org",
    role: Role = Role.READER,
    account_status: AccountStatus = AccountStatus.ACTIVE,
) -> UserRecord:
    now = datetime.now(tz=UTC)
    return UserRecord(
        user_id=user_id or uuid4(),
        email=email,
        password_hash="hashed",
        role=role,
        is_active=account_status is AccountStatus.ACTIVE,
        account_status=account_status,
        created_at=now,
        updated_at=now,
    )


@dataclass
class FakeUserRepository:
    users: dict[UUID, UserRecord]

    async def get_by_id(self, *, user_id: UUID) -> UserRecord | None:
        return self.users.get(user_id)

    async def get_by_email(self, *, email: str) -> UserRecord | None:
        for user in self.users.values():
            if user.email == email:
                return user
        return None

    async def get_active_by_email(self, *, email: str) -> UserRecord | None:
        user = await self.get_by_email(email=email)
        if user is None or not user.is_active:
            return None
        return user

    async def list_users(self) -> list[UserRecord]:
        return sorted(self.users.values(), key=lambda item: item.email)

    async def create_user(self, payload: UserCreateInput) -> UserRecord:
        user = _make_user(
            user_id=payload.user_id,
            email=payload.email,
            role=payload.role,
            account_status=payload.account_status,
        )
        self.users[user.user_id] = user
        return user

    async def set_account_status(
        self,
        *,
        user_id: UUID,
        account_status: AccountStatus,
    ) -> UserRecord | None:
        existing = self.users.get(user_id)
        if existing is None:
            return None
        updated = _make_user(
            user_id=existing.user_id,
            email=existing.email,
            role=existing.role,
            account_status=account_status,
        )
        self.users[user_id] = updated
        return updated


class FakeAuthTokenRepository:
    def __init__(self) -> None:
        self.revoked_users: list[UUID] = []

    async def create_token(self, payload: AuthTokenCreateInput) -> AuthTokenRecord:
        _ = payload
        now = datetime.now(tz=UTC)
        return AuthTokenRecord(
            id=1,
            user_id=uuid4(),
            token_hash="fake",
            issued_at=now,
            expires_at=now,
            revoked_at=None,
            last_used_at=None,
        )

    async def get_active_by_hash(self, *, token_hash: str) -> AuthTokenRecord | None:
        _ = token_hash
        return None

    async def revoke_active_tokens_for_user(self, *, user_id: UUID) -> int:
        self.revoked_users.append(user_id)
        return 1


@pytest.mark.asyncio
async def test_list_users_returns_repository_listing() -> None:
    first = _make_user(email="a@example.org")
    second = _make_user(email="b@example.org")
    users = FakeUserRepository(users={first.user_id: first, second.user_id: second})
    service = UserManagementService(users=users, auth_tokens=FakeAuthTokenRepository())

    listed = await service.list_users()

    assert [item.email for item in listed] == ["a@example.org", "b@example.org"]


@pytest.mark.asyncio
async def test_create_user_delegates_to_repository() -> None:
    users = FakeUserRepository(users={})
    service = UserManagementService(users=users, auth_tokens=FakeAuthTokenRepository())
    payload = UserCreateInput(
        user_id=uuid4(),
        email="new-admin@example.org",
        password_hash="hashed::secret",
        role=Role.ADMIN,
        account_status=AccountStatus.ACTIVE,
    )

    created = await service.create_user(payload=payload)

    assert created.user_id == payload.user_id
    assert created.email == "new-admin@example.org"
    assert created.role is Role.ADMIN
    assert created.account_status is AccountStatus.ACTIVE


@pytest.mark.asyncio
async def test_block_user_updates_status_and_revokes_tokens() -> None:
    target = _make_user(account_status=AccountStatus.ACTIVE)
    users = FakeUserRepository(users={target.user_id: target})
    auth_tokens = FakeAuthTokenRepository()
    service = UserManagementService(users=users, auth_tokens=auth_tokens)

    blocked = await service.block_user(user_id=target.user_id)

    assert blocked.account_status is AccountStatus.BLOCKED
    assert blocked.is_active is False
    assert auth_tokens.revoked_users == [target.user_id]


@pytest.mark.asyncio
async def test_reactivate_user_updates_status_without_revocation() -> None:
    target = _make_user(account_status=AccountStatus.BLOCKED)
    users = FakeUserRepository(users={target.user_id: target})
    auth_tokens = FakeAuthTokenRepository()
    service = UserManagementService(users=users, auth_tokens=auth_tokens)

    active = await service.reactivate_user(user_id=target.user_id)

    assert active.account_status is AccountStatus.ACTIVE
    assert active.is_active is True
    assert auth_tokens.revoked_users == []


@pytest.mark.asyncio
async def test_remove_user_updates_status_and_revokes_tokens() -> None:
    target = _make_user(account_status=AccountStatus.ACTIVE)
    users = FakeUserRepository(users={target.user_id: target})
    auth_tokens = FakeAuthTokenRepository()
    service = UserManagementService(users=users, auth_tokens=auth_tokens)

    removed = await service.remove_user(user_id=target.user_id)

    assert removed.account_status is AccountStatus.REMOVED
    assert removed.is_active is False
    assert auth_tokens.revoked_users == [target.user_id]


@pytest.mark.asyncio
async def test_block_user_raises_user_not_found_for_unknown_user() -> None:
    users = FakeUserRepository(users={})
    service = UserManagementService(users=users, auth_tokens=FakeAuthTokenRepository())

    with pytest.raises(UserNotFoundError):
        await service.block_user(user_id=uuid4())

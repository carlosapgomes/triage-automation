from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from triage_automation.application.ports.auth_token_repository_port import (
    AuthTokenCreateInput,
    AuthTokenRecord,
)
from triage_automation.application.ports.user_repository_port import UserCreateInput, UserRecord
from triage_automation.application.services.user_management_service import (
    InvalidUserEmailError,
    InvalidUserPasswordError,
    LastActiveAdminError,
    SelfUserManagementError,
    UserCreateRequest,
    UserManagementService,
    UserNotFoundError,
)
from triage_automation.domain.auth.account_status import AccountStatus
from triage_automation.domain.auth.roles import Role


def _make_user(
    *,
    user_id: UUID | None = None,
    email: str = "reader@example.org",
    password_hash: str = "hashed",
    role: Role = Role.READER,
    account_status: AccountStatus = AccountStatus.ACTIVE,
) -> UserRecord:
    now = datetime.now(tz=UTC)
    return UserRecord(
        user_id=user_id or uuid4(),
        email=email,
        password_hash=password_hash,
        role=role,
        is_active=account_status is AccountStatus.ACTIVE,
        account_status=account_status,
        created_at=now,
        updated_at=now,
    )


@dataclass
class FakeUserRepository:
    users: dict[UUID, UserRecord]
    create_payloads: list[UserCreateInput] = field(default_factory=list)

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
        self.create_payloads.append(payload)
        user = _make_user(
            user_id=payload.user_id,
            email=payload.email,
            password_hash=payload.password_hash,
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


class FakePasswordHasher:
    def __init__(self) -> None:
        self.hash_calls: list[str] = []

    def hash_password(self, password: str) -> str:
        self.hash_calls.append(password)
        return f"hashed::{password}"

    def verify_password(self, *, password: str, password_hash: str) -> bool:
        _ = password, password_hash
        return False


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
    service = UserManagementService(
        users=users,
        auth_tokens=FakeAuthTokenRepository(),
        password_hasher=FakePasswordHasher(),
    )

    listed = await service.list_users()

    assert [item.email for item in listed] == ["a@example.org", "b@example.org"]


@pytest.mark.asyncio
async def test_create_user_normalizes_email_and_hashes_password() -> None:
    users = FakeUserRepository(users={})
    password_hasher = FakePasswordHasher()
    service = UserManagementService(
        users=users,
        auth_tokens=FakeAuthTokenRepository(),
        password_hasher=password_hasher,
    )
    payload = UserCreateRequest(
        email=" New-Admin@Example.org ",
        password="  secret-pass  ",
        role=Role.ADMIN,
    )

    created = await service.create_user(payload=payload)

    assert created.email == "new-admin@example.org"
    assert created.password_hash == "hashed::secret-pass"
    assert created.role is Role.ADMIN
    assert created.account_status is AccountStatus.ACTIVE
    assert password_hasher.hash_calls == ["secret-pass"]
    assert users.create_payloads[0].email == "new-admin@example.org"
    assert users.create_payloads[0].password_hash == "hashed::secret-pass"


@pytest.mark.asyncio
async def test_create_user_rejects_blank_email() -> None:
    users = FakeUserRepository(users={})
    password_hasher = FakePasswordHasher()
    service = UserManagementService(
        users=users,
        auth_tokens=FakeAuthTokenRepository(),
        password_hasher=password_hasher,
    )

    with pytest.raises(InvalidUserEmailError):
        await service.create_user(
            payload=UserCreateRequest(
                email="   ",
                password="valid-password",
                role=Role.READER,
            )
        )

    assert users.create_payloads == []
    assert password_hasher.hash_calls == []


@pytest.mark.asyncio
async def test_create_user_rejects_blank_password() -> None:
    users = FakeUserRepository(users={})
    password_hasher = FakePasswordHasher()
    service = UserManagementService(
        users=users,
        auth_tokens=FakeAuthTokenRepository(),
        password_hasher=password_hasher,
    )

    with pytest.raises(InvalidUserPasswordError):
        await service.create_user(
            payload=UserCreateRequest(
                email="reader@example.org",
                password="   ",
                role=Role.READER,
            )
        )

    assert users.create_payloads == []
    assert password_hasher.hash_calls == []


@pytest.mark.asyncio
async def test_block_user_updates_status_and_revokes_tokens() -> None:
    target = _make_user(account_status=AccountStatus.ACTIVE)
    users = FakeUserRepository(users={target.user_id: target})
    auth_tokens = FakeAuthTokenRepository()
    service = UserManagementService(
        users=users,
        auth_tokens=auth_tokens,
        password_hasher=FakePasswordHasher(),
    )

    blocked = await service.block_user(
        actor_user_id=uuid4(),
        user_id=target.user_id,
    )

    assert blocked.account_status is AccountStatus.BLOCKED
    assert blocked.is_active is False
    assert auth_tokens.revoked_users == [target.user_id]


@pytest.mark.asyncio
async def test_reactivate_user_updates_status_without_revocation() -> None:
    target = _make_user(account_status=AccountStatus.BLOCKED)
    users = FakeUserRepository(users={target.user_id: target})
    auth_tokens = FakeAuthTokenRepository()
    service = UserManagementService(
        users=users,
        auth_tokens=auth_tokens,
        password_hasher=FakePasswordHasher(),
    )

    active = await service.reactivate_user(user_id=target.user_id)

    assert active.account_status is AccountStatus.ACTIVE
    assert active.is_active is True
    assert auth_tokens.revoked_users == []


@pytest.mark.asyncio
async def test_remove_user_updates_status_and_revokes_tokens() -> None:
    target = _make_user(account_status=AccountStatus.ACTIVE)
    users = FakeUserRepository(users={target.user_id: target})
    auth_tokens = FakeAuthTokenRepository()
    service = UserManagementService(
        users=users,
        auth_tokens=auth_tokens,
        password_hasher=FakePasswordHasher(),
    )

    removed = await service.remove_user(
        actor_user_id=uuid4(),
        user_id=target.user_id,
    )

    assert removed.account_status is AccountStatus.REMOVED
    assert removed.is_active is False
    assert auth_tokens.revoked_users == [target.user_id]


@pytest.mark.asyncio
async def test_block_user_raises_user_not_found_for_unknown_user() -> None:
    users = FakeUserRepository(users={})
    service = UserManagementService(
        users=users,
        auth_tokens=FakeAuthTokenRepository(),
        password_hasher=FakePasswordHasher(),
    )

    with pytest.raises(UserNotFoundError):
        await service.block_user(
            actor_user_id=uuid4(),
            user_id=uuid4(),
        )


@pytest.mark.asyncio
async def test_block_user_rejects_self_block_action() -> None:
    actor = _make_user(role=Role.ADMIN, account_status=AccountStatus.ACTIVE)
    other_admin = _make_user(role=Role.ADMIN, email="other-admin@example.org")
    users = FakeUserRepository(users={actor.user_id: actor, other_admin.user_id: other_admin})
    service = UserManagementService(
        users=users,
        auth_tokens=FakeAuthTokenRepository(),
        password_hasher=FakePasswordHasher(),
    )

    with pytest.raises(SelfUserManagementError):
        await service.block_user(
            actor_user_id=actor.user_id,
            user_id=actor.user_id,
        )


@pytest.mark.asyncio
async def test_remove_user_rejects_self_remove_action() -> None:
    actor = _make_user(role=Role.ADMIN, account_status=AccountStatus.ACTIVE)
    other_admin = _make_user(role=Role.ADMIN, email="other-admin@example.org")
    users = FakeUserRepository(users={actor.user_id: actor, other_admin.user_id: other_admin})
    service = UserManagementService(
        users=users,
        auth_tokens=FakeAuthTokenRepository(),
        password_hasher=FakePasswordHasher(),
    )

    with pytest.raises(SelfUserManagementError):
        await service.remove_user(
            actor_user_id=actor.user_id,
            user_id=actor.user_id,
        )


@pytest.mark.asyncio
async def test_block_user_rejects_disabling_last_active_admin() -> None:
    last_admin = _make_user(role=Role.ADMIN, account_status=AccountStatus.ACTIVE)
    blocked_admin = _make_user(
        role=Role.ADMIN,
        email="blocked-admin@example.org",
        account_status=AccountStatus.BLOCKED,
    )
    users = FakeUserRepository(
        users={
            last_admin.user_id: last_admin,
            blocked_admin.user_id: blocked_admin,
        }
    )
    service = UserManagementService(
        users=users,
        auth_tokens=FakeAuthTokenRepository(),
        password_hasher=FakePasswordHasher(),
    )

    with pytest.raises(LastActiveAdminError):
        await service.block_user(
            actor_user_id=uuid4(),
            user_id=last_admin.user_id,
        )


@pytest.mark.asyncio
async def test_remove_user_rejects_disabling_last_active_admin() -> None:
    last_admin = _make_user(role=Role.ADMIN, account_status=AccountStatus.ACTIVE)
    blocked_admin = _make_user(
        role=Role.ADMIN,
        email="blocked-admin@example.org",
        account_status=AccountStatus.BLOCKED,
    )
    users = FakeUserRepository(
        users={
            last_admin.user_id: last_admin,
            blocked_admin.user_id: blocked_admin,
        }
    )
    service = UserManagementService(
        users=users,
        auth_tokens=FakeAuthTokenRepository(),
        password_hasher=FakePasswordHasher(),
    )

    with pytest.raises(LastActiveAdminError):
        await service.remove_user(
            actor_user_id=uuid4(),
            user_id=last_admin.user_id,
        )

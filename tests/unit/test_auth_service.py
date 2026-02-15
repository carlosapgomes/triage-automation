from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from triage_automation.application.ports.auth_event_repository_port import AuthEventCreateInput
from triage_automation.application.ports.user_repository_port import UserRecord
from triage_automation.application.services.auth_service import AuthOutcome, AuthService
from triage_automation.domain.auth.roles import Role


@dataclass
class FakeUserRepository:
    user: UserRecord | None

    async def get_by_email(self, *, email: str) -> UserRecord | None:
        _ = email
        return self.user

    async def get_active_by_email(self, *, email: str) -> UserRecord | None:
        _ = email
        if self.user is None or not self.user.is_active:
            return None
        return self.user


class FakeAuthEventRepository:
    def __init__(self) -> None:
        self.events: list[AuthEventCreateInput] = []

    async def append_event(self, payload: AuthEventCreateInput) -> int:
        self.events.append(payload)
        return len(self.events)


class FakePasswordHasher:
    def __init__(self, *, should_verify: bool) -> None:
        self.should_verify = should_verify
        self.verify_calls: list[tuple[str, str]] = []

    def hash_password(self, password: str) -> str:
        return f"hashed::{password}"

    def verify_password(self, *, password: str, password_hash: str) -> bool:
        self.verify_calls.append((password, password_hash))
        return self.should_verify


def _user(*, is_active: bool = True) -> UserRecord:
    now = datetime.now(tz=UTC)
    return UserRecord(
        user_id=uuid4(),
        email="admin@example.com",
        password_hash="hashed::pw",
        role=Role.ADMIN,
        is_active=is_active,
        created_at=now,
        updated_at=now,
    )


@pytest.mark.asyncio
async def test_authenticate_success_returns_user_and_logs_success() -> None:
    user = _user(is_active=True)
    users = FakeUserRepository(user=user)
    auth_events = FakeAuthEventRepository()
    hasher = FakePasswordHasher(should_verify=True)
    service = AuthService(users=users, auth_events=auth_events, password_hasher=hasher)

    result = await service.authenticate(
        email=user.email,
        password="pw",
        ip_address="127.0.0.1",
        user_agent="pytest",
    )

    assert result.outcome is AuthOutcome.SUCCESS
    assert result.user == user
    assert hasher.verify_calls == [("pw", "hashed::pw")]
    assert len(auth_events.events) == 1
    event = auth_events.events[0]
    assert event.event_type == "login_success"
    assert event.user_id == user.user_id
    assert event.payload == {"email": user.email, "role": "admin"}


@pytest.mark.asyncio
async def test_authenticate_invalid_password_logs_failure_event() -> None:
    user = _user(is_active=True)
    users = FakeUserRepository(user=user)
    auth_events = FakeAuthEventRepository()
    hasher = FakePasswordHasher(should_verify=False)
    service = AuthService(users=users, auth_events=auth_events, password_hasher=hasher)

    result = await service.authenticate(
        email=user.email,
        password="wrong",
        ip_address="127.0.0.1",
        user_agent="pytest",
    )

    assert result.outcome is AuthOutcome.INVALID_CREDENTIALS
    assert result.user is None
    assert hasher.verify_calls == [("wrong", "hashed::pw")]
    assert len(auth_events.events) == 1
    event = auth_events.events[0]
    assert event.event_type == "login_failed"
    assert event.user_id == user.user_id
    assert event.payload == {"email": user.email, "reason": "invalid_credentials"}


@pytest.mark.asyncio
async def test_authenticate_inactive_user_blocks_without_password_check() -> None:
    user = _user(is_active=False)
    users = FakeUserRepository(user=user)
    auth_events = FakeAuthEventRepository()
    hasher = FakePasswordHasher(should_verify=True)
    service = AuthService(users=users, auth_events=auth_events, password_hasher=hasher)

    result = await service.authenticate(
        email=user.email,
        password="pw",
        ip_address="127.0.0.1",
        user_agent="pytest",
    )

    assert result.outcome is AuthOutcome.INACTIVE_USER
    assert result.user is None
    assert hasher.verify_calls == []
    assert len(auth_events.events) == 1
    event = auth_events.events[0]
    assert event.event_type == "login_blocked_inactive"
    assert event.user_id == user.user_id
    assert event.payload == {"email": user.email}


@pytest.mark.asyncio
async def test_authenticate_unknown_user_logs_invalid_credentials() -> None:
    users = FakeUserRepository(user=None)
    auth_events = FakeAuthEventRepository()
    hasher = FakePasswordHasher(should_verify=True)
    service = AuthService(users=users, auth_events=auth_events, password_hasher=hasher)

    result = await service.authenticate(
        email="missing@example.com",
        password="pw",
        ip_address="127.0.0.1",
        user_agent="pytest",
    )

    assert result.outcome is AuthOutcome.INVALID_CREDENTIALS
    assert result.user is None
    assert hasher.verify_calls == []
    assert len(auth_events.events) == 1
    event = auth_events.events[0]
    assert event.event_type == "login_failed"
    assert event.user_id is None
    assert event.payload == {
        "email": "missing@example.com",
        "reason": "invalid_credentials",
    }

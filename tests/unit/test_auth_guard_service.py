from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from triage_automation.application.ports.auth_token_repository_port import AuthTokenRecord
from triage_automation.application.ports.user_repository_port import UserRecord
from triage_automation.application.services.access_guard_service import RoleNotAuthorizedError
from triage_automation.domain.auth.roles import Role
from triage_automation.infrastructure.http.auth_guard import (
    InvalidAuthTokenError,
    MissingAuthTokenError,
    WidgetAuthGuard,
    extract_bearer_token,
)
from triage_automation.infrastructure.security.token_service import OpaqueTokenService


@dataclass
class FakeAuthTokenRepository:
    records_by_hash: dict[str, AuthTokenRecord]

    async def get_active_by_hash(self, *, token_hash: str) -> AuthTokenRecord | None:
        return self.records_by_hash.get(token_hash)


@dataclass
class FakeUserRepository:
    users_by_id: dict[object, UserRecord]

    async def get_by_id(self, *, user_id: object) -> UserRecord | None:
        return self.users_by_id.get(user_id)


def _user(*, role: Role) -> UserRecord:
    now = datetime.now(tz=UTC)
    return UserRecord(
        user_id=uuid4(),
        email=f"{role.value}@example.org",
        password_hash="hash",
        role=role,
        is_active=True,
        created_at=now,
        updated_at=now,
    )


def _token_record(*, user: UserRecord) -> AuthTokenRecord:
    now = datetime.now(tz=UTC)
    return AuthTokenRecord(
        id=1,
        user_id=user.user_id,
        token_hash="unused",
        issued_at=now,
        expires_at=now + timedelta(hours=1),
        revoked_at=None,
        last_used_at=None,
    )


def test_extract_bearer_token_returns_token_value() -> None:
    assert extract_bearer_token("Bearer opaque-token") == "opaque-token"


@pytest.mark.parametrize("header", [None, "", "   "])
def test_extract_bearer_token_rejects_missing_value(header: str | None) -> None:
    with pytest.raises(MissingAuthTokenError, match="missing bearer token"):
        extract_bearer_token(header)


@pytest.mark.parametrize("header", ["Basic token", "Bearer", "Bearer   "])
def test_extract_bearer_token_rejects_malformed_header(header: str) -> None:
    with pytest.raises(InvalidAuthTokenError, match="invalid bearer token header"):
        extract_bearer_token(header)


@pytest.mark.asyncio
async def test_widget_auth_guard_rejects_unknown_token() -> None:
    token_service = OpaqueTokenService()
    guard = WidgetAuthGuard(
        token_service=token_service,
        auth_token_repository=FakeAuthTokenRepository(records_by_hash={}),
        user_repository=FakeUserRepository(users_by_id={}),
    )

    with pytest.raises(InvalidAuthTokenError, match="invalid or expired auth token"):
        await guard.require_admin_user(authorization_header="Bearer missing-token")


@pytest.mark.asyncio
async def test_widget_auth_guard_rejects_non_admin_role() -> None:
    token_service = OpaqueTokenService()
    reader = _user(role=Role.READER)
    reader_token = "reader-token"
    reader_hash = token_service.hash_token(reader_token)
    token_record = _token_record(user=reader)

    guard = WidgetAuthGuard(
        token_service=token_service,
        auth_token_repository=FakeAuthTokenRepository(
            records_by_hash={
                reader_hash: AuthTokenRecord(
                    id=token_record.id,
                    user_id=token_record.user_id,
                    token_hash=reader_hash,
                    issued_at=token_record.issued_at,
                    expires_at=token_record.expires_at,
                    revoked_at=token_record.revoked_at,
                    last_used_at=token_record.last_used_at,
                )
            }
        ),
        user_repository=FakeUserRepository(users_by_id={reader.user_id: reader}),
    )

    with pytest.raises(RoleNotAuthorizedError, match="admin role required"):
        await guard.require_admin_user(authorization_header=f"Bearer {reader_token}")


@pytest.mark.asyncio
async def test_widget_auth_guard_accepts_valid_admin_token() -> None:
    token_service = OpaqueTokenService()
    admin = _user(role=Role.ADMIN)
    admin_token = "admin-token"
    admin_hash = token_service.hash_token(admin_token)
    token_record = _token_record(user=admin)

    guard = WidgetAuthGuard(
        token_service=token_service,
        auth_token_repository=FakeAuthTokenRepository(
            records_by_hash={
                admin_hash: AuthTokenRecord(
                    id=token_record.id,
                    user_id=token_record.user_id,
                    token_hash=admin_hash,
                    issued_at=token_record.issued_at,
                    expires_at=token_record.expires_at,
                    revoked_at=token_record.revoked_at,
                    last_used_at=token_record.last_used_at,
                )
            }
        ),
        user_repository=FakeUserRepository(users_by_id={admin.user_id: admin}),
    )

    authenticated_user = await guard.require_admin_user(
        authorization_header=f"Bearer {admin_token}"
    )

    assert authenticated_user.user_id == admin.user_id
    assert authenticated_user.role is Role.ADMIN


@pytest.mark.asyncio
async def test_widget_auth_guard_accepts_valid_reader_for_audit_access() -> None:
    token_service = OpaqueTokenService()
    reader = _user(role=Role.READER)
    reader_token = "reader-token"
    reader_hash = token_service.hash_token(reader_token)
    token_record = _token_record(user=reader)

    guard = WidgetAuthGuard(
        token_service=token_service,
        auth_token_repository=FakeAuthTokenRepository(
            records_by_hash={
                reader_hash: AuthTokenRecord(
                    id=token_record.id,
                    user_id=token_record.user_id,
                    token_hash=reader_hash,
                    issued_at=token_record.issued_at,
                    expires_at=token_record.expires_at,
                    revoked_at=token_record.revoked_at,
                    last_used_at=token_record.last_used_at,
                )
            }
        ),
        user_repository=FakeUserRepository(users_by_id={reader.user_id: reader}),
    )

    authenticated_user = await guard.require_audit_user(
        authorization_header=f"Bearer {reader_token}"
    )

    assert authenticated_user.user_id == reader.user_id
    assert authenticated_user.role is Role.READER

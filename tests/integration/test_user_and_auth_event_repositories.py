from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

import pytest
import sqlalchemy as sa
from alembic.config import Config

from alembic import command
from triage_automation.application.ports.auth_event_repository_port import (
    AuthEventCreateInput,
)
from triage_automation.application.ports.auth_token_repository_port import (
    AuthTokenCreateInput,
)
from triage_automation.application.ports.user_repository_port import UserCreateInput
from triage_automation.domain.auth.account_status import AccountStatus
from triage_automation.domain.auth.roles import Role
from triage_automation.infrastructure.db.auth_event_repository import SqlAlchemyAuthEventRepository
from triage_automation.infrastructure.db.auth_token_repository import SqlAlchemyAuthTokenRepository
from triage_automation.infrastructure.db.session import create_session_factory
from triage_automation.infrastructure.db.user_repository import SqlAlchemyUserRepository


def _upgrade_head(tmp_path: Path, filename: str) -> tuple[str, str]:
    db_path = tmp_path / filename
    sync_url = f"sqlite+pysqlite:///{db_path}"
    async_url = f"sqlite+aiosqlite:///{db_path}"

    alembic_config = Config("alembic.ini")
    alembic_config.set_main_option("sqlalchemy.url", sync_url)
    command.upgrade(alembic_config, "head")

    return sync_url, async_url


def _insert_user(
    connection: sa.Connection,
    *,
    user_id: UUID,
    email: str,
    role: str,
    is_active: bool,
    account_status: str | None = None,
) -> None:
    resolved_account_status = account_status or ("active" if is_active else "blocked")
    connection.execute(
        sa.text(
            "INSERT INTO users (id, email, password_hash, role, is_active, account_status) "
            "VALUES (:id, :email, :password_hash, :role, :is_active, :account_status)"
        ),
        {
            "id": user_id.hex,
            "email": email,
            "password_hash": "hash",
            "role": role,
            "is_active": is_active,
            "account_status": resolved_account_status,
        },
    )


def test_role_enum_values_are_exact_admin_and_reader() -> None:
    assert {member.value for member in Role} == {"admin", "reader"}


@pytest.mark.asyncio
async def test_user_repository_fetches_only_active_user_by_email(tmp_path: Path) -> None:
    sync_url, async_url = _upgrade_head(tmp_path, "user_repo_active.db")
    session_factory = create_session_factory(async_url)
    repo = SqlAlchemyUserRepository(session_factory)

    engine = sa.create_engine(sync_url)
    active_id = uuid4()
    inactive_id = uuid4()
    with engine.begin() as connection:
        _insert_user(
            connection,
            user_id=active_id,
            email="admin@example.org",
            role="admin",
            is_active=True,
        )
        _insert_user(
            connection,
            user_id=inactive_id,
            email="reader@example.org",
            role="reader",
            is_active=False,
        )

    active_user = await repo.get_active_by_email(email="admin@example.org")
    inactive_user = await repo.get_active_by_email(email="reader@example.org")

    assert active_user is not None
    assert active_user.user_id == active_id
    assert active_user.email == "admin@example.org"
    assert active_user.role == Role.ADMIN
    assert inactive_user is None


@pytest.mark.asyncio
async def test_auth_event_repository_appends_events(tmp_path: Path) -> None:
    sync_url, async_url = _upgrade_head(tmp_path, "auth_event_repo.db")
    session_factory = create_session_factory(async_url)
    user_repo = SqlAlchemyUserRepository(session_factory)
    auth_event_repo = SqlAlchemyAuthEventRepository(session_factory)

    engine = sa.create_engine(sync_url)
    user_id = uuid4()
    with engine.begin() as connection:
        _insert_user(
            connection,
            user_id=user_id,
            email="reader@example.org",
            role="reader",
            is_active=True,
        )

    inserted = await auth_event_repo.append_event(
        AuthEventCreateInput(
            user_id=user_id,
            event_type="LOGIN_SUCCESS",
            ip_address="127.0.0.1",
            user_agent="pytest",
            payload={"source": "integration-test"},
        )
    )
    assert inserted > 0

    fetched = await user_repo.get_active_by_email(email="reader@example.org")
    assert fetched is not None
    assert fetched.user_id == user_id

    with engine.begin() as connection:
        row = connection.execute(
            sa.text(
                "SELECT event_type, ip_address, user_agent, payload "
                "FROM auth_events WHERE id = :id"
            ),
            {"id": inserted},
        ).mappings().one()

    assert row["event_type"] == "LOGIN_SUCCESS"
    assert row["ip_address"] == "127.0.0.1"
    assert row["user_agent"] == "pytest"
    assert "integration-test" in str(row["payload"])


@pytest.mark.asyncio
async def test_auth_token_repository_persists_and_resolves_active_tokens(tmp_path: Path) -> None:
    sync_url, async_url = _upgrade_head(tmp_path, "auth_token_repo.db")
    session_factory = create_session_factory(async_url)
    token_repo = SqlAlchemyAuthTokenRepository(session_factory)

    engine = sa.create_engine(sync_url)
    user_id = uuid4()
    with engine.begin() as connection:
        _insert_user(
            connection,
            user_id=user_id,
            email="admin@example.org",
            role="admin",
            is_active=True,
        )

    expires_at = datetime.now(tz=UTC) + timedelta(hours=1)
    token = await token_repo.create_token(
        AuthTokenCreateInput(
            user_id=user_id,
            token_hash="opaque-token-hash",
            expires_at=expires_at,
        )
    )
    assert token.token_hash == "opaque-token-hash"

    active = await token_repo.get_active_by_hash(token_hash="opaque-token-hash")
    assert active is not None
    assert active.user_id == user_id

    with engine.begin() as connection:
        connection.execute(
            sa.text("UPDATE auth_tokens SET revoked_at = CURRENT_TIMESTAMP WHERE id = :id"),
            {"id": token.id},
        )

    revoked = await token_repo.get_active_by_hash(token_hash="opaque-token-hash")
    assert revoked is None


@pytest.mark.asyncio
async def test_auth_token_repository_revokes_active_tokens_for_user(tmp_path: Path) -> None:
    sync_url, async_url = _upgrade_head(tmp_path, "auth_token_revoke_by_user.db")
    session_factory = create_session_factory(async_url)
    token_repo = SqlAlchemyAuthTokenRepository(session_factory)

    engine = sa.create_engine(sync_url)
    target_user_id = uuid4()
    other_user_id = uuid4()
    with engine.begin() as connection:
        _insert_user(
            connection,
            user_id=target_user_id,
            email="target@example.org",
            role="reader",
            is_active=True,
        )
        _insert_user(
            connection,
            user_id=other_user_id,
            email="other@example.org",
            role="admin",
            is_active=True,
        )

    expires_at = datetime.now(tz=UTC) + timedelta(hours=1)
    await token_repo.create_token(
        AuthTokenCreateInput(
            user_id=target_user_id,
            token_hash="target-token-1",
            expires_at=expires_at,
        )
    )
    target_token_2 = await token_repo.create_token(
        AuthTokenCreateInput(
            user_id=target_user_id,
            token_hash="target-token-2",
            expires_at=expires_at,
        )
    )
    await token_repo.create_token(
        AuthTokenCreateInput(
            user_id=other_user_id,
            token_hash="other-token-1",
            expires_at=expires_at,
        )
    )
    with engine.begin() as connection:
        connection.execute(
            sa.text("UPDATE auth_tokens SET revoked_at = CURRENT_TIMESTAMP WHERE id = :id"),
            {"id": target_token_2.id},
        )

    revoked_count = await token_repo.revoke_active_tokens_for_user(user_id=target_user_id)
    assert revoked_count == 1

    assert await token_repo.get_active_by_hash(token_hash="target-token-1") is None
    assert await token_repo.get_active_by_hash(token_hash="target-token-2") is None
    assert await token_repo.get_active_by_hash(token_hash="other-token-1") is not None


@pytest.mark.asyncio
async def test_user_repository_lists_users_with_account_status(tmp_path: Path) -> None:
    sync_url, async_url = _upgrade_head(tmp_path, "user_repo_list.db")
    session_factory = create_session_factory(async_url)
    repo = SqlAlchemyUserRepository(session_factory)

    engine = sa.create_engine(sync_url)
    with engine.begin() as connection:
        _insert_user(
            connection,
            user_id=uuid4(),
            email="removed@example.org",
            role="reader",
            is_active=False,
            account_status="removed",
        )
        _insert_user(
            connection,
            user_id=uuid4(),
            email="active@example.org",
            role="admin",
            is_active=True,
            account_status="active",
        )

    users = await repo.list_users()
    assert [user.email for user in users] == ["active@example.org", "removed@example.org"]
    assert users[0].account_status is AccountStatus.ACTIVE
    assert users[0].is_active is True
    assert users[1].account_status is AccountStatus.REMOVED
    assert users[1].is_active is False


@pytest.mark.asyncio
async def test_user_repository_creates_user_and_applies_status_transitions(tmp_path: Path) -> None:
    sync_url, async_url = _upgrade_head(tmp_path, "user_repo_create_update.db")
    session_factory = create_session_factory(async_url)
    repo = SqlAlchemyUserRepository(session_factory)

    created = await repo.create_user(
        UserCreateInput(
            user_id=uuid4(),
            email="new-admin@example.org",
            password_hash="hashed-password",
            role=Role.ADMIN,
            account_status=AccountStatus.ACTIVE,
        )
    )
    assert created.email == "new-admin@example.org"
    assert created.role is Role.ADMIN
    assert created.account_status is AccountStatus.ACTIVE
    assert created.is_active is True

    blocked = await repo.set_account_status(
        user_id=created.user_id,
        account_status=AccountStatus.BLOCKED,
    )
    assert blocked is not None
    assert blocked.account_status is AccountStatus.BLOCKED
    assert blocked.is_active is False

    removed = await repo.set_account_status(
        user_id=created.user_id,
        account_status=AccountStatus.REMOVED,
    )
    assert removed is not None
    assert removed.account_status is AccountStatus.REMOVED
    assert removed.is_active is False

    reactivated = await repo.set_account_status(
        user_id=created.user_id,
        account_status=AccountStatus.ACTIVE,
    )
    assert reactivated is not None
    assert reactivated.account_status is AccountStatus.ACTIVE
    assert reactivated.is_active is True

    engine = sa.create_engine(sync_url)
    with engine.connect() as connection:
        row = (
            connection.execute(
                sa.text(
                    "SELECT email, role, is_active, account_status "
                    "FROM users "
                    "WHERE id = :id"
                ),
                {"id": created.user_id.hex},
            )
            .mappings()
            .one()
        )
    assert row["email"] == "new-admin@example.org"
    assert row["role"] == "admin"
    assert bool(row["is_active"]) is True
    assert row["account_status"] == "active"


@pytest.mark.asyncio
async def test_user_repository_create_blocked_user_sets_is_active_false(tmp_path: Path) -> None:
    sync_url, async_url = _upgrade_head(tmp_path, "user_repo_create_blocked.db")
    session_factory = create_session_factory(async_url)
    repo = SqlAlchemyUserRepository(session_factory)

    created = await repo.create_user(
        UserCreateInput(
            user_id=uuid4(),
            email="blocked-user@example.org",
            password_hash="hashed-password",
            role=Role.READER,
            account_status=AccountStatus.BLOCKED,
        )
    )
    assert created.account_status is AccountStatus.BLOCKED
    assert created.is_active is False

    engine = sa.create_engine(sync_url)
    with engine.connect() as connection:
        row = (
            connection.execute(
                sa.text(
                    "SELECT is_active, account_status FROM users WHERE id = :id"
                ),
                {"id": created.user_id.hex},
            )
            .mappings()
            .one()
        )
    assert bool(row["is_active"]) is False
    assert row["account_status"] == "blocked"


@pytest.mark.asyncio
async def test_user_repository_set_account_status_returns_none_for_unknown_user(
    tmp_path: Path,
) -> None:
    _, async_url = _upgrade_head(tmp_path, "user_repo_set_status_missing.db")
    session_factory = create_session_factory(async_url)
    repo = SqlAlchemyUserRepository(session_factory)

    updated = await repo.set_account_status(
        user_id=uuid4(),
        account_status=AccountStatus.BLOCKED,
    )

    assert updated is None

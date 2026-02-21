from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

import pytest
import sqlalchemy as sa
from alembic.config import Config
from fastapi.testclient import TestClient

from alembic import command
from apps.bot_api.main import create_app
from triage_automation.application.services.auth_service import AuthService
from triage_automation.infrastructure.db.auth_event_repository import SqlAlchemyAuthEventRepository
from triage_automation.infrastructure.db.auth_token_repository import SqlAlchemyAuthTokenRepository
from triage_automation.infrastructure.db.session import create_session_factory
from triage_automation.infrastructure.db.user_repository import SqlAlchemyUserRepository
from triage_automation.infrastructure.security.password_hasher import BcryptPasswordHasher
from triage_automation.infrastructure.security.token_service import OpaqueTokenService


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
) -> None:
    hasher = BcryptPasswordHasher()
    connection.execute(
        sa.text(
            "INSERT INTO users (id, email, password_hash, role, is_active, account_status) "
            "VALUES (:id, :email, :password_hash, :role, 1, 'active')"
        ),
        {
            "id": user_id.hex,
            "email": email,
            "password_hash": hasher.hash_password("unused-password"),
            "role": role,
        },
    )


def _insert_token(
    connection: sa.Connection,
    *,
    token_service: OpaqueTokenService,
    user_id: UUID,
    token: str,
) -> None:
    issued_at = datetime.now(tz=UTC)
    expires_at = issued_at + timedelta(hours=1)
    connection.execute(
        sa.text(
            "INSERT INTO auth_tokens (user_id, token_hash, expires_at, issued_at) "
            "VALUES (:user_id, :token_hash, :expires_at, :issued_at)"
        ),
        {
            "user_id": user_id.hex,
            "token_hash": token_service.hash_token(token),
            "expires_at": expires_at,
            "issued_at": issued_at,
        },
    )


def _build_client(async_url: str, *, token_service: OpaqueTokenService) -> TestClient:
    session_factory = create_session_factory(async_url)
    auth_service = AuthService(
        users=SqlAlchemyUserRepository(session_factory),
        auth_events=SqlAlchemyAuthEventRepository(session_factory),
        password_hasher=BcryptPasswordHasher(),
    )
    token_repository = SqlAlchemyAuthTokenRepository(session_factory)
    app = create_app(
        auth_service=auth_service,
        auth_token_repository=token_repository,
        token_service=token_service,
        database_url=async_url,
    )
    return TestClient(app)


@pytest.mark.asyncio
async def test_admin_get_users_page_renders_html(tmp_path: Path) -> None:
    sync_url, async_url = _upgrade_head(tmp_path, "user_management_admin_get_page.db")
    token_service = OpaqueTokenService()
    admin_id = uuid4()
    admin_token = "admin-users-page-token"

    engine = sa.create_engine(sync_url)
    with engine.begin() as connection:
        _insert_user(connection, user_id=admin_id, email="admin@example.org", role="admin")
        _insert_token(
            connection,
            token_service=token_service,
            user_id=admin_id,
            token=admin_token,
        )

    with _build_client(async_url, token_service=token_service) as client:
        response = client.get(
            "/admin/users",
            headers={"Authorization": f"Bearer {admin_token}"},
        )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "Gestao de Usuarios" in response.text


@pytest.mark.asyncio
async def test_admin_create_user_form_persists_new_account(tmp_path: Path) -> None:
    sync_url, async_url = _upgrade_head(tmp_path, "user_management_admin_create_form.db")
    token_service = OpaqueTokenService()
    admin_id = uuid4()
    admin_token = "admin-users-create-token"

    engine = sa.create_engine(sync_url)
    with engine.begin() as connection:
        _insert_user(connection, user_id=admin_id, email="admin@example.org", role="admin")
        _insert_token(
            connection,
            token_service=token_service,
            user_id=admin_id,
            token=admin_token,
        )

    with _build_client(async_url, token_service=token_service) as client:
        response = client.post(
            "/admin/users",
            headers={"Authorization": f"Bearer {admin_token}"},
            data={
                "email": " New.Reader@Example.org ",
                "password": "  test-password  ",
                "role": "reader",
            },
            follow_redirects=False,
        )

    assert response.status_code == 303
    assert response.headers["location"].startswith("/admin/users")

    with sa.create_engine(sync_url).begin() as connection:
        created = connection.execute(
            sa.text(
                "SELECT email, role, is_active, account_status "
                "FROM users WHERE email = :email LIMIT 1"
            ),
            {"email": "new.reader@example.org"},
        ).mappings().one()

        event = connection.execute(
            sa.text(
                "SELECT event_type, payload FROM auth_events "
                "WHERE event_type = 'user_created' ORDER BY id DESC LIMIT 1"
            )
        ).mappings().one()

    assert created["email"] == "new.reader@example.org"
    assert created["role"] == "reader"
    assert bool(created["is_active"]) is True
    assert str(created["account_status"]) == "active"
    assert event["event_type"] == "user_created"


@pytest.mark.asyncio
async def test_admin_create_user_form_shows_success_feedback_banner(tmp_path: Path) -> None:
    sync_url, async_url = _upgrade_head(tmp_path, "user_management_admin_feedback_success.db")
    token_service = OpaqueTokenService()
    admin_id = uuid4()
    admin_token = "admin-users-success-feedback-token"

    engine = sa.create_engine(sync_url)
    with engine.begin() as connection:
        _insert_user(connection, user_id=admin_id, email="admin@example.org", role="admin")
        _insert_token(
            connection,
            token_service=token_service,
            user_id=admin_id,
            token=admin_token,
        )

    with _build_client(async_url, token_service=token_service) as client:
        response = client.post(
            "/admin/users",
            headers={"Authorization": f"Bearer {admin_token}"},
            data={
                "email": "feedback.reader@example.org",
                "password": "test-password",
                "role": "reader",
            },
        )

    assert response.status_code == 200
    assert "Usuario criado:" in response.text
    assert "feedback.reader@example.org" in response.text
    assert "alert alert-success" in response.text


@pytest.mark.asyncio
async def test_admin_create_user_form_duplicate_email_shows_error_feedback(
    tmp_path: Path,
) -> None:
    sync_url, async_url = _upgrade_head(tmp_path, "user_management_admin_feedback_duplicate.db")
    token_service = OpaqueTokenService()
    admin_id = uuid4()
    existing_id = uuid4()
    admin_token = "admin-users-duplicate-feedback-token"

    engine = sa.create_engine(sync_url)
    with engine.begin() as connection:
        _insert_user(connection, user_id=admin_id, email="admin@example.org", role="admin")
        _insert_user(
            connection,
            user_id=existing_id,
            email="existing.reader@example.org",
            role="reader",
        )
        _insert_token(
            connection,
            token_service=token_service,
            user_id=admin_id,
            token=admin_token,
        )

    with _build_client(async_url, token_service=token_service) as client:
        response = client.post(
            "/admin/users",
            headers={"Authorization": f"Bearer {admin_token}"},
            data={
                "email": " Existing.Reader@Example.org ",
                "password": "another-password",
                "role": "reader",
            },
        )

    assert response.status_code == 200
    assert "Email ja cadastrado." in response.text
    assert "alert alert-danger" in response.text

    with sa.create_engine(sync_url).begin() as connection:
        count = connection.execute(
            sa.text(
                "SELECT COUNT(*) FROM users WHERE lower(email) = lower(:email)"
            ),
            {"email": "existing.reader@example.org"},
        ).scalar_one()
    assert int(count) == 1


@pytest.mark.asyncio
async def test_admin_user_actions_block_activate_remove_target(tmp_path: Path) -> None:
    sync_url, async_url = _upgrade_head(tmp_path, "user_management_admin_lifecycle_actions.db")
    token_service = OpaqueTokenService()
    admin_id = uuid4()
    target_id = uuid4()
    admin_token = "admin-users-lifecycle-token"

    engine = sa.create_engine(sync_url)
    with engine.begin() as connection:
        _insert_user(connection, user_id=admin_id, email="admin@example.org", role="admin")
        _insert_user(connection, user_id=target_id, email="reader@example.org", role="reader")
        _insert_token(
            connection,
            token_service=token_service,
            user_id=admin_id,
            token=admin_token,
        )

    with _build_client(async_url, token_service=token_service) as client:
        block_response = client.post(
            f"/admin/users/{target_id}/block",
            headers={"Authorization": f"Bearer {admin_token}"},
            follow_redirects=False,
        )
        activate_response = client.post(
            f"/admin/users/{target_id}/activate",
            headers={"Authorization": f"Bearer {admin_token}"},
            follow_redirects=False,
        )
        remove_response = client.post(
            f"/admin/users/{target_id}/remove",
            headers={"Authorization": f"Bearer {admin_token}"},
            follow_redirects=False,
        )

    assert block_response.status_code == 303
    assert activate_response.status_code == 303
    assert remove_response.status_code == 303

    with sa.create_engine(sync_url).begin() as connection:
        target = connection.execute(
            sa.text(
                "SELECT is_active, account_status FROM users WHERE id = :id LIMIT 1"
            ),
            {"id": target_id.hex},
        ).mappings().one()
        events = connection.execute(
            sa.text(
                "SELECT event_type FROM auth_events "
                "WHERE event_type IN ('user_blocked', 'user_reactivated', 'user_removed') "
                "ORDER BY id"
            )
        ).scalars().all()

    assert bool(target["is_active"]) is False
    assert str(target["account_status"]) == "removed"
    assert events == ["user_blocked", "user_reactivated", "user_removed"]


@pytest.mark.asyncio
async def test_reader_get_users_page_is_forbidden_with_403(tmp_path: Path) -> None:
    sync_url, async_url = _upgrade_head(tmp_path, "user_management_reader_get_forbidden.db")
    token_service = OpaqueTokenService()
    reader_id = uuid4()
    reader_token = "reader-users-page-token"

    engine = sa.create_engine(sync_url)
    with engine.begin() as connection:
        _insert_user(connection, user_id=reader_id, email="reader@example.org", role="reader")
        _insert_token(
            connection,
            token_service=token_service,
            user_id=reader_id,
            token=reader_token,
        )

    with _build_client(async_url, token_service=token_service) as client:
        response = client.get(
            "/admin/users",
            headers={"Authorization": f"Bearer {reader_token}"},
        )

    assert response.status_code == 403
    assert response.json() == {"detail": "admin role required"}


@pytest.mark.asyncio
async def test_reader_user_admin_actions_are_forbidden_and_do_not_mutate_state(
    tmp_path: Path,
) -> None:
    sync_url, async_url = _upgrade_head(tmp_path, "user_management_reader_actions_forbidden.db")
    token_service = OpaqueTokenService()
    reader_id = uuid4()
    target_id = uuid4()
    reader_token = "reader-users-actions-token"

    engine = sa.create_engine(sync_url)
    with engine.begin() as connection:
        _insert_user(connection, user_id=reader_id, email="reader@example.org", role="reader")
        _insert_user(
            connection,
            user_id=target_id,
            email="target.reader@example.org",
            role="reader",
        )
        _insert_token(
            connection,
            token_service=token_service,
            user_id=reader_id,
            token=reader_token,
        )

    with _build_client(async_url, token_service=token_service) as client:
        create_response = client.post(
            "/admin/users",
            headers={"Authorization": f"Bearer {reader_token}"},
            data={
                "email": "new.reader@example.org",
                "password": "reader-password",
                "role": "reader",
            },
        )
        block_response = client.post(
            f"/admin/users/{target_id}/block",
            headers={"Authorization": f"Bearer {reader_token}"},
        )
        activate_response = client.post(
            f"/admin/users/{target_id}/activate",
            headers={"Authorization": f"Bearer {reader_token}"},
        )
        remove_response = client.post(
            f"/admin/users/{target_id}/remove",
            headers={"Authorization": f"Bearer {reader_token}"},
        )

    for response in (
        create_response,
        block_response,
        activate_response,
        remove_response,
    ):
        assert response.status_code == 403
        assert response.json() == {"detail": "admin role required"}

    with sa.create_engine(sync_url).begin() as connection:
        user_count = connection.execute(sa.text("SELECT COUNT(*) FROM users")).scalar_one()
        target_row = connection.execute(
            sa.text(
                "SELECT is_active, account_status FROM users WHERE id = :id LIMIT 1"
            ),
            {"id": target_id.hex},
        ).mappings().one()
        admin_event_count = connection.execute(
            sa.text(
                "SELECT COUNT(*) FROM auth_events "
                "WHERE event_type IN ("
                "'user_created', 'user_blocked', 'user_reactivated', 'user_removed'"
                ")"
            )
        ).scalar_one()

    assert int(user_count) == 2
    assert bool(target_row["is_active"]) is True
    assert str(target_row["account_status"]) == "active"
    assert int(admin_event_count) == 0

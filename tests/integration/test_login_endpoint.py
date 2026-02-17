from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

import pytest
import sqlalchemy as sa
from alembic.config import Config
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from alembic import command
from apps.bot_api.main import create_app
from triage_automation.application.services.auth_service import AuthService
from triage_automation.application.services.handle_doctor_decision_service import (
    HandleDoctorDecisionService,
)
from triage_automation.infrastructure.db.audit_repository import SqlAlchemyAuditRepository
from triage_automation.infrastructure.db.auth_event_repository import SqlAlchemyAuthEventRepository
from triage_automation.infrastructure.db.auth_token_repository import SqlAlchemyAuthTokenRepository
from triage_automation.infrastructure.db.case_repository import SqlAlchemyCaseRepository
from triage_automation.infrastructure.db.job_queue_repository import SqlAlchemyJobQueueRepository
from triage_automation.infrastructure.db.session import create_session_factory
from triage_automation.infrastructure.db.user_repository import SqlAlchemyUserRepository
from triage_automation.infrastructure.security.password_hasher import BcryptPasswordHasher
from triage_automation.infrastructure.security.token_service import OpaqueTokenService

SECRET = "webhook-secret"


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
    password_hash: str,
    role: str,
    is_active: bool,
) -> None:
    connection.execute(
        sa.text(
            "INSERT INTO users (id, email, password_hash, role, is_active) "
            "VALUES (:id, :email, :password_hash, :role, :is_active)"
        ),
        {
            "id": user_id.hex,
            "email": email,
            "password_hash": password_hash,
            "role": role,
            "is_active": is_active,
        },
    )


def _build_client(async_url: str, *, token_service: OpaqueTokenService | None = None) -> TestClient:
    session_factory = create_session_factory(async_url)
    decision_service = HandleDoctorDecisionService(
        case_repository=SqlAlchemyCaseRepository(session_factory),
        audit_repository=SqlAlchemyAuditRepository(session_factory),
        job_queue=SqlAlchemyJobQueueRepository(session_factory),
    )
    auth_service = AuthService(
        users=SqlAlchemyUserRepository(session_factory),
        auth_events=SqlAlchemyAuthEventRepository(session_factory),
        password_hasher=BcryptPasswordHasher(),
    )
    token_repository = SqlAlchemyAuthTokenRepository(session_factory)
    app = create_app(
        webhook_hmac_secret=SECRET,
        decision_service=decision_service,
        auth_service=auth_service,
        auth_token_repository=token_repository,
        token_service=token_service,
        database_url=async_url,
    )
    return TestClient(app)


@pytest.mark.asyncio
async def test_valid_credentials_return_opaque_token_role_and_persist_hash(tmp_path: Path) -> None:
    sync_url, async_url = _upgrade_head(tmp_path, "login_success.db")
    user_id = uuid4()
    hasher = BcryptPasswordHasher()
    fixed_now = datetime(2026, 2, 15, 0, 0, 0, tzinfo=UTC)
    token_service = OpaqueTokenService(
        token_ttl=timedelta(hours=1),
        token_factory=lambda: "opaque-token-value",
        now=lambda: fixed_now,
    )

    engine = sa.create_engine(sync_url)
    with engine.begin() as connection:
        _insert_user(
            connection,
            user_id=user_id,
            email="admin@example.org",
            password_hash=hasher.hash_password("correct-password"),
            role="admin",
            is_active=True,
        )

    with _build_client(async_url, token_service=token_service) as client:
        response = client.post(
            "/auth/login",
            json={"email": "admin@example.org", "password": "correct-password"},
            headers={"user-agent": "pytest-client"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["token"] == "opaque-token-value"
    assert body["role"] == "admin"
    assert body["expires_at"] == "2026-02-15T01:00:00Z"

    with engine.begin() as connection:
        auth_event = connection.execute(
            sa.text(
                "SELECT event_type, user_id, payload FROM auth_events "
                "ORDER BY id DESC LIMIT 1"
            )
        ).mappings().one()
        auth_token = connection.execute(
            sa.text(
                "SELECT user_id, token_hash FROM auth_tokens "
                "ORDER BY id DESC LIMIT 1"
            )
        ).mappings().one()

    assert auth_event["event_type"] == "login_success"
    assert UUID(str(auth_event["user_id"])) == user_id
    assert "admin@example.org" in str(auth_event["payload"])

    assert UUID(str(auth_token["user_id"])) == user_id
    assert auth_token["token_hash"] == token_service.hash_token("opaque-token-value")


@pytest.mark.asyncio
async def test_invalid_credentials_return_auth_error_and_no_token_row(tmp_path: Path) -> None:
    sync_url, async_url = _upgrade_head(tmp_path, "login_invalid.db")
    user_id = uuid4()
    hasher = BcryptPasswordHasher()

    engine = sa.create_engine(sync_url)
    with engine.begin() as connection:
        _insert_user(
            connection,
            user_id=user_id,
            email="admin@example.org",
            password_hash=hasher.hash_password("correct-password"),
            role="admin",
            is_active=True,
        )

    with _build_client(async_url) as client:
        response = client.post(
            "/auth/login",
            json={"email": "admin@example.org", "password": "wrong-password"},
            headers={"user-agent": "pytest-client"},
        )

    assert response.status_code == 401
    assert response.json() == {"detail": "invalid credentials"}

    with engine.begin() as connection:
        auth_event = connection.execute(
            sa.text("SELECT event_type, payload FROM auth_events ORDER BY id DESC LIMIT 1")
        ).mappings().one()
        auth_token_count = connection.execute(
            sa.text("SELECT COUNT(*) AS count FROM auth_tokens")
        ).mappings().one()

    assert auth_event["event_type"] == "login_failed"
    assert "invalid_credentials" in str(auth_event["payload"])
    assert int(auth_token_count["count"]) == 0


@pytest.mark.asyncio
async def test_inactive_user_returns_forbidden_and_no_token_row(tmp_path: Path) -> None:
    sync_url, async_url = _upgrade_head(tmp_path, "login_inactive.db")
    user_id = uuid4()
    hasher = BcryptPasswordHasher()

    engine = sa.create_engine(sync_url)
    with engine.begin() as connection:
        _insert_user(
            connection,
            user_id=user_id,
            email="reader@example.org",
            password_hash=hasher.hash_password("reader-password"),
            role="reader",
            is_active=False,
        )

    with _build_client(async_url) as client:
        response = client.post(
            "/auth/login",
            json={"email": "reader@example.org", "password": "reader-password"},
            headers={"user-agent": "pytest-client"},
        )

    assert response.status_code == 403
    assert response.json() == {"detail": "inactive user"}

    with engine.begin() as connection:
        auth_event = connection.execute(
            sa.text("SELECT event_type FROM auth_events ORDER BY id DESC LIMIT 1")
        ).mappings().one()
        auth_token_count = connection.execute(
            sa.text("SELECT COUNT(*) AS count FROM auth_tokens")
        ).mappings().one()

    assert auth_event["event_type"] == "login_blocked_inactive"
    assert int(auth_token_count["count"]) == 0


@pytest.mark.asyncio
async def test_route_paths_only_add_login_endpoint(tmp_path: Path) -> None:
    _, async_url = _upgrade_head(tmp_path, "login_routes.db")

    with _build_client(async_url) as client:
        paths = {route.path for route in client.app.routes if isinstance(route, APIRoute)}

    assert paths == {
        "/auth/login",
        "/callbacks/triage-decision",
        "/widget/room2/bootstrap",
        "/widget/room2/submit",
    }

from __future__ import annotations

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
from triage_automation.infrastructure.http.auth_guard import SESSION_COOKIE_NAME
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
    password_hash: str,
    role: str = "admin",
) -> None:
    connection.execute(
        sa.text(
            "INSERT INTO users (id, email, password_hash, role, is_active) "
            "VALUES (:id, :email, :password_hash, :role, 1)"
        ),
        {
            "id": user_id.hex,
            "email": email,
            "password_hash": password_hash,
            "role": role,
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
async def test_root_redirects_to_login_for_anonymous_and_to_dashboard_when_session_exists(
    tmp_path: Path,
) -> None:
    sync_url, async_url = _upgrade_head(tmp_path, "web_session_root_redirects.db")
    hasher = BcryptPasswordHasher()
    token_service = OpaqueTokenService(token_factory=lambda: "web-session-token")
    admin_id = uuid4()

    with sa.create_engine(sync_url).begin() as connection:
        _insert_user(
            connection,
            user_id=admin_id,
            email="admin@example.org",
            password_hash=hasher.hash_password("correct-password"),
        )

    with _build_client(async_url, token_service=token_service) as client:
        anonymous_root = client.get("/", follow_redirects=False)
        login_page = client.get("/login")
        login_response = client.post(
            "/login",
            data={"email": "admin@example.org", "password": "correct-password"},
            follow_redirects=False,
        )
        authenticated_root = client.get("/", follow_redirects=False)

    assert anonymous_root.status_code == 303
    assert anonymous_root.headers["location"] == "/login"
    assert login_page.status_code == 200
    assert login_page.headers["content-type"].startswith("text/html")
    assert '<form method="post" action="/login">' in login_page.text
    assert 'name="email"' in login_page.text
    assert 'name="password"' in login_page.text
    assert login_response.status_code == 303
    assert login_response.headers["location"] == "/dashboard/cases"
    assert SESSION_COOKIE_NAME in login_response.headers.get("set-cookie", "")
    assert authenticated_root.status_code == 303
    assert authenticated_root.headers["location"] == "/dashboard/cases"


@pytest.mark.asyncio
async def test_login_rejects_invalid_credentials_without_session_cookie(tmp_path: Path) -> None:
    _, async_url = _upgrade_head(tmp_path, "web_session_invalid_credentials.db")
    token_service = OpaqueTokenService()

    with _build_client(async_url, token_service=token_service) as client:
        response = client.post(
            "/login",
            data={"email": "missing@example.org", "password": "wrong"},
        )

    assert response.status_code == 401
    assert response.headers["content-type"].startswith("text/html")
    assert "Credenciais invalidas" in response.text
    assert SESSION_COOKIE_NAME not in response.headers.get("set-cookie", "")


@pytest.mark.asyncio
async def test_logout_clears_cookie_and_redirects_to_login(tmp_path: Path) -> None:
    sync_url, async_url = _upgrade_head(tmp_path, "web_session_logout.db")
    hasher = BcryptPasswordHasher()
    token_service = OpaqueTokenService(token_factory=lambda: "logout-session-token")
    admin_id = uuid4()

    with sa.create_engine(sync_url).begin() as connection:
        _insert_user(
            connection,
            user_id=admin_id,
            email="admin@example.org",
            password_hash=hasher.hash_password("correct-password"),
        )

    with _build_client(async_url, token_service=token_service) as client:
        client.post(
            "/login",
            data={"email": "admin@example.org", "password": "correct-password"},
            follow_redirects=False,
        )
        logout_response = client.post("/logout", follow_redirects=False)
        root_after_logout = client.get("/", follow_redirects=False)

    assert logout_response.status_code == 303
    assert logout_response.headers["location"] == "/login"
    assert SESSION_COOKIE_NAME in logout_response.headers.get("set-cookie", "")
    assert root_after_logout.status_code == 303
    assert root_after_logout.headers["location"] == "/login"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("role", "expected_prompt_status"),
    [
        ("admin", 200),
        ("reader", 403),
    ],
)
async def test_session_role_matrix_dashboard_allowed_and_prompt_admin_restricted(
    tmp_path: Path,
    role: str,
    expected_prompt_status: int,
) -> None:
    sync_url, async_url = _upgrade_head(tmp_path, f"web_session_role_matrix_{role}.db")
    hasher = BcryptPasswordHasher()
    token_service = OpaqueTokenService(token_factory=lambda: f"{role}-session-token")
    user_id = uuid4()
    email = f"{role}@example.org"

    with sa.create_engine(sync_url).begin() as connection:
        _insert_user(
            connection,
            user_id=user_id,
            email=email,
            password_hash=hasher.hash_password("correct-password"),
            role=role,
        )

    with _build_client(async_url, token_service=token_service) as client:
        login_response = client.post(
            "/login",
            data={"email": email, "password": "correct-password"},
            follow_redirects=False,
        )
        dashboard_response = client.get("/dashboard/cases")
        prompts_response = client.get("/admin/prompts", follow_redirects=False)

    assert login_response.status_code == 303
    assert login_response.headers["location"] == "/dashboard/cases"
    assert dashboard_response.status_code == 200
    assert prompts_response.status_code == expected_prompt_status
    if role == "admin":
        assert prompts_response.headers["content-type"].startswith("text/html")
        assert "Gestao de Prompts" in prompts_response.text
    else:
        assert prompts_response.json() == {"detail": "admin role required"}

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import cast
from uuid import UUID, uuid4

import pytest
import sqlalchemy as sa
from alembic.config import Config
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from alembic import command
from apps.bot_api import main as bot_api_main
from triage_automation.application.ports.auth_token_repository_port import (
    AuthTokenRepositoryPort,
)
from triage_automation.application.services.auth_service import AuthService
from triage_automation.infrastructure.security.password_hasher import BcryptPasswordHasher
from triage_automation.infrastructure.security.token_service import OpaqueTokenService


class _DummyAuthService:
    async def authenticate(
        self,
        *,
        email: str,
        password: str,
        ip_address: str,
        user_agent: str,
    ) -> object:
        _ = email, password, ip_address, user_agent
        raise RuntimeError("not used in route-shape test")


class _DummyAuthTokenRepository:
    async def create_token(self, payload: object) -> object:
        _ = payload
        raise RuntimeError("not used in route-shape test")


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
            "INSERT INTO users (id, email, password_hash, role, is_active) "
            "VALUES (:id, :email, :password_hash, :role, 1)"
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


def test_main_starts_uvicorn_with_factory(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def _fake_run(app: str, **kwargs: object) -> None:
        captured["app"] = app
        captured["kwargs"] = kwargs

    monkeypatch.setattr(
        bot_api_main,
        "uvicorn",
        type("UvicornStub", (), {"run": _fake_run}),
        raising=False,
    )

    bot_api_main.main()

    assert captured["app"] == "apps.bot_api.main:create_app"
    assert captured["kwargs"] == {"host": "0.0.0.0", "port": 8000, "factory": True}


def test_build_runtime_app_exposes_existing_route_paths() -> None:
    app = bot_api_main.build_runtime_app(
        auth_service=cast(AuthService, _DummyAuthService()),
        auth_token_repository=cast(AuthTokenRepositoryPort, _DummyAuthTokenRepository()),
        token_service=OpaqueTokenService(),
        database_url="sqlite+aiosqlite:///unused.db",
    )

    paths = {route.path for route in app.routes if isinstance(route, APIRoute)}
    assert paths == {
        "/",
        "/login",
        "/logout",
        "/auth/login",
        "/monitoring/cases",
        "/monitoring/cases/{case_id}",
        "/dashboard/cases",
        "/dashboard/cases/{case_id}",
        "/admin/prompts",
        "/admin/prompts/{prompt_name}/activate-form",
        "/admin/prompts/{prompt_name}/create-form",
        "/admin/prompts/{prompt_name}/versions/{version}",
        "/admin/prompts/versions",
        "/admin/prompts/{prompt_name}/active",
        "/admin/prompts/{prompt_name}/activate",
        "/admin/users",
        "/admin/users/{user_id}/block",
        "/admin/users/{user_id}/activate",
        "/admin/users/{user_id}/remove",
    }


def test_runtime_app_serves_monitoring_and_prompt_admin_routes_in_same_process(
    tmp_path: Path,
) -> None:
    sync_url, async_url = _upgrade_head(tmp_path, "bot_api_runtime_same_process.db")
    token_service = OpaqueTokenService()
    admin_id = uuid4()
    admin_token = "admin-runtime-surface-token"

    engine = sa.create_engine(sync_url)
    with engine.begin() as connection:
        _insert_user(connection, user_id=admin_id, email="admin@example.org", role="admin")
        _insert_token(
            connection,
            token_service=token_service,
            user_id=admin_id,
            token=admin_token,
        )

    auth_service = bot_api_main.build_auth_service(async_url)
    auth_token_repository = bot_api_main.build_auth_token_repository(async_url)
    app = bot_api_main.build_runtime_app(
        token_service=token_service,
        database_url=async_url,
        auth_service=auth_service,
        auth_token_repository=auth_token_repository,
    )
    auth_headers = {"Authorization": f"Bearer {admin_token}"}

    with TestClient(app) as client:
        monitoring_response = client.get("/monitoring/cases", headers=auth_headers)
        prompt_admin_response = client.get("/admin/prompts/versions", headers=auth_headers)
        users_admin_response = client.get("/admin/users", headers=auth_headers)

    assert monitoring_response.status_code == 200
    assert prompt_admin_response.status_code == 200
    assert users_admin_response.status_code == 200
    assert "items" in monitoring_response.json()
    assert "items" in prompt_admin_response.json()
    assert users_admin_response.headers["content-type"].startswith("text/html")


def test_runtime_app_keeps_legacy_http_decision_route_absent(tmp_path: Path) -> None:
    sync_url, async_url = _upgrade_head(tmp_path, "bot_api_runtime_matrix_only.db")
    token_service = OpaqueTokenService()
    admin_id = uuid4()
    admin_token = "admin-runtime-matrix-only-token"

    engine = sa.create_engine(sync_url)
    with engine.begin() as connection:
        _insert_user(connection, user_id=admin_id, email="admin@example.org", role="admin")
        _insert_token(
            connection,
            token_service=token_service,
            user_id=admin_id,
            token=admin_token,
        )

    auth_service = bot_api_main.build_auth_service(async_url)
    auth_token_repository = bot_api_main.build_auth_token_repository(async_url)
    app = bot_api_main.build_runtime_app(
        token_service=token_service,
        database_url=async_url,
        auth_service=auth_service,
        auth_token_repository=auth_token_repository,
    )

    runtime_paths = {route.path for route in app.routes if isinstance(route, APIRoute)}
    assert "/callbacks/triage-decision" not in runtime_paths
    assert all("callbacks" not in path for path in runtime_paths)

    with TestClient(app) as client:
        response = client.post(
            "/callbacks/triage-decision",
            json={"case_id": str(uuid4()), "decision": "accept"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )

    assert response.status_code == 404

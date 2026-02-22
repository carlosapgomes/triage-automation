from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

import pytest
import sqlalchemy as sa
from alembic.config import Config
from fastapi.testclient import TestClient

from alembic import command
from apps.bot_api.main import create_app
from triage_automation.config import settings as settings_module
from triage_automation.config.settings import load_settings
from triage_automation.infrastructure.security.password_hasher import BcryptPasswordHasher

REQUIRED_ENV = {
    "ROOM1_ID": "!room1:example.org",
    "ROOM2_ID": "!room2:example.org",
    "ROOM3_ID": "!room3:example.org",
    "MATRIX_HOMESERVER_URL": "https://matrix.example.org",
    "MATRIX_BOT_USER_ID": "@triage-bot:example.org",
    "MATRIX_ACCESS_TOKEN": "matrix-access-token",
    "WEBHOOK_PUBLIC_URL": "https://webhook.example.org",
    "WEBHOOK_HMAC_SECRET": "super-secret",
}


def _upgrade_head(tmp_path: Path, filename: str) -> tuple[str, str]:
    db_path = tmp_path / filename
    sync_url = f"sqlite+pysqlite:///{db_path}"
    async_url = f"sqlite+aiosqlite:///{db_path}"

    alembic_config = Config("alembic.ini")
    alembic_config.set_main_option("sqlalchemy.url", sync_url)
    command.upgrade(alembic_config, "head")
    return sync_url, async_url


def _set_runtime_env(monkeypatch: pytest.MonkeyPatch, *, database_url: str) -> None:
    for key, value in REQUIRED_ENV.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setenv("DATABASE_URL", database_url)


def _clear_bootstrap_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BOOTSTRAP_ADMIN_EMAIL", raising=False)
    monkeypatch.delenv("BOOTSTRAP_ADMIN_PASSWORD", raising=False)
    monkeypatch.delenv("BOOTSTRAP_ADMIN_PASSWORD_FILE", raising=False)


def _insert_user(connection: sa.Connection, *, email: str, role: str = "reader") -> None:
    hasher = BcryptPasswordHasher()
    connection.execute(
        sa.text(
            "INSERT INTO users (id, email, password_hash, role, is_active) "
            "VALUES (:id, :email, :password_hash, :role, 1)"
        ),
        {
            "id": uuid4().hex,
            "email": email,
            "password_hash": hasher.hash_password("existing-password"),
            "role": role,
        },
    )


def _create_runtime_test_client() -> TestClient:
    load_settings.cache_clear()
    # Mock load_settings to return controlled values, avoiding .env file interference
    # Create a mock settings object with bootstrap values from env vars (not .env file)
    mock_settings = load_settings()
    mock_settings.bootstrap_admin_email = os.environ.get("BOOTSTRAP_ADMIN_EMAIL")
    mock_settings.bootstrap_admin_password = os.environ.get("BOOTSTRAP_ADMIN_PASSWORD")
    mock_settings.bootstrap_admin_password_file = os.environ.get("BOOTSTRAP_ADMIN_PASSWORD_FILE")

    with patch.object(settings_module, "load_settings", return_value=mock_settings):
        app = create_app()
        return TestClient(app)


@pytest.mark.asyncio
async def test_startup_bootstrap_creates_first_admin_from_env_password(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sync_url, async_url = _upgrade_head(tmp_path, "admin_bootstrap_env_password.db")
    _set_runtime_env(monkeypatch, database_url=async_url)
    _clear_bootstrap_env(monkeypatch)
    monkeypatch.setenv("BOOTSTRAP_ADMIN_EMAIL", "bootstrap-admin@example.org")
    monkeypatch.setenv("BOOTSTRAP_ADMIN_PASSWORD", "bootstrap-password")

    try:
        with _create_runtime_test_client() as client:
            response = client.post(
                "/auth/login",
                json={
                    "email": "bootstrap-admin@example.org",
                    "password": "bootstrap-password",
                },
            )
    finally:
        load_settings.cache_clear()

    assert response.status_code == 200
    assert response.json()["role"] == "admin"

    with sa.create_engine(sync_url).begin() as connection:
        row = connection.execute(
            sa.text(
                "SELECT email, role, is_active FROM users WHERE email = :email LIMIT 1"
            ),
            {"email": "bootstrap-admin@example.org"},
        ).mappings().one()
        count = connection.execute(sa.text("SELECT COUNT(*) AS count FROM users")).mappings().one()

    assert row["email"] == "bootstrap-admin@example.org"
    assert row["role"] == "admin"
    assert bool(row["is_active"]) is True
    assert int(count["count"]) == 1


@pytest.mark.asyncio
async def test_startup_bootstrap_reads_admin_password_from_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, async_url = _upgrade_head(tmp_path, "admin_bootstrap_password_file.db")
    password_file = tmp_path / "bootstrap-password.txt"
    password_file.write_text("bootstrap-from-file\n", encoding="utf-8")
    _set_runtime_env(monkeypatch, database_url=async_url)
    _clear_bootstrap_env(monkeypatch)
    monkeypatch.setenv("BOOTSTRAP_ADMIN_EMAIL", "file-admin@example.org")
    monkeypatch.setenv("BOOTSTRAP_ADMIN_PASSWORD_FILE", str(password_file))

    try:
        with _create_runtime_test_client() as client:
            response = client.post(
                "/auth/login",
                json={
                    "email": "file-admin@example.org",
                    "password": "bootstrap-from-file",
                },
            )
    finally:
        load_settings.cache_clear()

    assert response.status_code == 200
    assert response.json()["role"] == "admin"


@pytest.mark.asyncio
async def test_startup_bootstrap_does_not_create_admin_when_users_exist(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sync_url, async_url = _upgrade_head(tmp_path, "admin_bootstrap_existing_user.db")
    _set_runtime_env(monkeypatch, database_url=async_url)
    _clear_bootstrap_env(monkeypatch)
    monkeypatch.setenv("BOOTSTRAP_ADMIN_EMAIL", "bootstrap-admin@example.org")
    monkeypatch.setenv("BOOTSTRAP_ADMIN_PASSWORD", "bootstrap-password")

    with sa.create_engine(sync_url).begin() as connection:
        _insert_user(connection, email="existing-reader@example.org", role="reader")

    try:
        with _create_runtime_test_client() as client:
            response = client.post(
                "/auth/login",
                json={
                    "email": "bootstrap-admin@example.org",
                    "password": "bootstrap-password",
                },
            )
    finally:
        load_settings.cache_clear()

    assert response.status_code == 401
    assert response.json() == {"detail": "invalid credentials"}

    with sa.create_engine(sync_url).begin() as connection:
        count = connection.execute(sa.text("SELECT COUNT(*) AS count FROM users")).mappings().one()

    assert int(count["count"]) == 1


@pytest.mark.asyncio
async def test_startup_bootstrap_rejects_invalid_password_source_configuration(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, async_url = _upgrade_head(tmp_path, "admin_bootstrap_invalid_config.db")
    password_file = tmp_path / "bootstrap-password.txt"
    password_file.write_text("bootstrap-from-file\n", encoding="utf-8")
    _set_runtime_env(monkeypatch, database_url=async_url)
    _clear_bootstrap_env(monkeypatch)
    monkeypatch.setenv("BOOTSTRAP_ADMIN_EMAIL", "invalid-config@example.org")
    monkeypatch.setenv("BOOTSTRAP_ADMIN_PASSWORD", "bootstrap-password")
    monkeypatch.setenv("BOOTSTRAP_ADMIN_PASSWORD_FILE", str(password_file))

    load_settings.cache_clear()
    try:
        with pytest.raises(
            RuntimeError,
            match="invalid admin bootstrap configuration",
        ):
            create_app()
    finally:
        load_settings.cache_clear()

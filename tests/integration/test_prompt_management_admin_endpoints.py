from __future__ import annotations

import json
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
    expires_at = datetime(2026, 2, 20, 0, 0, 0, tzinfo=UTC)
    connection.execute(
        sa.text(
            "INSERT INTO auth_tokens (user_id, token_hash, expires_at, issued_at) "
            "VALUES (:user_id, :token_hash, :expires_at, :issued_at)"
        ),
        {
            "user_id": user_id.hex,
            "token_hash": token_service.hash_token(token),
            "expires_at": expires_at,
            "issued_at": expires_at - timedelta(hours=1),
        },
    )


def _insert_prompt_template(
    connection: sa.Connection,
    *,
    prompt_name: str,
    version: int,
    content: str,
    is_active: bool,
) -> None:
    connection.execute(
        sa.text(
            "INSERT INTO prompt_templates (id, name, version, content, is_active) "
            "VALUES (:id, :name, :version, :content, :is_active)"
        ),
        {
            "id": uuid4().hex,
            "name": prompt_name,
            "version": version,
            "content": content,
            "is_active": is_active,
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
async def test_admin_lists_prompt_versions_with_active_flags(tmp_path: Path) -> None:
    sync_url, async_url = _upgrade_head(tmp_path, "prompt_management_admin_list_versions.db")
    token_service = OpaqueTokenService()
    admin_id = uuid4()
    admin_token = "admin-prompt-list-token"

    engine = sa.create_engine(sync_url)
    with engine.begin() as connection:
        _insert_user(connection, user_id=admin_id, email="admin@example.org", role="admin")
        _insert_token(
            connection,
            token_service=token_service,
            user_id=admin_id,
            token=admin_token,
        )
        _insert_prompt_template(
            connection,
            prompt_name="llm1_system",
            version=4,
            content="inactive llm1_system v4",
            is_active=False,
        )

    with _build_client(async_url, token_service=token_service) as client:
        response = client.get(
            "/admin/prompts/versions",
            headers={"Authorization": f"Bearer {admin_token}"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["items"][0] == {"name": "llm1_system", "version": 4, "is_active": False}
    assert {"name": "llm1_system", "version": 3, "is_active": True} in payload["items"]


@pytest.mark.asyncio
async def test_admin_gets_active_prompt_version_by_name(tmp_path: Path) -> None:
    sync_url, async_url = _upgrade_head(tmp_path, "prompt_management_admin_get_active.db")
    token_service = OpaqueTokenService()
    admin_id = uuid4()
    admin_token = "admin-prompt-active-token"

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
            "/admin/prompts/llm1_system/active",
            headers={"Authorization": f"Bearer {admin_token}"},
        )

    assert response.status_code == 200
    assert response.json() == {"name": "llm1_system", "version": 3, "is_active": True}


@pytest.mark.asyncio
async def test_admin_activates_prompt_version(tmp_path: Path) -> None:
    sync_url, async_url = _upgrade_head(tmp_path, "prompt_management_admin_activate.db")
    token_service = OpaqueTokenService()
    admin_id = uuid4()
    admin_token = "admin-prompt-activate-token"

    engine = sa.create_engine(sync_url)
    with engine.begin() as connection:
        _insert_user(connection, user_id=admin_id, email="admin@example.org", role="admin")
        _insert_token(
            connection,
            token_service=token_service,
            user_id=admin_id,
            token=admin_token,
        )
        _insert_prompt_template(
            connection,
            prompt_name="llm2_system",
            version=4,
            content="inactive llm2_system v4",
            is_active=False,
        )

    with _build_client(async_url, token_service=token_service) as client:
        response = client.post(
            "/admin/prompts/llm2_system/activate",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"version": 4},
        )

    assert response.status_code == 200
    assert response.json() == {"name": "llm2_system", "version": 4, "is_active": True}

    with sa.create_engine(sync_url).begin() as connection:
        rows = connection.execute(
            sa.text(
                "SELECT version, is_active FROM prompt_templates "
                "WHERE name = :name ORDER BY version"
            ),
            {"name": "llm2_system"},
        ).mappings()
        versions = {int(row["version"]): bool(row["is_active"]) for row in rows}

    assert versions[3] is False
    assert versions[4] is True
    assert sum(1 for is_active in versions.values() if is_active) == 1


@pytest.mark.asyncio
async def test_reader_cannot_activate_prompt_version_and_state_remains_unchanged(
    tmp_path: Path,
) -> None:
    sync_url, async_url = _upgrade_head(tmp_path, "prompt_management_reader_rejected.db")
    token_service = OpaqueTokenService()
    reader_id = uuid4()
    reader_token = "reader-prompt-activate-token"

    engine = sa.create_engine(sync_url)
    with engine.begin() as connection:
        _insert_user(connection, user_id=reader_id, email="reader@example.org", role="reader")
        _insert_token(
            connection,
            token_service=token_service,
            user_id=reader_id,
            token=reader_token,
        )
        _insert_prompt_template(
            connection,
            prompt_name="llm2_user",
            version=4,
            content="inactive llm2_user v4",
            is_active=False,
        )

    with _build_client(async_url, token_service=token_service) as client:
        response = client.post(
            "/admin/prompts/llm2_user/activate",
            headers={"Authorization": f"Bearer {reader_token}"},
            json={"version": 4},
        )

    assert response.status_code == 403
    assert response.json() == {"detail": "admin role required"}

    with sa.create_engine(sync_url).begin() as connection:
        rows = connection.execute(
            sa.text(
                "SELECT version, is_active FROM prompt_templates "
                "WHERE name = :name ORDER BY version"
            ),
            {"name": "llm2_user"},
        ).mappings()
        versions = {int(row["version"]): bool(row["is_active"]) for row in rows}

    assert versions[3] is True
    assert versions[4] is False
    assert sum(1 for is_active in versions.values() if is_active) == 1


@pytest.mark.asyncio
async def test_admin_renders_prompt_management_html_page_with_versions(tmp_path: Path) -> None:
    sync_url, async_url = _upgrade_head(tmp_path, "prompt_management_admin_html_page.db")
    token_service = OpaqueTokenService()
    admin_id = uuid4()
    admin_token = "admin-prompt-html-token"

    engine = sa.create_engine(sync_url)
    with engine.begin() as connection:
        _insert_user(connection, user_id=admin_id, email="admin@example.org", role="admin")
        _insert_token(
            connection,
            token_service=token_service,
            user_id=admin_id,
            token=admin_token,
        )
        _insert_prompt_template(
            connection,
            prompt_name="llm1_system",
            version=4,
            content="inactive llm1_system v4",
            is_active=False,
        )

    with _build_client(async_url, token_service=token_service) as client:
        response = client.get(
            "/admin/prompts",
            headers={"Authorization": f"Bearer {admin_token}"},
        )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "Gestao de Prompts" in response.text
    assert "llm1_system" in response.text
    assert 'href="/admin/prompts/llm1_system/versions/4"' in response.text
    assert 'class="d-flex justify-content-end align-items-center gap-2 flex-wrap"' in response.text
    assert 'action="/admin/prompts/llm1_system/activate-form"' in response.text
    assert 'class="d-inline mb-0"' in response.text
    assert "Sem acao" not in response.text
    assert '<form method="post" action="/logout"' in response.text
    assert 'href="/dashboard/cases"' in response.text
    assert 'href="/admin/prompts"' in response.text


@pytest.mark.asyncio
async def test_admin_renders_prompt_version_content_page(tmp_path: Path) -> None:
    sync_url, async_url = _upgrade_head(tmp_path, "prompt_management_admin_version_content.db")
    token_service = OpaqueTokenService()
    admin_id = uuid4()
    admin_token = "admin-prompt-version-content-token"

    engine = sa.create_engine(sync_url)
    with engine.begin() as connection:
        _insert_user(connection, user_id=admin_id, email="admin@example.org", role="admin")
        _insert_token(
            connection,
            token_service=token_service,
            user_id=admin_id,
            token=admin_token,
        )
        _insert_prompt_template(
            connection,
            prompt_name="llm1_user",
            version=4,
            content="PROMPT V4 CONTENT",
            is_active=False,
        )

    with _build_client(async_url, token_service=token_service) as client:
        response = client.get(
            "/admin/prompts/llm1_user/versions/4",
            headers={"Authorization": f"Bearer {admin_token}"},
        )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "Conteudo do Prompt" in response.text
    assert "llm1_user" in response.text
    assert "PROMPT V4 CONTENT" in response.text
    assert "Criar nova versao" in response.text


@pytest.mark.asyncio
async def test_admin_create_form_inserts_new_prompt_version_and_audits(tmp_path: Path) -> None:
    sync_url, async_url = _upgrade_head(tmp_path, "prompt_management_admin_create_form.db")
    token_service = OpaqueTokenService()
    admin_id = uuid4()
    admin_token = "admin-prompt-create-form-token"

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
            "/admin/prompts/llm2_user/create-form",
            headers={"Authorization": f"Bearer {admin_token}"},
            data={
                "source_version": "3",
                "content": "NOVA VERSAO DERIVADA DA V3",
            },
            follow_redirects=False,
        )

    assert response.status_code == 303
    assert response.headers["location"].startswith("/admin/prompts?")
    assert "created_name=llm2_user" in response.headers["location"]
    assert "created_version=4" in response.headers["location"]

    with sa.create_engine(sync_url).begin() as connection:
        versions_rows = connection.execute(
            sa.text(
                "SELECT version, is_active, content FROM prompt_templates "
                "WHERE name = :name ORDER BY version"
            ),
            {"name": "llm2_user"},
        ).mappings()
        versions = {
            int(row["version"]): {
                "is_active": bool(row["is_active"]),
                "content": str(row["content"]),
            }
            for row in versions_rows
        }
        event_row = connection.execute(
            sa.text(
                "SELECT user_id, event_type, payload, occurred_at "
                "FROM auth_events ORDER BY id DESC LIMIT 1"
            )
        ).mappings().one()

    assert versions[3]["is_active"] is True
    assert versions[4]["is_active"] is False
    assert versions[4]["content"] == "NOVA VERSAO DERIVADA DA V3"
    assert sum(1 for row in versions.values() if row["is_active"]) == 1

    payload = (
        event_row["payload"]
        if isinstance(event_row["payload"], dict)
        else json.loads(str(event_row["payload"]))
    )
    assert event_row["user_id"] in {admin_id, admin_id.hex, str(admin_id)}
    assert event_row["event_type"] == "prompt_version_created"
    assert payload == {
        "action": "create_prompt_version",
        "prompt_name": "llm2_user",
        "source_version": 3,
        "version": 4,
    }
    assert event_row["occurred_at"] is not None


@pytest.mark.asyncio
async def test_admin_activation_form_updates_prompt_version_and_redirects(tmp_path: Path) -> None:
    sync_url, async_url = _upgrade_head(tmp_path, "prompt_management_admin_html_activate.db")
    token_service = OpaqueTokenService()
    admin_id = uuid4()
    admin_token = "admin-prompt-html-activate-token"

    engine = sa.create_engine(sync_url)
    with engine.begin() as connection:
        _insert_user(connection, user_id=admin_id, email="admin@example.org", role="admin")
        _insert_token(
            connection,
            token_service=token_service,
            user_id=admin_id,
            token=admin_token,
        )
        _insert_prompt_template(
            connection,
            prompt_name="llm2_system",
            version=4,
            content="inactive llm2_system v4",
            is_active=False,
        )

    with _build_client(async_url, token_service=token_service) as client:
        response = client.post(
            "/admin/prompts/llm2_system/activate-form",
            headers={"Authorization": f"Bearer {admin_token}"},
            data={"version": "4"},
            follow_redirects=False,
        )

    assert response.status_code == 303
    assert response.headers["location"].startswith("/admin/prompts?")
    assert "activated_name=llm2_system" in response.headers["location"]
    assert "activated_version=4" in response.headers["location"]

    with sa.create_engine(sync_url).begin() as connection:
        rows = connection.execute(
            sa.text(
                "SELECT version, is_active FROM prompt_templates "
                "WHERE name = :name ORDER BY version"
            ),
            {"name": "llm2_system"},
        ).mappings()
        versions = {int(row["version"]): bool(row["is_active"]) for row in rows}

    assert versions[3] is False
    assert versions[4] is True
    assert sum(1 for is_active in versions.values() if is_active) == 1


@pytest.mark.asyncio
async def test_reader_prompt_management_html_is_forbidden_and_does_not_mutate_state(
    tmp_path: Path,
) -> None:
    sync_url, async_url = _upgrade_head(tmp_path, "prompt_management_reader_html_forbidden.db")
    token_service = OpaqueTokenService()
    reader_id = uuid4()
    reader_token = "reader-prompt-html-token"

    engine = sa.create_engine(sync_url)
    with engine.begin() as connection:
        _insert_user(connection, user_id=reader_id, email="reader@example.org", role="reader")
        _insert_token(
            connection,
            token_service=token_service,
            user_id=reader_id,
            token=reader_token,
        )
        _insert_prompt_template(
            connection,
            prompt_name="llm2_user",
            version=4,
            content="inactive llm2_user v4",
            is_active=False,
        )

    with _build_client(async_url, token_service=token_service) as client:
        page_response = client.get(
            "/admin/prompts",
            headers={"Authorization": f"Bearer {reader_token}"},
        )
        activate_response = client.post(
            "/admin/prompts/llm2_user/activate-form",
            headers={"Authorization": f"Bearer {reader_token}"},
            data={"version": "4"},
        )

    assert page_response.status_code == 403
    assert page_response.json() == {"detail": "admin role required"}
    assert activate_response.status_code == 403
    assert activate_response.json() == {"detail": "admin role required"}

    with sa.create_engine(sync_url).begin() as connection:
        rows = connection.execute(
            sa.text(
                "SELECT version, is_active FROM prompt_templates "
                "WHERE name = :name ORDER BY version"
            ),
            {"name": "llm2_user"},
        ).mappings()
        versions = {int(row["version"]): bool(row["is_active"]) for row in rows}

    assert versions[3] is True
    assert versions[4] is False
    assert sum(1 for is_active in versions.values() if is_active) == 1


@pytest.mark.asyncio
async def test_authorization_matrix_reader_read_only_and_admin_prompt_mutation(
    tmp_path: Path,
) -> None:
    sync_url, async_url = _upgrade_head(tmp_path, "prompt_management_authz_matrix.db")
    token_service = OpaqueTokenService()
    reader_id = uuid4()
    reader_token = "reader-authz-matrix-token"
    admin_id = uuid4()
    admin_token = "admin-authz-matrix-token"

    engine = sa.create_engine(sync_url)
    with engine.begin() as connection:
        _insert_user(connection, user_id=reader_id, email="reader@example.org", role="reader")
        _insert_token(
            connection,
            token_service=token_service,
            user_id=reader_id,
            token=reader_token,
        )
        _insert_user(connection, user_id=admin_id, email="admin@example.org", role="admin")
        _insert_token(
            connection,
            token_service=token_service,
            user_id=admin_id,
            token=admin_token,
        )
        _insert_prompt_template(
            connection,
            prompt_name="llm2_system",
            version=4,
            content="inactive llm2_system v4",
            is_active=False,
        )

    with _build_client(async_url, token_service=token_service) as client:
        reader_monitoring = client.get(
            "/monitoring/cases",
            headers={"Authorization": f"Bearer {reader_token}"},
        )
        reader_versions = client.get(
            "/admin/prompts/versions",
            headers={"Authorization": f"Bearer {reader_token}"},
        )
        reader_active = client.get(
            "/admin/prompts/llm2_system/active",
            headers={"Authorization": f"Bearer {reader_token}"},
        )
        reader_activate = client.post(
            "/admin/prompts/llm2_system/activate",
            headers={"Authorization": f"Bearer {reader_token}"},
            json={"version": 4},
        )
        admin_activate = client.post(
            "/admin/prompts/llm2_system/activate",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"version": 4},
        )

    assert reader_monitoring.status_code == 200
    assert reader_versions.status_code == 403
    assert reader_active.status_code == 403
    assert reader_activate.status_code == 403
    assert admin_activate.status_code == 200
    assert admin_activate.json() == {"name": "llm2_system", "version": 4, "is_active": True}

    with sa.create_engine(sync_url).begin() as connection:
        rows = connection.execute(
            sa.text(
                "SELECT version, is_active FROM prompt_templates "
                "WHERE name = :name ORDER BY version"
            ),
            {"name": "llm2_system"},
        ).mappings()
        versions = {int(row["version"]): bool(row["is_active"]) for row in rows}

    assert versions[3] is False
    assert versions[4] is True
    assert sum(1 for is_active in versions.values() if is_active) == 1


@pytest.mark.asyncio
async def test_admin_activation_appends_prompt_audit_event(tmp_path: Path) -> None:
    sync_url, async_url = _upgrade_head(tmp_path, "prompt_management_admin_audit.db")
    token_service = OpaqueTokenService()
    admin_id = uuid4()
    admin_token = "admin-prompt-audit-token"

    engine = sa.create_engine(sync_url)
    with engine.begin() as connection:
        _insert_user(connection, user_id=admin_id, email="admin@example.org", role="admin")
        _insert_token(
            connection,
            token_service=token_service,
            user_id=admin_id,
            token=admin_token,
        )
        _insert_prompt_template(
            connection,
            prompt_name="llm1_user",
            version=4,
            content="inactive llm1_user v4",
            is_active=False,
        )

    with _build_client(async_url, token_service=token_service) as client:
        response = client.post(
            "/admin/prompts/llm1_user/activate",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"version": 4},
        )

    assert response.status_code == 200

    with sa.create_engine(sync_url).begin() as connection:
        event_row = connection.execute(
            sa.text(
                "SELECT user_id, event_type, payload, occurred_at "
                "FROM auth_events ORDER BY id DESC LIMIT 1"
            )
        ).mappings().one()

    payload = (
        event_row["payload"]
        if isinstance(event_row["payload"], dict)
        else json.loads(str(event_row["payload"]))
    )
    assert event_row["user_id"] in {admin_id, admin_id.hex, str(admin_id)}
    assert event_row["event_type"] == "prompt_version_activated"
    assert payload == {
        "action": "activate_prompt_version",
        "prompt_name": "llm1_user",
        "version": 4,
    }
    assert event_row["occurred_at"] is not None


@pytest.mark.asyncio
async def test_admin_form_activation_appends_prompt_audit_event(tmp_path: Path) -> None:
    sync_url, async_url = _upgrade_head(tmp_path, "prompt_management_admin_form_audit.db")
    token_service = OpaqueTokenService()
    admin_id = uuid4()
    admin_token = "admin-prompt-form-audit-token"

    engine = sa.create_engine(sync_url)
    with engine.begin() as connection:
        _insert_user(connection, user_id=admin_id, email="admin@example.org", role="admin")
        _insert_token(
            connection,
            token_service=token_service,
            user_id=admin_id,
            token=admin_token,
        )
        _insert_prompt_template(
            connection,
            prompt_name="llm2_user",
            version=4,
            content="inactive llm2_user v4",
            is_active=False,
        )

    with _build_client(async_url, token_service=token_service) as client:
        response = client.post(
            "/admin/prompts/llm2_user/activate-form",
            headers={"Authorization": f"Bearer {admin_token}"},
            data={"version": "4"},
            follow_redirects=False,
        )

    assert response.status_code == 303

    with sa.create_engine(sync_url).begin() as connection:
        event_row = connection.execute(
            sa.text(
                "SELECT user_id, event_type, payload, occurred_at "
                "FROM auth_events ORDER BY id DESC LIMIT 1"
            )
        ).mappings().one()

    payload = (
        event_row["payload"]
        if isinstance(event_row["payload"], dict)
        else json.loads(str(event_row["payload"]))
    )
    assert event_row["user_id"] in {admin_id, admin_id.hex, str(admin_id)}
    assert event_row["event_type"] == "prompt_version_activated"
    assert payload == {
        "action": "activate_prompt_version",
        "prompt_name": "llm2_user",
        "version": 4,
    }
    assert event_row["occurred_at"] is not None

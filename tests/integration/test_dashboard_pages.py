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


def _insert_case(
    connection: sa.Connection,
    *,
    case_id: UUID,
    status: str,
    updated_at: datetime,
) -> None:
    connection.execute(
        sa.text(
            "INSERT INTO cases ("
            "case_id, status, room1_origin_room_id, room1_origin_event_id, room1_sender_user_id, "
            "created_at, updated_at"
            ") VALUES ("
            ":case_id, :status, '!room1:example.org', :origin_event_id, '@reader:example.org', "
            ":created_at, :updated_at"
            ")"
        ),
        {
            "case_id": case_id.hex,
            "status": status,
            "origin_event_id": f"$origin-{case_id.hex}",
            "created_at": updated_at,
            "updated_at": updated_at,
        },
    )


def _insert_matrix_transcript(
    connection: sa.Connection,
    *,
    case_id: UUID,
    event_id: str,
    captured_at: datetime,
) -> None:
    connection.execute(
        sa.text(
            "INSERT INTO case_matrix_message_transcripts ("
            "case_id, room_id, event_id, sender, message_type, message_text, captured_at"
            ") VALUES ("
            ":case_id, '!room2:example.org', :event_id, '@doctor:example.org', "
            "'room2_doctor_reply', 'ok', :captured_at"
            ")"
        ),
        {
            "case_id": case_id.hex,
            "event_id": event_id,
            "captured_at": captured_at,
        },
    )


@pytest.mark.asyncio
async def test_dashboard_case_list_page_renders_filters_and_paginated_rows_with_unpoly(
    tmp_path: Path,
) -> None:
    sync_url, async_url = _upgrade_head(tmp_path, "dashboard_page_list.db")
    token_service = OpaqueTokenService()
    reader_id = uuid4()
    reader_token = "reader-dashboard-page-token"
    today = datetime.now(tz=UTC)
    case_a = uuid4()
    case_b = uuid4()
    case_c = uuid4()
    filter_date = today.date().isoformat()

    engine = sa.create_engine(sync_url)
    with engine.begin() as connection:
        _insert_user(connection, user_id=reader_id, email="reader@example.org", role="reader")
        _insert_token(
            connection,
            token_service=token_service,
            user_id=reader_id,
            token=reader_token,
        )
        _insert_case(
            connection,
            case_id=case_a,
            status="WAIT_DOCTOR",
            updated_at=today - timedelta(hours=2),
        )
        _insert_case(
            connection,
            case_id=case_b,
            status="WAIT_DOCTOR",
            updated_at=today - timedelta(hours=3),
        )
        _insert_case(
            connection,
            case_id=case_c,
            status="FAILED",
            updated_at=today - timedelta(hours=4),
        )
        _insert_matrix_transcript(
            connection,
            case_id=case_a,
            event_id="$evt-a",
            captured_at=today - timedelta(minutes=10),
        )
        _insert_matrix_transcript(
            connection,
            case_id=case_b,
            event_id="$evt-b",
            captured_at=today - timedelta(minutes=20),
        )
        _insert_matrix_transcript(
            connection,
            case_id=case_c,
            event_id="$evt-c",
            captured_at=today - timedelta(minutes=30),
        )

    with _build_client(async_url, token_service=token_service) as client:
        response = client.get(
            
                "/dashboard/cases?page=1&page_size=2"
                f"&from_date={filter_date}&to_date={filter_date}"
            
        )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "bootstrap@5.3" in response.text
    assert "unpoly.min.js" in response.text
    assert "Dashboard de Monitoramento" in response.text
    assert 'up-target="#cases-list-fragment"' in response.text
    assert str(case_a) in response.text
    assert str(case_b) in response.text
    assert str(case_c) not in response.text
    assert "status" in response.text


@pytest.mark.asyncio
async def test_dashboard_case_list_fragment_update_respects_filters_and_pagination(
    tmp_path: Path,
) -> None:
    sync_url, async_url = _upgrade_head(tmp_path, "dashboard_page_list_fragment.db")
    token_service = OpaqueTokenService()
    reader_id = uuid4()
    reader_token = "reader-dashboard-page-fragment"
    today = datetime.now(tz=UTC)
    filter_date = today.date().isoformat()
    wait_case = uuid4()
    failed_case = uuid4()

    engine = sa.create_engine(sync_url)
    with engine.begin() as connection:
        _insert_user(connection, user_id=reader_id, email="reader@example.org", role="reader")
        _insert_token(
            connection,
            token_service=token_service,
            user_id=reader_id,
            token=reader_token,
        )
        _insert_case(
            connection,
            case_id=wait_case,
            status="WAIT_DOCTOR",
            updated_at=today - timedelta(hours=1),
        )
        _insert_case(
            connection,
            case_id=failed_case,
            status="FAILED",
            updated_at=today - timedelta(hours=2),
        )
        _insert_matrix_transcript(
            connection,
            case_id=wait_case,
            event_id="$evt-wait",
            captured_at=today - timedelta(minutes=5),
        )
        _insert_matrix_transcript(
            connection,
            case_id=failed_case,
            event_id="$evt-failed",
            captured_at=today - timedelta(minutes=6),
        )

    with _build_client(async_url, token_service=token_service) as client:
        response = client.get(
            (
                "/dashboard/cases?page=1&page_size=10&status=WAIT_DOCTOR"
                f"&from_date={filter_date}&to_date={filter_date}"
            ),
            headers={"X-Up-Target": "#cases-list-fragment"},
        )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "<!doctype html>" not in response.text.lower()
    assert 'id="cases-list-fragment"' in response.text
    assert str(wait_case) in response.text
    assert str(failed_case) not in response.text


@pytest.mark.asyncio
async def test_dashboard_case_detail_page_uses_same_base_layout(tmp_path: Path) -> None:
    sync_url, async_url = _upgrade_head(tmp_path, "dashboard_page_detail.db")
    token_service = OpaqueTokenService()
    reader_id = uuid4()
    reader_token = "reader-dashboard-detail-token"
    case_id = uuid4()

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
        response = client.get(f"/dashboard/cases/{case_id}")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "bootstrap@5.3" in response.text
    assert str(case_id) in response.text

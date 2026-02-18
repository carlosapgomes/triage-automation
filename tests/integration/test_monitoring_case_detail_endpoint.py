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
async def test_monitoring_case_detail_returns_unified_chronological_timeline(
    tmp_path: Path,
) -> None:
    sync_url, async_url = _upgrade_head(tmp_path, "monitoring_case_detail.db")
    token_service = OpaqueTokenService()
    reader_id = uuid4()
    reader_token = "reader-detail-token"
    case_id = uuid4()
    base = datetime(2026, 2, 18, 10, 0, 0, tzinfo=UTC)

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
            case_id=case_id,
            status="WAIT_DOCTOR",
            updated_at=base - timedelta(minutes=10),
        )
        connection.execute(
            sa.text(
                "INSERT INTO case_llm_interactions ("
                "case_id, stage, input_payload, output_payload, "
                "prompt_system_name, prompt_system_version, "
                "prompt_user_name, prompt_user_version, model_name, captured_at"
                ") VALUES ("
                ":case_id, 'LLM1', '{\"input\":\"x\"}', '{\"output\":\"y\"}', "
                "'llm1_system', 1, 'llm1_user', 1, 'gpt-4o-mini', :captured_at"
                ")"
            ),
            {
                "case_id": case_id.hex,
                "captured_at": base + timedelta(minutes=10),
            },
        )
        connection.execute(
            sa.text(
                "INSERT INTO case_report_transcripts (case_id, extracted_text, captured_at) "
                "VALUES (:case_id, :extracted_text, :captured_at)"
            ),
            {
                "case_id": case_id.hex,
                "extracted_text": "texto extraido",
                "captured_at": base,
            },
        )
        connection.execute(
            sa.text(
                "INSERT INTO case_matrix_message_transcripts ("
                "case_id, room_id, event_id, sender, message_type, message_text, captured_at"
                ") VALUES ("
                ":case_id, '!room2:example.org', '$evt-1', '@doctor:example.org', "
                "'room2_doctor_reply', 'ok', :captured_at"
                ")"
            ),
            {
                "case_id": case_id.hex,
                "captured_at": base + timedelta(minutes=20),
            },
        )

    with _build_client(async_url, token_service=token_service) as client:
        response = client.get(
            f"/monitoring/cases/{case_id}",
            headers={"Authorization": f"Bearer {reader_token}"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["case_id"] == str(case_id)
    assert payload["status"] == "WAIT_DOCTOR"
    assert [item["source"] for item in payload["timeline"]] == ["pdf", "llm", "matrix"]
    assert [item["event_type"] for item in payload["timeline"]] == [
        "pdf_report_extracted",
        "LLM1",
        "room2_doctor_reply",
    ]


@pytest.mark.asyncio
async def test_monitoring_case_detail_returns_not_found_for_unknown_case(tmp_path: Path) -> None:
    sync_url, async_url = _upgrade_head(tmp_path, "monitoring_case_detail_not_found.db")
    token_service = OpaqueTokenService()
    reader_id = uuid4()
    reader_token = "reader-detail-not-found"
    unknown_case_id = uuid4()

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
            f"/monitoring/cases/{unknown_case_id}",
            headers={"Authorization": f"Bearer {reader_token}"},
        )

    assert response.status_code == 404
    assert response.json() == {"detail": "case not found"}

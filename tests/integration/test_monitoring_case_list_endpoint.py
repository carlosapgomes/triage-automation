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
    expires_at = datetime.now(tz=UTC) + timedelta(days=30)
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


def _insert_case_report_transcript(
    connection: sa.Connection,
    *,
    case_id: UUID,
    captured_at: datetime,
) -> None:
    connection.execute(
        sa.text(
            "INSERT INTO case_report_transcripts (case_id, extracted_text, captured_at) "
            "VALUES (:case_id, :extracted_text, :captured_at)"
        ),
        {
            "case_id": case_id.hex,
            "extracted_text": "texto extraido",
            "captured_at": captured_at,
        },
    )


def _insert_case_llm_interaction(
    connection: sa.Connection,
    *,
    case_id: UUID,
    captured_at: datetime,
) -> None:
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
            "captured_at": captured_at,
        },
    )


def _insert_case_matrix_transcript(
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
async def test_monitoring_case_list_orders_by_latest_activity_with_pagination(
    tmp_path: Path,
) -> None:
    sync_url, async_url = _upgrade_head(tmp_path, "monitoring_case_list_pagination.db")
    token_service = OpaqueTokenService()
    reader_id = uuid4()
    reader_token = "reader-monitor-token"

    case_old = uuid4()
    case_mid = uuid4()
    case_new = uuid4()

    now = datetime(2026, 2, 18, 12, 0, 0, tzinfo=UTC)
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
            case_id=case_old,
            status="FAILED",
            updated_at=now - timedelta(hours=26),
        )
        _insert_case(
            connection,
            case_id=case_mid,
            status="DOCTOR_ACCEPTED",
            updated_at=now - timedelta(hours=3),
        )
        _insert_case(
            connection,
            case_id=case_new,
            status="WAIT_DOCTOR",
            updated_at=now - timedelta(hours=4),
        )
        _insert_case_report_transcript(
            connection,
            case_id=case_old,
            captured_at=now - timedelta(hours=24),
        )
        _insert_case_llm_interaction(
            connection,
            case_id=case_mid,
            captured_at=now - timedelta(hours=1, minutes=30),
        )
        _insert_case_matrix_transcript(
            connection,
            case_id=case_new,
            event_id="$evt-new",
            captured_at=now - timedelta(hours=1),
        )

    with _build_client(async_url, token_service=token_service) as client:
        response = client.get(
            "/monitoring/cases?page=1&page_size=2&from_date=2026-02-17&to_date=2026-02-18",
            headers={"Authorization": f"Bearer {reader_token}"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["page"] == 1
    assert payload["page_size"] == 2
    assert payload["total"] == 3
    assert [entry["case_id"] for entry in payload["items"]] == [str(case_new), str(case_mid)]
    assert payload["items"][0]["status"] == "WAIT_DOCTOR"
    assert payload["items"][1]["status"] == "DOCTOR_ACCEPTED"


@pytest.mark.asyncio
async def test_monitoring_case_list_applies_status_and_period_filters(tmp_path: Path) -> None:
    sync_url, async_url = _upgrade_head(tmp_path, "monitoring_case_list_filters.db")
    token_service = OpaqueTokenService()
    reader_id = uuid4()
    reader_token = "reader-filter-token"

    included_case = uuid4()
    excluded_status_case = uuid4()
    excluded_date_case = uuid4()
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
            case_id=included_case,
            status="WAIT_DOCTOR",
            updated_at=datetime(2026, 2, 18, 8, 0, 0, tzinfo=UTC),
        )
        _insert_case(
            connection,
            case_id=excluded_status_case,
            status="FAILED",
            updated_at=datetime(2026, 2, 18, 9, 0, 0, tzinfo=UTC),
        )
        _insert_case(
            connection,
            case_id=excluded_date_case,
            status="WAIT_DOCTOR",
            updated_at=datetime(2026, 2, 17, 9, 0, 0, tzinfo=UTC),
        )
        _insert_case_matrix_transcript(
            connection,
            case_id=included_case,
            event_id="$evt-included",
            captured_at=datetime(2026, 2, 18, 10, 0, 0, tzinfo=UTC),
        )
        _insert_case_matrix_transcript(
            connection,
            case_id=excluded_status_case,
            event_id="$evt-status",
            captured_at=datetime(2026, 2, 18, 11, 0, 0, tzinfo=UTC),
        )
        _insert_case_matrix_transcript(
            connection,
            case_id=excluded_date_case,
            event_id="$evt-date",
            captured_at=datetime(2026, 2, 17, 11, 0, 0, tzinfo=UTC),
        )

    with _build_client(async_url, token_service=token_service) as client:
        response = client.get(
            (
                "/monitoring/cases?page=1&page_size=10"
                "&status=WAIT_DOCTOR&from_date=2026-02-18&to_date=2026-02-18"
            ),
            headers={"Authorization": f"Bearer {reader_token}"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert len(payload["items"]) == 1
    assert payload["items"][0]["case_id"] == str(included_case)
    assert payload["items"][0]["status"] == "WAIT_DOCTOR"


@pytest.mark.asyncio
async def test_monitoring_case_list_defaults_to_today_filter_and_default_page_size(
    tmp_path: Path,
) -> None:
    sync_url, async_url = _upgrade_head(tmp_path, "monitoring_case_list_defaults.db")
    token_service = OpaqueTokenService()
    reader_id = uuid4()
    reader_token = "reader-defaults-token"

    today_case = uuid4()
    yesterday_case = uuid4()
    now = datetime.now(tz=UTC)
    today = datetime(now.year, now.month, now.day, 9, 0, 0, tzinfo=UTC)
    yesterday = today - timedelta(days=1)
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
            case_id=today_case,
            status="WAIT_DOCTOR",
            updated_at=today,
        )
        _insert_case(
            connection,
            case_id=yesterday_case,
            status="WAIT_DOCTOR",
            updated_at=yesterday,
        )
        _insert_case_report_transcript(
            connection,
            case_id=today_case,
            captured_at=today + timedelta(hours=2),
        )
        _insert_case_report_transcript(
            connection,
            case_id=yesterday_case,
            captured_at=yesterday + timedelta(hours=2),
        )

    with _build_client(async_url, token_service=token_service) as client:
        response = client.get(
            "/monitoring/cases",
            headers={"Authorization": f"Bearer {reader_token}"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["page"] == 1
    assert payload["page_size"] == 10
    assert payload["total"] == 1
    assert [entry["case_id"] for entry in payload["items"]] == [str(today_case)]

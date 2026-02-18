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
    agency_record_number: str | None = None,
    structured_data_json: dict[str, object] | None = None,
) -> None:
    connection.execute(
        sa.text(
            "INSERT INTO cases ("
            "case_id, status, room1_origin_room_id, room1_origin_event_id, room1_sender_user_id, "
            "agency_record_number, structured_data_json, created_at, updated_at"
            ") VALUES ("
            ":case_id, :status, '!room1:example.org', :origin_event_id, '@reader:example.org', "
            ":agency_record_number, :structured_data_json, :created_at, :updated_at"
            ")"
        ),
        {
            "case_id": case_id.hex,
            "status": status,
            "origin_event_id": f"$origin-{case_id.hex}",
            "agency_record_number": agency_record_number,
            "structured_data_json": (
                json.dumps(structured_data_json, ensure_ascii=False)
                if structured_data_json is not None
                else None
            ),
            "created_at": updated_at,
            "updated_at": updated_at,
        },
    )


def _insert_matrix_transcript(
    connection: sa.Connection,
    *,
    case_id: UUID,
    room_id: str = "!room2:example.org",
    event_id: str,
    sender: str = "@doctor:example.org",
    message_type: str = "room2_doctor_reply",
    message_text: str = "ok",
    captured_at: datetime,
) -> None:
    connection.execute(
        sa.text(
            "INSERT INTO case_matrix_message_transcripts ("
            "case_id, room_id, event_id, sender, message_type, message_text, captured_at"
            ") VALUES ("
            ":case_id, :room_id, :event_id, :sender, :message_type, :message_text, :captured_at"
            ")"
        ),
        {
            "case_id": case_id.hex,
            "room_id": room_id,
            "event_id": event_id,
            "sender": sender,
            "message_type": message_type,
            "message_text": message_text,
            "captured_at": captured_at,
        },
    )


def _insert_report_transcript(
    connection: sa.Connection,
    *,
    case_id: UUID,
    extracted_text: str,
    captured_at: datetime,
) -> None:
    connection.execute(
        sa.text(
            "INSERT INTO case_report_transcripts (case_id, extracted_text, captured_at) "
            "VALUES (:case_id, :extracted_text, :captured_at)"
        ),
        {
            "case_id": case_id.hex,
            "extracted_text": extracted_text,
            "captured_at": captured_at,
        },
    )


def _insert_case_event(
    connection: sa.Connection,
    *,
    case_id: UUID,
    ts: datetime,
    event_type: str,
    actor_type: str,
    actor_user_id: str | None = None,
    room_id: str | None = None,
    payload: dict[str, object] | None = None,
) -> None:
    connection.execute(
        sa.text(
            "INSERT INTO case_events ("
            "case_id, ts, actor_type, actor_user_id, room_id, event_type, payload"
            ") VALUES ("
            ":case_id, :ts, :actor_type, :actor_user_id, :room_id, :event_type, :payload"
            ")"
        ),
        {
            "case_id": case_id.hex,
            "ts": ts,
            "actor_type": actor_type,
            "actor_user_id": actor_user_id,
            "room_id": room_id,
            "event_type": event_type,
            "payload": json.dumps(payload, ensure_ascii=False) if payload is not None else "{}",
        },
    )


def _insert_llm_interaction(
    connection: sa.Connection,
    *,
    case_id: UUID,
    stage: str,
    captured_at: datetime,
) -> None:
    connection.execute(
        sa.text(
            "INSERT INTO case_llm_interactions ("
            "case_id, stage, input_payload, output_payload, "
            "prompt_system_name, prompt_system_version, "
            "prompt_user_name, prompt_user_version, model_name, captured_at"
            ") VALUES ("
            ":case_id, :stage, '{\"input\":\"x\"}', '{\"output\":\"y\"}', "
            "'llm_system', 1, 'llm_user', 1, 'gpt-4o-mini', :captured_at"
            ")"
        ),
        {
            "case_id": case_id.hex,
            "stage": stage,
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
            f"&from_date={filter_date}&to_date={filter_date}",
            headers={"Authorization": f"Bearer {reader_token}"},
        )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "bootstrap@5.3" in response.text
    assert "unpoly.min.js" in response.text
    assert "hospital-shell" in response.text
    assert "--hospital-primary" in response.text
    assert "Dashboard de Monitoramento" in response.text
    assert 'up-target="#cases-list-fragment"' in response.text
    assert str(case_a) in response.text
    assert str(case_b) in response.text
    assert str(case_c) not in response.text
    assert "status" in response.text


@pytest.mark.asyncio
async def test_dashboard_case_list_prefers_patient_name_and_record_number_identifier(
    tmp_path: Path,
) -> None:
    sync_url, async_url = _upgrade_head(tmp_path, "dashboard_page_patient_identifier.db")
    token_service = OpaqueTokenService()
    reader_id = uuid4()
    reader_token = "reader-dashboard-patient-id-token"
    now = datetime.now(tz=UTC)
    case_id = uuid4()
    filter_date = now.date().isoformat()

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
            updated_at=now - timedelta(minutes=20),
            agency_record_number="123456",
            structured_data_json={
                "patient": {
                    "name": "Maria Souza",
                    "age": 54,
                }
            },
        )
        _insert_matrix_transcript(
            connection,
            case_id=case_id,
            event_id="$evt-patient-id",
            captured_at=now - timedelta(minutes=5),
        )

    with _build_client(async_url, token_service=token_service) as client:
        response = client.get(
            "/dashboard/cases"
            f"?from_date={filter_date}&to_date={filter_date}",
            headers={"Authorization": f"Bearer {reader_token}"},
        )

    assert response.status_code == 200
    assert "Maria Souza · 123456" in response.text
    assert f'href="/dashboard/cases/{case_id}"' in response.text


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
            headers={
                "Authorization": f"Bearer {reader_token}",
                "X-Up-Target": "#cases-list-fragment",
            },
        )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "<!doctype html>" not in response.text.lower()
    assert 'id="cases-list-fragment"' in response.text
    assert str(wait_case) in response.text
    assert str(failed_case) not in response.text


@pytest.mark.asyncio
async def test_dashboard_case_list_requires_bearer_token(tmp_path: Path) -> None:
    _, async_url = _upgrade_head(tmp_path, "dashboard_page_list_auth_required.db")

    with _build_client(async_url, token_service=OpaqueTokenService()) as client:
        response = client.get("/dashboard/cases", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/login"


@pytest.mark.asyncio
async def test_dashboard_case_list_accepts_blank_status_query_parameter(tmp_path: Path) -> None:
    sync_url, async_url = _upgrade_head(tmp_path, "dashboard_page_list_blank_status.db")
    token_service = OpaqueTokenService()
    reader_id = uuid4()
    reader_token = "reader-dashboard-blank-status"
    now = datetime.now(tz=UTC)
    case_id = uuid4()
    filter_date = now.date().isoformat()

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
            updated_at=now - timedelta(minutes=15),
        )
        _insert_matrix_transcript(
            connection,
            case_id=case_id,
            event_id="$evt-blank-status",
            captured_at=now - timedelta(minutes=5),
        )

    with _build_client(async_url, token_service=token_service) as client:
        response = client.get(
            "/dashboard/cases"
            f"?status=&from_date={filter_date}&to_date={filter_date}",
            headers={"Authorization": f"Bearer {reader_token}"},
        )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert str(case_id) in response.text


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("role", "token"),
    [
        ("reader", "reader-dashboard-access"),
        ("admin", "admin-dashboard-access"),
    ],
)
async def test_dashboard_case_list_accepts_reader_and_admin_roles(
    tmp_path: Path,
    role: str,
    token: str,
) -> None:
    sync_url, async_url = _upgrade_head(tmp_path, f"dashboard_page_list_auth_{role}.db")
    token_service = OpaqueTokenService()
    user_id = uuid4()
    case_id = uuid4()
    now = datetime.now(tz=UTC)

    engine = sa.create_engine(sync_url)
    with engine.begin() as connection:
        _insert_user(
            connection,
            user_id=user_id,
            email=f"{role}@example.org",
            role=role,
        )
        _insert_token(
            connection,
            token_service=token_service,
            user_id=user_id,
            token=token,
        )
        _insert_case(
            connection,
            case_id=case_id,
            status="WAIT_DOCTOR",
            updated_at=now - timedelta(minutes=20),
        )
        _insert_matrix_transcript(
            connection,
            case_id=case_id,
            event_id=f"$evt-{role}",
            captured_at=now - timedelta(minutes=5),
        )

    filter_date = now.date().isoformat()
    with _build_client(async_url, token_service=token_service) as client:
        response = client.get(
            "/dashboard/cases"
            f"?from_date={filter_date}&to_date={filter_date}",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 200
    assert str(case_id) in response.text


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("role", "token", "shows_prompt_nav"),
    [
        ("reader", "reader-dashboard-shell-nav", False),
        ("admin", "admin-dashboard-shell-nav", True),
    ],
)
async def test_dashboard_shell_navigation_is_role_aware(
    tmp_path: Path,
    role: str,
    token: str,
    shows_prompt_nav: bool,
) -> None:
    sync_url, async_url = _upgrade_head(tmp_path, f"dashboard_shell_nav_{role}.db")
    token_service = OpaqueTokenService()
    user_id = uuid4()

    engine = sa.create_engine(sync_url)
    with engine.begin() as connection:
        _insert_user(
            connection,
            user_id=user_id,
            email=f"{role}@example.org",
            role=role,
        )
        _insert_token(
            connection,
            token_service=token_service,
            user_id=user_id,
            token=token,
        )

    with _build_client(async_url, token_service=token_service) as client:
        response = client.get(
            "/dashboard/cases",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 200
    assert '<form method="post" action="/logout"' in response.text
    assert 'href="/dashboard/cases"' in response.text
    if shows_prompt_nav:
        assert 'href="/admin/prompts"' in response.text
    else:
        assert 'href="/admin/prompts"' not in response.text


@pytest.mark.asyncio
async def test_dashboard_list_and_detail_reuse_shared_shell_layout(tmp_path: Path) -> None:
    sync_url, async_url = _upgrade_head(tmp_path, "dashboard_shell_layout_reuse.db")
    token_service = OpaqueTokenService()
    admin_id = uuid4()
    admin_token = "admin-dashboard-shell-layout-token"
    case_id = uuid4()
    base = datetime(2026, 2, 18, 12, 0, 0, tzinfo=UTC)

    engine = sa.create_engine(sync_url)
    with engine.begin() as connection:
        _insert_user(connection, user_id=admin_id, email="admin@example.org", role="admin")
        _insert_token(
            connection,
            token_service=token_service,
            user_id=admin_id,
            token=admin_token,
        )
        _insert_case(
            connection,
            case_id=case_id,
            status="WAIT_DOCTOR",
            updated_at=base - timedelta(minutes=10),
        )

    with _build_client(async_url, token_service=token_service) as client:
        list_response = client.get(
            "/dashboard/cases",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        detail_response = client.get(
            f"/dashboard/cases/{case_id}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )

    assert list_response.status_code == 200
    assert detail_response.status_code == 200
    assert '<header class="app-header' in list_response.text
    assert '<header class="app-header' in detail_response.text
    assert '<form method="post" action="/logout"' in list_response.text
    assert '<form method="post" action="/logout"' in detail_response.text
    assert 'href="/dashboard/cases"' in list_response.text
    assert 'href="/dashboard/cases"' in detail_response.text
    assert 'href="/admin/prompts"' in detail_response.text
    assert "Detalhe do Caso" in detail_response.text


@pytest.mark.asyncio
async def test_dashboard_case_detail_page_renders_timeline_and_full_content_toggle_for_admin(
    tmp_path: Path,
) -> None:
    sync_url, async_url = _upgrade_head(tmp_path, "dashboard_page_detail.db")
    token_service = OpaqueTokenService()
    admin_id = uuid4()
    admin_token = "admin-dashboard-detail-token"
    case_id = uuid4()
    base = datetime(2026, 2, 18, 10, 0, 0, tzinfo=UTC)
    long_pdf_text = ("trecho " * 40) + "SEGREDO_FULL_ADMIN_ONLY_123"

    engine = sa.create_engine(sync_url)
    with engine.begin() as connection:
        _insert_user(connection, user_id=admin_id, email="admin@example.org", role="admin")
        _insert_token(
            connection,
            token_service=token_service,
            user_id=admin_id,
            token=admin_token,
        )
        _insert_case(
            connection,
            case_id=case_id,
            status="WAIT_DOCTOR",
            updated_at=base - timedelta(minutes=15),
        )
        _insert_report_transcript(
            connection,
            case_id=case_id,
            extracted_text=long_pdf_text,
            captured_at=base,
        )
        _insert_matrix_transcript(
            connection,
            case_id=case_id,
            room_id="!room1:example.org",
            event_id="$evt-ack",
            sender="bot",
            message_type="bot_processing",
            message_text="processando...",
            captured_at=base + timedelta(minutes=5),
        )
        _insert_llm_interaction(
            connection,
            case_id=case_id,
            stage="LLM1",
            captured_at=base + timedelta(minutes=10),
        )
        _insert_matrix_transcript(
            connection,
            case_id=case_id,
            room_id="!room2:example.org",
            event_id="$evt-reply",
            sender="@doctor:example.org",
            message_type="room2_doctor_reply",
            message_text="decisao: aceitar",
            captured_at=base + timedelta(minutes=15),
        )

    with _build_client(async_url, token_service=token_service) as client:
        response = client.get(
            f"/dashboard/cases/{case_id}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "bootstrap@5.3" in response.text
    assert "hospital-shell" in response.text
    assert "--hospital-primary" in response.text
    assert str(case_id) in response.text
    assert 'id="case-timeline"' in response.text
    assert "pdf_report_extracted" in response.text
    assert "bot_processing" in response.text
    assert "LLM1" in response.text
    assert "room2_doctor_reply" in response.text
    assert "badge text-bg-secondary" in response.text
    assert "badge text-bg-info" in response.text
    assert "badge text-bg-warning" in response.text
    assert "badge text-bg-primary" in response.text
    assert "SEGREDO_FULL_ADMIN_ONLY_123" in response.text
    assert "data-toggle-full" in response.text
    assert "document.addEventListener(\"click\"" in response.text

    html = response.text
    assert html.index("pdf_report_extracted") < html.index("bot_processing")
    assert html.index("bot_processing") < html.index("LLM1")
    assert html.index("LLM1") < html.index("room2_doctor_reply")


@pytest.mark.asyncio
async def test_dashboard_case_detail_page_shows_excerpt_only_for_reader(tmp_path: Path) -> None:
    sync_url, async_url = _upgrade_head(tmp_path, "dashboard_page_detail_reader_excerpt.db")
    token_service = OpaqueTokenService()
    reader_id = uuid4()
    reader_token = "reader-dashboard-detail-token"
    case_id = uuid4()
    base = datetime(2026, 2, 18, 11, 0, 0, tzinfo=UTC)
    long_pdf_text = ("trecho " * 40) + "SEGREDO_FULL_ADMIN_ONLY_123"

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
        _insert_report_transcript(
            connection,
            case_id=case_id,
            extracted_text=long_pdf_text,
            captured_at=base,
        )

    with _build_client(async_url, token_service=token_service) as client:
        response = client.get(
            f"/dashboard/cases/{case_id}",
            headers={"Authorization": f"Bearer {reader_token}"},
        )

    assert response.status_code == 200
    assert "SEGREDO_FULL_ADMIN_ONLY_123" not in response.text
    assert "data-toggle-full=" not in response.text
    assert "trecho" in response.text


@pytest.mark.asyncio
async def test_dashboard_case_detail_falls_back_to_legacy_case_events_timeline(
    tmp_path: Path,
) -> None:
    sync_url, async_url = _upgrade_head(tmp_path, "dashboard_page_detail_legacy_events.db")
    token_service = OpaqueTokenService()
    reader_id = uuid4()
    reader_token = "reader-dashboard-detail-legacy-events"
    case_id = uuid4()
    base = datetime(2026, 2, 18, 14, 0, 0, tzinfo=UTC)

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
            status="CLEANED",
            updated_at=base + timedelta(minutes=4),
        )
        _insert_case_event(
            connection,
            case_id=case_id,
            ts=base,
            event_type="CASE_CREATED",
            actor_type="system",
            payload={"origin": "legacy"},
        )
        _insert_case_event(
            connection,
            case_id=case_id,
            ts=base + timedelta(minutes=3),
            event_type="ROOM2_DOCTOR_REPLY",
            actor_type="user",
            actor_user_id="@doctor:example.org",
            room_id="!room2:example.org",
            payload={"decision": "accept"},
        )

    with _build_client(async_url, token_service=token_service) as client:
        response = client.get(
            f"/dashboard/cases/{case_id}",
            headers={"Authorization": f"Bearer {reader_token}"},
        )

    assert response.status_code == 200
    assert "CASE_CREATED" in response.text
    assert "ROOM2_DOCTOR_REPLY" in response.text
    assert "@doctor:example.org" in response.text
    assert "!room2:example.org" in response.text

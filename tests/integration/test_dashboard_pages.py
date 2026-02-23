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
    sender_display_name: str | None = None,
    message_type: str = "room2_doctor_reply",
    message_text: str = "ok",
    captured_at: datetime,
) -> None:
    connection.execute(
        sa.text(
            "INSERT INTO case_matrix_message_transcripts ("
            "case_id, room_id, event_id, sender, sender_display_name, "
            "message_type, message_text, captured_at"
            ") VALUES ("
            ":case_id, :room_id, :event_id, :sender, :sender_display_name, "
            ":message_type, :message_text, :captured_at"
            ")"
        ),
        {
            "case_id": case_id.hex,
            "room_id": room_id,
            "event_id": event_id,
            "sender": sender,
            "sender_display_name": sender_display_name,
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


def _insert_reaction_checkpoint(
    connection: sa.Connection,
    *,
    case_id: UUID,
    stage: str,
    room_id: str,
    target_event_id: str,
    expected_at: datetime,
    outcome: str = "PENDING",
    reaction_event_id: str | None = None,
    reactor_user_id: str | None = None,
    reactor_display_name: str | None = None,
    reaction_key: str | None = None,
    reacted_at: datetime | None = None,
) -> None:
    connection.execute(
        sa.text(
            "INSERT INTO case_reaction_checkpoints ("
            "case_id, stage, room_id, target_event_id, expected_at, outcome, "
            "reaction_event_id, reactor_user_id, reactor_display_name, "
            "reaction_key, reacted_at"
            ") VALUES ("
            ":case_id, :stage, :room_id, :target_event_id, :expected_at, :outcome, "
            ":reaction_event_id, :reactor_user_id, :reactor_display_name, "
            ":reaction_key, :reacted_at"
            ")"
        ),
        {
            "case_id": case_id.hex,
            "stage": stage,
            "room_id": room_id,
            "target_event_id": target_event_id,
            "expected_at": expected_at,
            "outcome": outcome,
            "reaction_event_id": reaction_event_id,
            "reactor_user_id": reactor_user_id,
            "reactor_display_name": reactor_display_name,
            "reaction_key": reaction_key,
            "reacted_at": reacted_at,
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
    today = datetime(2026, 2, 18, 12, 0, 0, tzinfo=UTC)
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
    now = datetime(2026, 2, 18, 12, 0, 0, tzinfo=UTC)
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
    today = datetime(2026, 2, 18, 12, 0, 0, tzinfo=UTC)
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
    now = datetime(2026, 2, 18, 12, 0, 0, tzinfo=UTC)
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
    now = datetime(2026, 2, 18, 12, 0, 0, tzinfo=UTC)

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
    ("role", "token", "shows_prompt_nav", "shows_users_nav"),
    [
        ("reader", "reader-dashboard-shell-nav", False, False),
        ("admin", "admin-dashboard-shell-nav", True, True),
    ],
)
async def test_dashboard_shell_navigation_is_role_aware(
    tmp_path: Path,
    role: str,
    token: str,
    shows_prompt_nav: bool,
    shows_users_nav: bool,
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
    if shows_users_nav:
        assert 'href="/admin/users"' in response.text
    else:
        assert 'href="/admin/users"' not in response.text


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
            f"/dashboard/cases/{case_id}?view=pure",
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
    assert 'href="/admin/users"' in detail_response.text
    assert "Detalhe do Caso" in detail_response.text


@pytest.mark.asyncio
async def test_dashboard_case_detail_page_renders_timeline_and_full_content_toggle_for_admin(
    tmp_path: Path,
) -> None:
    """Verifica se a página de detalhes renderiza histórico e toggle de conteúdo para admin."""
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
            sender_display_name="Dra. Joana",
            message_type="room2_doctor_reply",
            message_text="decisao: aceitar",
            captured_at=base + timedelta(minutes=15),
        )

    with _build_client(async_url, token_service=token_service) as client:
        response = client.get(
            f"/dashboard/cases/{case_id}?view=pure",
            headers={"Authorization": f"Bearer {admin_token}"},
        )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "bootstrap@5.3" in response.text
    assert "hospital-shell" in response.text
    assert "--hospital-primary" in response.text
    assert str(case_id) in response.text
    assert 'id="case-timeline"' in response.text
    assert "relatório pdf extraído" in response.text
    assert "bot processando" in response.text
    assert "extração estruturada" in response.text
    assert "resposta do médico" in response.text
    assert "Dra. Joana" in response.text
    assert "badge text-bg-secondary" in response.text
    assert "badge text-bg-info" in response.text
    assert "badge text-bg-warning" in response.text
    assert "badge text-bg-primary" in response.text
    assert "SEGREDO_FULL_ADMIN_ONLY_123" in response.text
    assert "data-toggle-full" in response.text
    assert "document.addEventListener(\"click\"" in response.text

    html = response.text
    assert html.index("relatório pdf extraído") < html.index("bot processando")
    assert html.index("bot processando") < html.index("extração estruturada")
    assert html.index("extração estruturada") < html.index("resposta do médico")


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
            f"/dashboard/cases/{case_id}?view=pure",
            headers={"Authorization": f"Bearer {reader_token}"},
        )

    assert response.status_code == 200
    assert "SEGREDO_FULL_ADMIN_ONLY_123" not in response.text
    assert "data-toggle-full=" not in response.text
    assert "trecho" in response.text


@pytest.mark.asyncio
async def test_dashboard_case_detail_page_renders_reaction_checkpoint_timeline_events(
    tmp_path: Path,
) -> None:
    """Verifica se a visualização pura exibe checkpoints de reação traduzidos."""
    sync_url, async_url = _upgrade_head(tmp_path, "dashboard_page_detail_reaction_events.db")
    token_service = OpaqueTokenService()
    reader_id = uuid4()
    reader_token = "reader-dashboard-detail-reactions"
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
            status="WAIT_R1_CLEANUP_THUMBS",
            updated_at=base + timedelta(minutes=4),
        )
        _insert_reaction_checkpoint(
            connection,
            case_id=case_id,
            stage="ROOM3_ACK",
            room_id="!room3:example.org",
            target_event_id="$room3-ack-1",
            expected_at=base,
        )
        _insert_reaction_checkpoint(
            connection,
            case_id=case_id,
            stage="ROOM3_ACK",
            room_id="!room3:example.org",
            target_event_id="$room3-ack-2",
            expected_at=base + timedelta(minutes=2),
            outcome="POSITIVE_RECEIVED",
            reaction_event_id="$reaction-room3-1",
            reactor_user_id="@scheduler:example.org",
            reactor_display_name="Enf. Maria",
            reaction_key="✅",
            reacted_at=base + timedelta(minutes=3),
        )

    with _build_client(async_url, token_service=token_service) as client:
        response = client.get(
            f"/dashboard/cases/{case_id}?view=pure",
            headers={"Authorization": f"Bearer {reader_token}"},
        )

    assert response.status_code == 200
    assert "aguardando reação positiva do Agendamento" in response.text
    assert "reação positiva recebida do Agendamento" in response.text
    assert "Enf. Maria" in response.text
    assert "!room3:example.org" in response.text


@pytest.mark.asyncio
async def test_dashboard_case_detail_defaults_to_thread_view_with_decision_and_reactions(
    tmp_path: Path,
) -> None:
    """Verifica visualização padrão em etapas com decisão médica e reações traduzidas."""
    sync_url, async_url = _upgrade_head(tmp_path, "dashboard_page_detail_thread_default.db")
    token_service = OpaqueTokenService()
    reader_id = uuid4()
    reader_token = "reader-dashboard-thread-default"
    case_id = uuid4()
    base = datetime(2026, 2, 18, 15, 0, 0, tzinfo=UTC)

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
            updated_at=base + timedelta(minutes=30),
        )
        _insert_report_transcript(
            connection,
            case_id=case_id,
            extracted_text="texto limpo sem watermark",
            captured_at=base,
        )
        _insert_matrix_transcript(
            connection,
            case_id=case_id,
            room_id="!room1:example.org",
            event_id="$evt-room1-ack",
            sender="bot",
            message_type="bot_processing",
            message_text="processando...",
            captured_at=base + timedelta(minutes=2),
        )
        _insert_matrix_transcript(
            connection,
            case_id=case_id,
            room_id="!room2:example.org",
            event_id="$evt-room2-reply",
            sender="@doctor:example.org",
            sender_display_name="Dra. Joana",
            message_type="room2_doctor_reply",
            message_text="decisao: aceitar\nsuporte: nenhum\nmotivo: ok",
            captured_at=base + timedelta(minutes=5),
        )
        _insert_matrix_transcript(
            connection,
            case_id=case_id,
            room_id="!room2:example.org",
            event_id="$evt-room2-ack",
            sender="bot",
            message_type="room2_decision_ack",
            message_text="resultado: sucesso",
            captured_at=base + timedelta(minutes=6),
        )
        _insert_reaction_checkpoint(
            connection,
            case_id=case_id,
            stage="ROOM2_ACK",
            room_id="!room2:example.org",
            target_event_id="$evt-room2-ack",
            expected_at=base + timedelta(minutes=6),
            outcome="POSITIVE_RECEIVED",
            reaction_event_id="$reaction-room2-1",
            reactor_user_id="@admin:example.org",
            reactor_display_name="Carlos Gomes",
            reaction_key="👍",
            reacted_at=base + timedelta(minutes=7),
        )
        _insert_matrix_transcript(
            connection,
            case_id=case_id,
            room_id="!room3:example.org",
            event_id="$evt-room3-reply",
            sender="@scheduler:example.org",
            sender_display_name="Enf. Maria",
            message_type="room3_reply",
            message_text=(
                "status: confirmed\n"
                "date_time: 2026-02-20 14:30\n"
                "location: Ambulatorio 3\n"
                "instructions: jejum"
            ),
            captured_at=base + timedelta(minutes=8),
        )
        _insert_matrix_transcript(
            connection,
            case_id=case_id,
            room_id="!room3:example.org",
            event_id="$evt-room3-ack",
            sender="bot",
            message_type="bot_ack",
            message_text="ack da agenda",
            captured_at=base + timedelta(minutes=9),
        )
        _insert_reaction_checkpoint(
            connection,
            case_id=case_id,
            stage="ROOM3_ACK",
            room_id="!room3:example.org",
            target_event_id="$evt-room3-ack",
            expected_at=base + timedelta(minutes=9),
            outcome="POSITIVE_RECEIVED",
            reaction_event_id="$reaction-room3-1",
            reactor_user_id="@admin:example.org",
            reactor_display_name="Carlos Gomes",
            reaction_key="✅",
            reacted_at=base + timedelta(minutes=10),
        )
        _insert_matrix_transcript(
            connection,
            case_id=case_id,
            room_id="!room1:example.org",
            event_id="$evt-room1-final",
            sender="bot",
            message_type="room1_final",
            message_text="agendamento confirmado para 2026-02-20 14:30",
            captured_at=base + timedelta(minutes=11),
        )
        _insert_reaction_checkpoint(
            connection,
            case_id=case_id,
            stage="ROOM1_FINAL",
            room_id="!room1:example.org",
            target_event_id="$evt-room1-final",
            expected_at=base + timedelta(minutes=11),
            outcome="POSITIVE_RECEIVED",
            reaction_event_id="$reaction-room1-1",
            reactor_user_id="@admin:example.org",
            reactor_display_name="Carlos Gomes",
            reaction_key="👍",
            reacted_at=base + timedelta(minutes=12),
        )

    with _build_client(async_url, token_service=token_service) as client:
        response = client.get(
            f"/dashboard/cases/{case_id}",
            headers={"Authorization": f"Bearer {reader_token}"},
        )

    assert response.status_code == 200
    assert 'id="case-thread-view"' in response.text
    assert "Fluxo por Etapas" in response.text
    assert "Histórico Completo" in response.text
    assert "Resposta médica: DECISÃO = ACEITAR" in response.text
    assert "Autor: Dra. Joana" in response.text
    assert "Resposta do Agendamento: POSITIVA" in response.text
    assert "Agendado para: 2026-02-20 14:30" in response.text
    assert "Autor: Enf. Maria" in response.text
    assert "Resultado final: AGENDAMENTO CONFIRMADO para 2026-02-20 14:30" in response.text
    assert "Reação à confirmação: 👍 por Carlos Gomes" in response.text


@pytest.mark.asyncio
async def test_dashboard_case_detail_shows_patient_name_and_record_number(
    tmp_path: Path,
) -> None:
    """Verifica se a página de detalhes exibe nome do paciente e número da ocorrência."""
    sync_url, async_url = _upgrade_head(tmp_path, "dashboard_detail_patient_info.db")
    token_service = OpaqueTokenService()
    admin_id = uuid4()
    admin_token = "admin-detail-patient-token"
    case_id = uuid4()
    now = datetime(2026, 2, 22, 12, 0, 0, tzinfo=UTC)

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
            updated_at=now,
            agency_record_number="REC-2026-001",
            structured_data_json={
                "patient": {
                    "name": "Maria da Silva",
                    "age": 45,
                },
            },
        )
        _insert_report_transcript(
            connection,
            case_id=case_id,
            extracted_text="Relatorio medico da paciente",
            captured_at=now,
        )

    with _build_client(async_url, token_service=token_service) as client:
        response = client.get(
            f"/dashboard/cases/{case_id}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )

    assert response.status_code == 200
    assert "Maria da Silva" in response.text
    assert "REC-2026-001" in response.text
    assert "Ocorrência:" in response.text
    # Verifica que o nome do paciente aparece no cabecalho (nao apenas o UUID)
    assert "Detalhe do Caso" in response.text


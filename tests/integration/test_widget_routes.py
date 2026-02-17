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
from triage_automation.application.ports.case_repository_port import CaseCreateInput
from triage_automation.application.services.auth_service import AuthService
from triage_automation.application.services.handle_doctor_decision_service import (
    HandleDoctorDecisionService,
)
from triage_automation.domain.case_status import CaseStatus
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
BOOTSTRAP_PATH = "/widget/room2/bootstrap"
SUBMIT_PATH = "/widget/room2/submit"


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


def _insert_token(
    connection: sa.Connection,
    *,
    user_id: UUID,
    token_hash: str,
    expires_at: datetime,
) -> None:
    connection.execute(
        sa.text(
            "INSERT INTO auth_tokens (user_id, token_hash, expires_at) "
            "VALUES (:user_id, :token_hash, :expires_at)"
        ),
        {
            "user_id": user_id.hex,
            "token_hash": token_hash,
            "expires_at": expires_at,
        },
    )


async def _create_case(async_url: str, *, status: CaseStatus, event_id: str) -> UUID:
    session_factory = create_session_factory(async_url)
    case_repo = SqlAlchemyCaseRepository(session_factory)
    created = await case_repo.create_case(
        CaseCreateInput(
            case_id=uuid4(),
            status=status,
            room1_origin_room_id="!room1:example.org",
            room1_origin_event_id=event_id,
            room1_sender_user_id="@human:example.org",
        )
    )
    return created.case_id


def _build_client(async_url: str) -> TestClient:
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

    app = create_app(
        webhook_hmac_secret=SECRET,
        decision_service=decision_service,
        auth_service=auth_service,
        auth_token_repository=SqlAlchemyAuthTokenRepository(session_factory),
        database_url=async_url,
    )
    return TestClient(app)


def _auth_header(token: str) -> dict[str, str]:
    return {"authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_bootstrap_returns_case_context_for_authenticated_admin(tmp_path: Path) -> None:
    sync_url, async_url = _upgrade_head(tmp_path, "widget_bootstrap_admin.db")
    case_id = await _create_case(async_url, status=CaseStatus.WAIT_DOCTOR, event_id="$widget-1")

    token_service = OpaqueTokenService()
    admin_token = "admin-token"
    admin_hash = token_service.hash_token(admin_token)
    admin_user_id = uuid4()

    hasher = BcryptPasswordHasher()
    engine = sa.create_engine(sync_url)
    with engine.begin() as connection:
        _insert_user(
            connection,
            user_id=admin_user_id,
            email="admin@example.org",
            password_hash=hasher.hash_password("pw"),
            role="admin",
            is_active=True,
        )
        _insert_token(
            connection,
            user_id=admin_user_id,
            token_hash=admin_hash,
            expires_at=datetime.now(tz=UTC) + timedelta(hours=1),
        )

    with _build_client(async_url) as client:
        response = client.post(
            BOOTSTRAP_PATH,
            json={"case_id": str(case_id)},
            headers=_auth_header(admin_token),
        )

    assert response.status_code == 200
    assert response.json() == {
        "case_id": str(case_id),
        "status": "WAIT_DOCTOR",
        "doctor_decision": None,
        "doctor_reason": None,
    }


@pytest.mark.asyncio
async def test_submit_returns_not_found_for_unknown_case(tmp_path: Path) -> None:
    sync_url, async_url = _upgrade_head(tmp_path, "widget_submit_not_found.db")

    token_service = OpaqueTokenService()
    admin_token = "admin-token"
    admin_hash = token_service.hash_token(admin_token)
    admin_user_id = uuid4()

    hasher = BcryptPasswordHasher()
    engine = sa.create_engine(sync_url)
    with engine.begin() as connection:
        _insert_user(
            connection,
            user_id=admin_user_id,
            email="admin@example.org",
            password_hash=hasher.hash_password("pw"),
            role="admin",
            is_active=True,
        )
        _insert_token(
            connection,
            user_id=admin_user_id,
            token_hash=admin_hash,
            expires_at=datetime.now(tz=UTC) + timedelta(hours=1),
        )

    with _build_client(async_url) as client:
        response = client.post(
            SUBMIT_PATH,
            json={
                "case_id": str(uuid4()),
                "doctor_user_id": "@doctor:example.org",
                "decision": "deny",
                "support_flag": "none",
            },
            headers=_auth_header(admin_token),
        )

    assert response.status_code == 404
    assert response.json() == {"detail": "case not found"}


@pytest.mark.asyncio
async def test_submit_returns_conflict_for_case_not_waiting_doctor(tmp_path: Path) -> None:
    sync_url, async_url = _upgrade_head(tmp_path, "widget_submit_wrong_state.db")
    case_id = await _create_case(async_url, status=CaseStatus.DOCTOR_ACCEPTED, event_id="$widget-2")

    token_service = OpaqueTokenService()
    admin_token = "admin-token"
    admin_hash = token_service.hash_token(admin_token)
    admin_user_id = uuid4()

    hasher = BcryptPasswordHasher()
    engine = sa.create_engine(sync_url)
    with engine.begin() as connection:
        _insert_user(
            connection,
            user_id=admin_user_id,
            email="admin@example.org",
            password_hash=hasher.hash_password("pw"),
            role="admin",
            is_active=True,
        )
        _insert_token(
            connection,
            user_id=admin_user_id,
            token_hash=admin_hash,
            expires_at=datetime.now(tz=UTC) + timedelta(hours=1),
        )

    with _build_client(async_url) as client:
        response = client.post(
            SUBMIT_PATH,
            json={
                "case_id": str(case_id),
                "doctor_user_id": "@doctor:example.org",
                "decision": "deny",
                "support_flag": "none",
            },
            headers=_auth_header(admin_token),
        )

    assert response.status_code == 409
    assert response.json() == {"detail": "case not in WAIT_DOCTOR"}


@pytest.mark.asyncio
async def test_submit_applies_decision_and_enqueues_existing_job_path(tmp_path: Path) -> None:
    sync_url, async_url = _upgrade_head(tmp_path, "widget_submit_applied.db")
    case_id = await _create_case(async_url, status=CaseStatus.WAIT_DOCTOR, event_id="$widget-3")

    token_service = OpaqueTokenService()
    admin_token = "admin-token"
    admin_hash = token_service.hash_token(admin_token)
    admin_user_id = uuid4()

    hasher = BcryptPasswordHasher()
    engine = sa.create_engine(sync_url)
    with engine.begin() as connection:
        _insert_user(
            connection,
            user_id=admin_user_id,
            email="admin@example.org",
            password_hash=hasher.hash_password("pw"),
            role="admin",
            is_active=True,
        )
        _insert_token(
            connection,
            user_id=admin_user_id,
            token_hash=admin_hash,
            expires_at=datetime.now(tz=UTC) + timedelta(hours=1),
        )

    with _build_client(async_url) as client:
        response = client.post(
            SUBMIT_PATH,
            json={
                "case_id": str(case_id),
                "doctor_user_id": "@doctor:example.org",
                "decision": "deny",
                "support_flag": "none",
            },
            headers=_auth_header(admin_token),
        )

    assert response.status_code == 200
    assert response.json() == {"ok": True}

    with engine.begin() as connection:
        row = connection.execute(
            sa.text(
                "SELECT status, doctor_decision, doctor_support_flag FROM cases "
                "WHERE case_id = :case_id"
            ),
            {"case_id": case_id.hex},
        ).mappings().one()
        jobs = connection.execute(
            sa.text("SELECT job_type FROM jobs WHERE case_id = :case_id"),
            {"case_id": case_id.hex},
        ).scalars().all()

    assert row["status"] == "DOCTOR_DENIED"
    assert row["doctor_decision"] == "deny"
    assert row["doctor_support_flag"] == "none"
    assert list(jobs) == ["post_room1_final_denial_triage"]


@pytest.mark.asyncio
async def test_submit_rejects_missing_token_and_reader_role_without_mutation(
    tmp_path: Path,
) -> None:
    sync_url, async_url = _upgrade_head(tmp_path, "widget_submit_auth.db")
    case_id = await _create_case(async_url, status=CaseStatus.WAIT_DOCTOR, event_id="$widget-4")

    token_service = OpaqueTokenService()
    reader_token = "reader-token"
    reader_hash = token_service.hash_token(reader_token)
    reader_user_id = uuid4()

    hasher = BcryptPasswordHasher()
    engine = sa.create_engine(sync_url)
    with engine.begin() as connection:
        _insert_user(
            connection,
            user_id=reader_user_id,
            email="reader@example.org",
            password_hash=hasher.hash_password("pw"),
            role="reader",
            is_active=True,
        )
        _insert_token(
            connection,
            user_id=reader_user_id,
            token_hash=reader_hash,
            expires_at=datetime.now(tz=UTC) + timedelta(hours=1),
        )

    with _build_client(async_url) as client:
        unauth = client.post(
            SUBMIT_PATH,
            json={
                "case_id": str(case_id),
                "doctor_user_id": "@doctor:example.org",
                "decision": "deny",
                "support_flag": "none",
            },
        )
        forbidden = client.post(
            SUBMIT_PATH,
            json={
                "case_id": str(case_id),
                "doctor_user_id": "@doctor:example.org",
                "decision": "deny",
                "support_flag": "none",
            },
            headers=_auth_header(reader_token),
        )

    assert unauth.status_code == 401
    assert forbidden.status_code == 403

    with engine.begin() as connection:
        row = connection.execute(
            sa.text("SELECT status, doctor_decision FROM cases WHERE case_id = :case_id"),
            {"case_id": case_id.hex},
        ).mappings().one()
        jobs_count = connection.execute(
            sa.text("SELECT COUNT(*) AS count FROM jobs WHERE case_id = :case_id"),
            {"case_id": case_id.hex},
        ).mappings().one()

    assert row["status"] == "WAIT_DOCTOR"
    assert row["doctor_decision"] is None
    assert int(jobs_count["count"]) == 0

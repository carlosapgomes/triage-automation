from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
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
from triage_automation.application.services.post_room2_widget_service import PostRoom2WidgetService
from triage_automation.domain.case_status import CaseStatus
from triage_automation.infrastructure.db.audit_repository import SqlAlchemyAuditRepository
from triage_automation.infrastructure.db.auth_event_repository import SqlAlchemyAuthEventRepository
from triage_automation.infrastructure.db.auth_token_repository import SqlAlchemyAuthTokenRepository
from triage_automation.infrastructure.db.case_repository import SqlAlchemyCaseRepository
from triage_automation.infrastructure.db.job_queue_repository import SqlAlchemyJobQueueRepository
from triage_automation.infrastructure.db.message_repository import SqlAlchemyMessageRepository
from triage_automation.infrastructure.db.prior_case_queries import SqlAlchemyPriorCaseQueries
from triage_automation.infrastructure.db.session import create_session_factory
from triage_automation.infrastructure.db.user_repository import SqlAlchemyUserRepository
from triage_automation.infrastructure.security.password_hasher import BcryptPasswordHasher
from triage_automation.infrastructure.security.token_service import OpaqueTokenService

SECRET = "webhook-secret"
SUBMIT_PATH = "/widget/room2/submit"


class FakeMatrixPoster:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []
        self.file_calls: list[tuple[str, str, str, str]] = []
        self._counter = 0

    async def send_text(
        self,
        *,
        room_id: str,
        body: str,
        formatted_body: str | None = None,
    ) -> str:
        _ = formatted_body
        self.calls.append((room_id, body))
        self._counter += 1
        return f"$room2-{self._counter}"

    async def reply_text(
        self,
        *,
        room_id: str,
        event_id: str,
        body: str,
        formatted_body: str | None = None,
    ) -> str:
        _ = formatted_body
        _ = event_id
        self.calls.append((room_id, body))
        self._counter += 1
        return f"$room2-{self._counter}"

    async def reply_file_text(
        self,
        *,
        room_id: str,
        event_id: str,
        filename: str,
        text_content: str,
    ) -> str:
        _ = event_id
        self.file_calls.append((room_id, filename, text_content, event_id))
        self._counter += 1
        return f"$room2-{self._counter}"


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


def _structured_data() -> dict[str, Any]:
    return {
        "schema_version": "1.1",
        "policy_precheck": {},
        "eda": {
            "asa": {"class": "II"},
            "cardiovascular_risk": {"level": "low"},
        },
    }


def _suggested_action(*, case_id: UUID, suggestion: str) -> dict[str, Any]:
    return {
        "schema_version": "1.1",
        "case_id": str(case_id),
        "agency_record_number": "12345",
        "suggestion": suggestion,
        "support_recommendation": "none",
        "rationale": "rationale",
    }


async def _create_case_and_post_room2(async_url: str, *, suggestion: str, event_id: str) -> UUID:
    session_factory = create_session_factory(async_url)
    case_repo = SqlAlchemyCaseRepository(session_factory)

    created = await case_repo.create_case(
        CaseCreateInput(
            case_id=uuid4(),
            status=CaseStatus.LLM_SUGGEST,
            room1_origin_room_id="!room1:example.org",
            room1_origin_event_id=event_id,
            room1_sender_user_id="@human:example.org",
        )
    )
    await case_repo.store_pdf_extraction(
        case_id=created.case_id,
        pdf_mxc_url="mxc://example.org/current",
        extracted_text="current text",
        agency_record_number="12345",
    )
    await case_repo.store_llm1_artifacts(
        case_id=created.case_id,
        structured_data_json=_structured_data(),
        summary_text="Resumo LLM1",
    )
    await case_repo.store_llm2_artifacts(
        case_id=created.case_id,
        suggested_action_json=_suggested_action(case_id=created.case_id, suggestion=suggestion),
    )

    service = PostRoom2WidgetService(
        room2_id="!room2:example.org",
        widget_public_base_url="https://bot-api.example.org",
        case_repository=case_repo,
        audit_repository=SqlAlchemyAuditRepository(session_factory),
        message_repository=SqlAlchemyMessageRepository(session_factory),
        prior_case_queries=SqlAlchemyPriorCaseQueries(session_factory),
        matrix_poster=FakeMatrixPoster(),
    )
    await service.post_widget(case_id=created.case_id)
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
async def test_widget_accept_path_reaches_doctor_accepted_with_single_job_and_audit(
    tmp_path: Path,
) -> None:
    sync_url, async_url = _upgrade_head(tmp_path, "room2_widget_accept.db")
    case_id = await _create_case_and_post_room2(
        async_url,
        suggestion="accept",
        event_id="$room2-widget-accept",
    )

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
        first = client.post(
            SUBMIT_PATH,
            json={
                "case_id": str(case_id),
                "doctor_user_id": "@doctor:example.org",
                "decision": "accept",
                "support_flag": "anesthesist",
            },
            headers=_auth_header(admin_token),
        )
        duplicate = client.post(
            SUBMIT_PATH,
            json={
                "case_id": str(case_id),
                "doctor_user_id": "@doctor:example.org",
                "decision": "accept",
                "support_flag": "anesthesist",
            },
            headers=_auth_header(admin_token),
        )

    assert first.status_code == 200
    assert first.json() == {"ok": True}
    assert duplicate.status_code == 409

    with engine.begin() as connection:
        case_row = connection.execute(
            sa.text(
                "SELECT status, doctor_decision, doctor_support_flag "
                "FROM cases WHERE case_id = :case_id"
            ),
            {"case_id": case_id.hex},
        ).mappings().one()
        jobs = connection.execute(
            sa.text("SELECT job_type FROM jobs WHERE case_id = :case_id ORDER BY job_id"),
            {"case_id": case_id.hex},
        ).scalars().all()
        audit_payload = connection.execute(
            sa.text(
                "SELECT payload FROM case_events WHERE case_id = :case_id "
                "AND event_type = 'ROOM2_WIDGET_SUBMITTED' ORDER BY id DESC LIMIT 1"
            ),
            {"case_id": case_id.hex},
        ).scalar_one()

    assert case_row["status"] == "DOCTOR_ACCEPTED"
    assert case_row["doctor_decision"] == "accept"
    assert case_row["doctor_support_flag"] == "anesthesist"
    assert list(jobs) == ["post_room3_request"]

    parsed_audit_payload = (
        audit_payload if isinstance(audit_payload, dict) else json.loads(str(audit_payload))
    )
    assert parsed_audit_payload["doctor_user_id"] == "@doctor:example.org"
    assert parsed_audit_payload["decision"] == "accept"


@pytest.mark.asyncio
async def test_widget_deny_path_reaches_doctor_denied_and_enqueues_final_denial(
    tmp_path: Path,
) -> None:
    sync_url, async_url = _upgrade_head(tmp_path, "room2_widget_deny.db")
    case_id = await _create_case_and_post_room2(
        async_url,
        suggestion="deny",
        event_id="$room2-widget-deny",
    )

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
        case_row = connection.execute(
            sa.text(
                "SELECT status, doctor_decision, doctor_support_flag "
                "FROM cases WHERE case_id = :case_id"
            ),
            {"case_id": case_id.hex},
        ).mappings().one()
        jobs = connection.execute(
            sa.text("SELECT job_type FROM jobs WHERE case_id = :case_id ORDER BY job_id"),
            {"case_id": case_id.hex},
        ).scalars().all()

    assert case_row["status"] == "DOCTOR_DENIED"
    assert case_row["doctor_decision"] == "deny"
    assert case_row["doctor_support_flag"] == "none"
    assert list(jobs) == ["post_room1_final_denial_triage"]


@pytest.mark.asyncio
async def test_widget_submit_rejects_unauthenticated_and_reader_without_case_mutation(
    tmp_path: Path,
) -> None:
    sync_url, async_url = _upgrade_head(tmp_path, "room2_widget_auth_negative.db")
    case_id = await _create_case_and_post_room2(
        async_url,
        suggestion="deny",
        event_id="$room2-widget-auth",
    )

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
        case_row = connection.execute(
            sa.text("SELECT status, doctor_decision FROM cases WHERE case_id = :case_id"),
            {"case_id": case_id.hex},
        ).mappings().one()
        jobs_count = connection.execute(
            sa.text("SELECT COUNT(*) AS count FROM jobs WHERE case_id = :case_id"),
            {"case_id": case_id.hex},
        ).mappings().one()

    assert case_row["status"] == "WAIT_DOCTOR"
    assert case_row["doctor_decision"] is None
    assert int(jobs_count["count"]) == 0

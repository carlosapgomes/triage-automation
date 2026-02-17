from __future__ import annotations

import json
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
from triage_automation.infrastructure.db.message_repository import SqlAlchemyMessageRepository
from triage_automation.infrastructure.db.session import create_session_factory
from triage_automation.infrastructure.db.user_repository import SqlAlchemyUserRepository
from triage_automation.infrastructure.http.hmac_auth import compute_hmac_sha256
from triage_automation.infrastructure.security.password_hasher import BcryptPasswordHasher

SECRET = "webhook-secret"


class FakeRoom2DecisionPoster:
    """In-memory Matrix poster used to assert Room-2 decision ack emission."""

    def __init__(self) -> None:
        self.send_calls: list[tuple[str, str]] = []
        self.reply_calls: list[tuple[str, str, str]] = []
        self._counter = 0

    async def send_text(self, *, room_id: str, body: str) -> str:
        self.send_calls.append((room_id, body))
        self._counter += 1
        return f"$room2-decision-ack-{self._counter}"

    async def reply_text(self, *, room_id: str, event_id: str, body: str) -> str:
        self.reply_calls.append((room_id, event_id, body))
        self._counter += 1
        return f"$room2-decision-ack-{self._counter}"


def _upgrade_head(tmp_path: Path, filename: str) -> tuple[str, str]:
    db_path = tmp_path / filename
    sync_url = f"sqlite+pysqlite:///{db_path}"
    async_url = f"sqlite+aiosqlite:///{db_path}"

    alembic_config = Config("alembic.ini")
    alembic_config.set_main_option("sqlalchemy.url", sync_url)
    command.upgrade(alembic_config, "head")

    return sync_url, async_url


async def _create_wait_doctor_case(async_url: str, *, event_id: str) -> UUID:
    session_factory = create_session_factory(async_url)
    case_repo = SqlAlchemyCaseRepository(session_factory)

    created = await case_repo.create_case(
        CaseCreateInput(
            case_id=uuid4(),
            status=CaseStatus.WAIT_DOCTOR,
            room1_origin_room_id="!room1:example.org",
            room1_origin_event_id=event_id,
            room1_sender_user_id="@human:example.org",
        )
    )
    return created.case_id


def _build_client(
    async_url: str,
    *,
    decision_service: HandleDoctorDecisionService | None = None,
) -> TestClient:
    session_factory = create_session_factory(async_url)
    runtime_decision_service = decision_service or HandleDoctorDecisionService(
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
        decision_service=runtime_decision_service,
        auth_service=auth_service,
        auth_token_repository=SqlAlchemyAuthTokenRepository(session_factory),
        database_url=async_url,
    )
    return TestClient(app)


def _post_signed(client: TestClient, payload: dict[str, object], *, signature: str | None = None):
    body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    signed = signature or compute_hmac_sha256(secret=SECRET, body=body)
    return client.post(
        "/callbacks/triage-decision",
        content=body,
        headers={"content-type": "application/json", "x-signature": signed},
    )


@pytest.mark.asyncio
async def test_valid_signature_is_accepted_and_invalid_rejected(tmp_path: Path) -> None:
    sync_url, async_url = _upgrade_head(tmp_path, "triage_webhook_signature.db")
    case_id = await _create_wait_doctor_case(async_url, event_id="$origin-webhook-1")

    with _build_client(async_url) as client:
        payload = {
            "case_id": str(case_id),
            "doctor_user_id": "@doctor:example.org",
            "decision": "deny",
            "support_flag": "none",
            "reason": "sem criterio",
        }

        rejected = _post_signed(client, payload, signature="bad-signature")
        assert rejected.status_code == 401

        accepted = _post_signed(client, payload)
        assert accepted.status_code == 200
        assert accepted.json() == {"ok": True}

    engine = sa.create_engine(sync_url)
    with engine.begin() as connection:
        row = connection.execute(
            sa.text(
                "SELECT status, doctor_decision, doctor_support_flag "
                "FROM cases WHERE case_id = :case_id"
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
async def test_decision_deny_requires_support_flag_none(tmp_path: Path) -> None:
    _, async_url = _upgrade_head(tmp_path, "triage_webhook_deny_support.db")
    case_id = await _create_wait_doctor_case(async_url, event_id="$origin-webhook-2")

    with _build_client(async_url) as client:
        response = _post_signed(
            client,
            {
                "case_id": str(case_id),
                "doctor_user_id": "@doctor:example.org",
                "decision": "deny",
                "support_flag": "anesthesist",
            },
        )

    assert response.status_code == 400


@pytest.mark.asyncio
@pytest.mark.parametrize("support_flag", ["none", "anesthesist", "anesthesist_icu"])
async def test_decision_accept_allows_only_supported_flags_and_enqueues_room3(
    tmp_path: Path,
    support_flag: str,
) -> None:
    sync_url, async_url = _upgrade_head(tmp_path, f"triage_webhook_accept_{support_flag}.db")
    case_id = await _create_wait_doctor_case(async_url, event_id=f"$origin-webhook-{support_flag}")

    with _build_client(async_url) as client:
        response = _post_signed(
            client,
            {
                "case_id": str(case_id),
                "doctor_user_id": "@doctor:example.org",
                "decision": "accept",
                "support_flag": support_flag,
            },
        )

    assert response.status_code == 200

    engine = sa.create_engine(sync_url)
    with engine.begin() as connection:
        row = connection.execute(
            sa.text("SELECT status, doctor_support_flag FROM cases WHERE case_id = :case_id"),
            {"case_id": case_id.hex},
        ).mappings().one()
        jobs = connection.execute(
            sa.text("SELECT job_type FROM jobs WHERE case_id = :case_id"),
            {"case_id": case_id.hex},
        ).scalars().all()

    assert row["status"] == "DOCTOR_ACCEPTED"
    assert row["doctor_support_flag"] == support_flag
    assert list(jobs) == ["post_room3_request"]


@pytest.mark.asyncio
async def test_webhook_posts_room2_decision_ack_and_persists_target_mapping(tmp_path: Path) -> None:
    sync_url, async_url = _upgrade_head(tmp_path, "triage_webhook_room2_decision_ack.db")
    case_id = await _create_wait_doctor_case(async_url, event_id="$origin-webhook-room2-ack")
    session_factory = create_session_factory(async_url)
    matrix_poster = FakeRoom2DecisionPoster()
    decision_service = HandleDoctorDecisionService(
        case_repository=SqlAlchemyCaseRepository(session_factory),
        audit_repository=SqlAlchemyAuditRepository(session_factory),
        job_queue=SqlAlchemyJobQueueRepository(session_factory),
        message_repository=SqlAlchemyMessageRepository(session_factory),
        matrix_poster=matrix_poster,
        room2_id="!room2:example.org",
    )

    with _build_client(async_url, decision_service=decision_service) as client:
        response = _post_signed(
            client,
            {
                "case_id": str(case_id),
                "doctor_user_id": "@doctor:example.org",
                "decision": "accept",
                "support_flag": "none",
                "widget_event_id": "$doctor-decision-event",
            },
        )

    assert response.status_code == 200
    assert matrix_poster.reply_calls
    assert not matrix_poster.send_calls

    engine = sa.create_engine(sync_url)
    with engine.begin() as connection:
        room2_ack_messages = connection.execute(
            sa.text(
                "SELECT COUNT(*) FROM case_messages WHERE case_id = :case_id "
                "AND room_id = '!room2:example.org' "
                "AND kind = 'room2_decision_ack'"
            ),
            {"case_id": case_id.hex},
        ).scalar_one()

    assert int(room2_ack_messages) == 1

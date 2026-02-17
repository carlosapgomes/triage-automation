from __future__ import annotations

from pathlib import Path
from uuid import UUID, uuid4

import pytest
import sqlalchemy as sa
from alembic.config import Config

from alembic import command
from apps.bot_matrix.main import poll_room2_reply_events_once
from triage_automation.application.ports.case_repository_port import CaseCreateInput
from triage_automation.application.ports.message_repository_port import CaseMessageCreateInput
from triage_automation.application.services.handle_doctor_decision_service import (
    HandleDoctorDecisionService,
)
from triage_automation.application.services.room2_reply_service import Room2ReplyService
from triage_automation.domain.case_status import CaseStatus
from triage_automation.infrastructure.db.audit_repository import SqlAlchemyAuditRepository
from triage_automation.infrastructure.db.case_repository import SqlAlchemyCaseRepository
from triage_automation.infrastructure.db.job_queue_repository import SqlAlchemyJobQueueRepository
from triage_automation.infrastructure.db.message_repository import SqlAlchemyMessageRepository
from triage_automation.infrastructure.db.session import create_session_factory


class FakeMatrixRuntimeClient:
    def __init__(
        self,
        sync_payload: dict[str, object],
        *,
        joined_members: dict[str, set[str]] | None = None,
    ) -> None:
        self._sync_payload = sync_payload
        self._joined_members = joined_members
        self.sync_calls: list[tuple[str | None, int]] = []
        self.reply_calls: list[tuple[str, str, str]] = []
        self.send_calls: list[tuple[str, str]] = []
        self._counter = 0

    async def sync(self, *, since: str | None, timeout_ms: int) -> dict[str, object]:
        self.sync_calls.append((since, timeout_ms))
        return self._sync_payload

    async def reply_text(self, *, room_id: str, event_id: str, body: str) -> str:
        self.reply_calls.append((room_id, event_id, body))
        self._counter += 1
        return f"$room2-ack-{self._counter}"

    async def send_text(self, *, room_id: str, body: str) -> str:
        self.send_calls.append((room_id, body))
        self._counter += 1
        return f"$room2-send-{self._counter}"

    async def is_user_joined(self, *, room_id: str, user_id: str) -> bool:
        if self._joined_members is None:
            return True
        return user_id in self._joined_members.get(room_id, set())


def _upgrade_head(tmp_path: Path, filename: str) -> tuple[str, str]:
    db_path = tmp_path / filename
    sync_url = f"sqlite+pysqlite:///{db_path}"
    async_url = f"sqlite+aiosqlite:///{db_path}"

    alembic_config = Config("alembic.ini")
    alembic_config.set_main_option("sqlalchemy.url", sync_url)
    command.upgrade(alembic_config, "head")

    return sync_url, async_url


async def _setup_wait_doctor_case(
    async_url: str,
    *,
    origin_event_id: str,
) -> tuple[UUID, str]:
    return await _setup_case_with_status(
        async_url,
        origin_event_id=origin_event_id,
        status=CaseStatus.WAIT_DOCTOR,
    )


async def _setup_case_with_status(
    async_url: str,
    *,
    origin_event_id: str,
    status: CaseStatus,
) -> tuple[UUID, str]:
    session_factory = create_session_factory(async_url)
    case_repo = SqlAlchemyCaseRepository(session_factory)
    message_repo = SqlAlchemyMessageRepository(session_factory)

    case = await case_repo.create_case(
        CaseCreateInput(
            case_id=uuid4(),
            status=status,
            room1_origin_room_id="!room1:example.org",
            room1_origin_event_id=origin_event_id,
            room1_sender_user_id="@human:example.org",
        )
    )

    room2_root_event_id = "$room2-root"
    await message_repo.add_message(
        CaseMessageCreateInput(
            case_id=case.case_id,
            room_id="!room2:example.org",
            event_id=room2_root_event_id,
            kind="room2_case_root",
            sender_user_id=None,
        )
    )
    return case.case_id, room2_root_event_id


def _room2_reply_event(
    *,
    event_id: str,
    sender: str,
    body: str,
    reply_to_event_id: str,
) -> dict[str, object]:
    return {
        "type": "m.room.message",
        "event_id": event_id,
        "sender": sender,
        "content": {
            "msgtype": "m.text",
            "body": body,
            "m.relates_to": {
                "m.in_reply_to": {
                    "event_id": reply_to_event_id,
                }
            },
        },
    }


def _room2_non_reply_message_event(
    *,
    event_id: str,
    sender: str,
    body: str,
) -> dict[str, object]:
    return {
        "type": "m.room.message",
        "event_id": event_id,
        "sender": sender,
        "content": {
            "msgtype": "m.text",
            "body": body,
        },
    }


def _sync_payload(
    *,
    next_batch: str,
    room_id: str,
    events: list[dict[str, object]],
) -> dict[str, object]:
    return {
        "next_batch": next_batch,
        "rooms": {
            "join": {
                room_id: {
                    "timeline": {
                        "events": events,
                    }
                }
            }
        },
    }


@pytest.mark.asyncio
async def test_runtime_listener_routes_room2_decision_reply_to_existing_decision_path(
    tmp_path: Path,
) -> None:
    sync_url, async_url = _upgrade_head(tmp_path, "room2_reply_listener_valid.db")
    case_id, root_event_id = await _setup_wait_doctor_case(
        async_url,
        origin_event_id="$origin-room2-listener-valid",
    )
    body = (
        "decision: accept\n"
        "support_flag: none\n"
        "reason: criterios atendidos\n"
        f"case_id: {case_id}"
    )
    sync_client = FakeMatrixRuntimeClient(
        _sync_payload(
            next_batch="s-room2",
            room_id="!room2:example.org",
            events=[
                _room2_reply_event(
                    event_id="$doctor-room2-reply-1",
                    sender="@doctor:example.org",
                    body=body,
                    reply_to_event_id=root_event_id,
                )
            ],
        )
    )

    session_factory = create_session_factory(async_url)
    message_repository = SqlAlchemyMessageRepository(session_factory)
    decision_service = HandleDoctorDecisionService(
        case_repository=SqlAlchemyCaseRepository(session_factory),
        audit_repository=SqlAlchemyAuditRepository(session_factory),
        job_queue=SqlAlchemyJobQueueRepository(session_factory),
        message_repository=message_repository,
        matrix_poster=sync_client,
        room2_id="!room2:example.org",
    )
    room2_reply_service = Room2ReplyService(
        room2_id="!room2:example.org",
        decision_service=decision_service,
        membership_authorizer=sync_client,
    )

    next_since, routed_count = await poll_room2_reply_events_once(
        matrix_client=sync_client,
        room2_reply_service=room2_reply_service,
        message_repository=message_repository,
        room2_id="!room2:example.org",
        bot_user_id="@bot:example.org",
        since_token=None,
        sync_timeout_ms=5_000,
    )

    assert next_since == "s-room2"
    assert routed_count == 1
    assert len(sync_client.reply_calls) == 1
    assert sync_client.reply_calls[0][1] == "$doctor-room2-reply-1"
    ack_body = sync_client.reply_calls[0][2]
    assert "resultado: sucesso" in ack_body
    assert f"caso: {case_id}" in ack_body
    assert "decisao: aceitar" in ack_body
    assert "suporte: nenhum" in ack_body

    engine = sa.create_engine(sync_url)
    with engine.begin() as connection:
        case_row = connection.execute(
            sa.text(
                "SELECT status, doctor_decision, doctor_support_flag, doctor_user_id "
                "FROM cases WHERE case_id = :case_id"
            ),
            {"case_id": case_id.hex},
        ).mappings().one()
        jobs = connection.execute(
            sa.text(
                "SELECT job_type FROM jobs WHERE case_id = :case_id ORDER BY job_id DESC LIMIT 1"
            ),
            {"case_id": case_id.hex},
        ).scalar_one()
        room2_reply_count = connection.execute(
            sa.text(
                "SELECT COUNT(*) FROM case_messages "
                "WHERE case_id = :case_id AND kind = 'room2_doctor_reply'"
            ),
            {"case_id": case_id.hex},
        ).scalar_one()

    assert case_row["status"] == "DOCTOR_ACCEPTED"
    assert case_row["doctor_decision"] == "accept"
    assert case_row["doctor_support_flag"] == "none"
    assert case_row["doctor_user_id"] == "@doctor:example.org"
    assert jobs == "post_room3_request"
    assert int(room2_reply_count) == 1


@pytest.mark.asyncio
async def test_runtime_listener_routes_room2_decision_reply_to_instructions_message(
    tmp_path: Path,
) -> None:
    sync_url, async_url = _upgrade_head(tmp_path, "room2_reply_listener_instructions.db")
    case_id, _root_event_id = await _setup_wait_doctor_case(
        async_url,
        origin_event_id="$origin-room2-listener-instructions",
    )
    instructions_event_id = "$room2-instructions"
    session_factory = create_session_factory(async_url)
    message_repository = SqlAlchemyMessageRepository(session_factory)
    await message_repository.add_message(
        CaseMessageCreateInput(
            case_id=case_id,
            room_id="!room2:example.org",
            event_id=instructions_event_id,
            kind="room2_case_instructions",
            sender_user_id=None,
        )
    )

    body = (
        "decisao: aceitar\n"
        "suporte: nenhum\n"
        "motivo: criterios atendidos\n"
        f"caso: {case_id}"
    )
    sync_client = FakeMatrixRuntimeClient(
        _sync_payload(
            next_batch="s-room2-instructions",
            room_id="!room2:example.org",
            events=[
                _room2_reply_event(
                    event_id="$doctor-room2-reply-instructions-1",
                    sender="@doctor:example.org",
                    body=body,
                    reply_to_event_id=instructions_event_id,
                )
            ],
        )
    )

    decision_service = HandleDoctorDecisionService(
        case_repository=SqlAlchemyCaseRepository(session_factory),
        audit_repository=SqlAlchemyAuditRepository(session_factory),
        job_queue=SqlAlchemyJobQueueRepository(session_factory),
        message_repository=message_repository,
        matrix_poster=sync_client,
        room2_id="!room2:example.org",
    )
    room2_reply_service = Room2ReplyService(
        room2_id="!room2:example.org",
        decision_service=decision_service,
        membership_authorizer=sync_client,
    )

    next_since, routed_count = await poll_room2_reply_events_once(
        matrix_client=sync_client,
        room2_reply_service=room2_reply_service,
        message_repository=message_repository,
        room2_id="!room2:example.org",
        bot_user_id="@bot:example.org",
        since_token=None,
        sync_timeout_ms=5_000,
    )

    assert next_since == "s-room2-instructions"
    assert routed_count == 1
    assert len(sync_client.reply_calls) == 1
    ack_body = sync_client.reply_calls[0][2]
    assert "resultado: sucesso" in ack_body
    assert f"caso: {case_id}" in ack_body
    assert "decisao: aceitar" in ack_body
    assert "suporte: nenhum" in ack_body

    engine = sa.create_engine(sync_url)
    with engine.begin() as connection:
        case_row = connection.execute(
            sa.text(
                "SELECT status, doctor_decision, doctor_support_flag, doctor_user_id "
                "FROM cases WHERE case_id = :case_id"
            ),
            {"case_id": case_id.hex},
        ).mappings().one()
        jobs = connection.execute(
            sa.text(
                "SELECT job_type FROM jobs WHERE case_id = :case_id ORDER BY job_id DESC LIMIT 1"
            ),
            {"case_id": case_id.hex},
        ).scalar_one()

    assert case_row["status"] == "DOCTOR_ACCEPTED"
    assert case_row["doctor_decision"] == "accept"
    assert case_row["doctor_support_flag"] == "none"
    assert case_row["doctor_user_id"] == "@doctor:example.org"
    assert jobs == "post_room3_request"


@pytest.mark.asyncio
async def test_runtime_listener_routes_room2_deny_reply_to_denial_job_path(
    tmp_path: Path,
) -> None:
    sync_url, async_url = _upgrade_head(tmp_path, "room2_reply_listener_deny.db")
    case_id, root_event_id = await _setup_wait_doctor_case(
        async_url,
        origin_event_id="$origin-room2-listener-deny",
    )
    body = (
        "decision: deny\n"
        "support_flag: none\n"
        "reason: criterios negados\n"
        f"case_id: {case_id}"
    )
    sync_client = FakeMatrixRuntimeClient(
        _sync_payload(
            next_batch="s-room2-deny",
            room_id="!room2:example.org",
            events=[
                _room2_reply_event(
                    event_id="$doctor-room2-reply-deny-1",
                    sender="@doctor:example.org",
                    body=body,
                    reply_to_event_id=root_event_id,
                )
            ],
        )
    )

    session_factory = create_session_factory(async_url)
    message_repository = SqlAlchemyMessageRepository(session_factory)
    decision_service = HandleDoctorDecisionService(
        case_repository=SqlAlchemyCaseRepository(session_factory),
        audit_repository=SqlAlchemyAuditRepository(session_factory),
        job_queue=SqlAlchemyJobQueueRepository(session_factory),
        message_repository=message_repository,
        matrix_poster=sync_client,
        room2_id="!room2:example.org",
    )
    room2_reply_service = Room2ReplyService(
        room2_id="!room2:example.org",
        decision_service=decision_service,
        membership_authorizer=sync_client,
    )

    next_since, routed_count = await poll_room2_reply_events_once(
        matrix_client=sync_client,
        room2_reply_service=room2_reply_service,
        message_repository=message_repository,
        room2_id="!room2:example.org",
        bot_user_id="@bot:example.org",
        since_token=None,
        sync_timeout_ms=5_000,
    )

    assert next_since == "s-room2-deny"
    assert routed_count == 1
    assert len(sync_client.reply_calls) == 1
    ack_body = sync_client.reply_calls[0][2]
    assert "resultado: sucesso" in ack_body
    assert "decisao: negar" in ack_body
    assert "suporte: nenhum" in ack_body

    engine = sa.create_engine(sync_url)
    with engine.begin() as connection:
        case_row = connection.execute(
            sa.text(
                "SELECT status, doctor_decision, doctor_support_flag, doctor_user_id "
                "FROM cases WHERE case_id = :case_id"
            ),
            {"case_id": case_id.hex},
        ).mappings().one()
        jobs = connection.execute(
            sa.text(
                "SELECT job_type FROM jobs WHERE case_id = :case_id ORDER BY job_id DESC LIMIT 1"
            ),
            {"case_id": case_id.hex},
        ).scalar_one()

    assert case_row["status"] == "DOCTOR_DENIED"
    assert case_row["doctor_decision"] == "deny"
    assert case_row["doctor_support_flag"] == "none"
    assert case_row["doctor_user_id"] == "@doctor:example.org"
    assert jobs == "post_room1_final_denial_triage"


@pytest.mark.asyncio
async def test_runtime_listener_duplicate_room2_replies_are_idempotent(
    tmp_path: Path,
) -> None:
    sync_url, async_url = _upgrade_head(tmp_path, "room2_reply_listener_duplicate.db")
    case_id, root_event_id = await _setup_wait_doctor_case(
        async_url,
        origin_event_id="$origin-room2-listener-duplicate",
    )
    body = (
        "decision: accept\n"
        "support_flag: none\n"
        "reason: criterios atendidos\n"
        f"case_id: {case_id}"
    )
    sync_client = FakeMatrixRuntimeClient(
        _sync_payload(
            next_batch="s-room2-duplicate",
            room_id="!room2:example.org",
            events=[
                _room2_reply_event(
                    event_id="$doctor-room2-reply-dup-1",
                    sender="@doctor:example.org",
                    body=body,
                    reply_to_event_id=root_event_id,
                ),
                _room2_reply_event(
                    event_id="$doctor-room2-reply-dup-2",
                    sender="@doctor:example.org",
                    body=body,
                    reply_to_event_id=root_event_id,
                ),
            ],
        )
    )

    session_factory = create_session_factory(async_url)
    message_repository = SqlAlchemyMessageRepository(session_factory)
    decision_service = HandleDoctorDecisionService(
        case_repository=SqlAlchemyCaseRepository(session_factory),
        audit_repository=SqlAlchemyAuditRepository(session_factory),
        job_queue=SqlAlchemyJobQueueRepository(session_factory),
        message_repository=message_repository,
        matrix_poster=sync_client,
        room2_id="!room2:example.org",
    )
    room2_reply_service = Room2ReplyService(
        room2_id="!room2:example.org",
        decision_service=decision_service,
        membership_authorizer=sync_client,
    )

    next_since, routed_count = await poll_room2_reply_events_once(
        matrix_client=sync_client,
        room2_reply_service=room2_reply_service,
        message_repository=message_repository,
        room2_id="!room2:example.org",
        bot_user_id="@bot:example.org",
        since_token=None,
        sync_timeout_ms=5_000,
    )

    assert next_since == "s-room2-duplicate"
    assert routed_count == 1
    assert len(sync_client.reply_calls) == 2
    first_feedback = sync_client.reply_calls[0][2]
    second_feedback = sync_client.reply_calls[1][2]
    assert "resultado: sucesso" in first_feedback
    assert "resultado: erro" in second_feedback
    assert "codigo_erro: state_conflict" in second_feedback

    engine = sa.create_engine(sync_url)
    with engine.begin() as connection:
        case_row = connection.execute(
            sa.text(
                "SELECT status, doctor_decision, doctor_support_flag, doctor_user_id "
                "FROM cases WHERE case_id = :case_id"
            ),
            {"case_id": case_id.hex},
        ).mappings().one()
        jobs = connection.execute(
            sa.text("SELECT job_type FROM jobs WHERE case_id = :case_id"),
            {"case_id": case_id.hex},
        ).scalars().all()

    assert case_row["status"] == "DOCTOR_ACCEPTED"
    assert case_row["doctor_decision"] == "accept"
    assert case_row["doctor_support_flag"] == "none"
    assert case_row["doctor_user_id"] == "@doctor:example.org"
    assert list(jobs) == ["post_room3_request"]


@pytest.mark.asyncio
async def test_runtime_listener_rejects_reply_with_typed_doctor_identity_field(
    tmp_path: Path,
) -> None:
    sync_url, async_url = _upgrade_head(tmp_path, "room2_reply_listener_typed_identity.db")
    case_id, root_event_id = await _setup_wait_doctor_case(
        async_url,
        origin_event_id="$origin-room2-listener-typed-identity",
    )
    body = (
        "decision: accept\n"
        "support_flag: none\n"
        "reason: criterios atendidos\n"
        "doctor_user_id: @spoofed:example.org\n"
        f"case_id: {case_id}"
    )
    sync_client = FakeMatrixRuntimeClient(
        _sync_payload(
            next_batch="s-room2-typed-identity",
            room_id="!room2:example.org",
            events=[
                _room2_reply_event(
                    event_id="$doctor-room2-reply-typed-identity",
                    sender="@doctor:example.org",
                    body=body,
                    reply_to_event_id=root_event_id,
                )
            ],
        )
    )

    session_factory = create_session_factory(async_url)
    message_repository = SqlAlchemyMessageRepository(session_factory)
    decision_service = HandleDoctorDecisionService(
        case_repository=SqlAlchemyCaseRepository(session_factory),
        audit_repository=SqlAlchemyAuditRepository(session_factory),
        job_queue=SqlAlchemyJobQueueRepository(session_factory),
        message_repository=message_repository,
        matrix_poster=sync_client,
        room2_id="!room2:example.org",
    )
    room2_reply_service = Room2ReplyService(
        room2_id="!room2:example.org",
        decision_service=decision_service,
        membership_authorizer=sync_client,
    )

    next_since, routed_count = await poll_room2_reply_events_once(
        matrix_client=sync_client,
        room2_reply_service=room2_reply_service,
        message_repository=message_repository,
        room2_id="!room2:example.org",
        bot_user_id="@bot:example.org",
        since_token=None,
        sync_timeout_ms=5_000,
    )

    assert next_since == "s-room2-typed-identity"
    assert routed_count == 0
    assert len(sync_client.reply_calls) == 1
    error_body = sync_client.reply_calls[0][2]
    assert "resultado: erro" in error_body
    assert "codigo_erro: invalid_template" in error_body
    assert f"caso: {case_id}" in error_body
    assert sync_client.send_calls == []

    engine = sa.create_engine(sync_url)
    with engine.begin() as connection:
        case_row = connection.execute(
            sa.text(
                "SELECT status, doctor_decision, doctor_support_flag, doctor_user_id "
                "FROM cases WHERE case_id = :case_id"
            ),
            {"case_id": case_id.hex},
        ).mappings().one()
        jobs_count = connection.execute(
            sa.text("SELECT COUNT(*) FROM jobs WHERE case_id = :case_id"),
            {"case_id": case_id.hex},
        ).scalar_one()

    assert case_row["status"] == "WAIT_DOCTOR"
    assert case_row["doctor_decision"] is None
    assert case_row["doctor_support_flag"] is None
    assert case_row["doctor_user_id"] is None
    assert int(jobs_count) == 0


@pytest.mark.asyncio
async def test_runtime_listener_rejects_reply_from_room2_unauthorized_sender(
    tmp_path: Path,
) -> None:
    sync_url, async_url = _upgrade_head(tmp_path, "room2_reply_listener_unauthorized.db")
    case_id, root_event_id = await _setup_wait_doctor_case(
        async_url,
        origin_event_id="$origin-room2-listener-unauthorized",
    )
    body = (
        "decision: accept\n"
        "support_flag: none\n"
        "reason: criterios atendidos\n"
        f"case_id: {case_id}"
    )
    sync_client = FakeMatrixRuntimeClient(
        _sync_payload(
            next_batch="s-room2-unauthorized",
            room_id="!room2:example.org",
            events=[
                _room2_reply_event(
                    event_id="$doctor-room2-reply-unauthorized",
                    sender="@intruder:example.org",
                    body=body,
                    reply_to_event_id=root_event_id,
                )
            ],
        ),
        joined_members={"!room2:example.org": {"@doctor:example.org"}},
    )

    session_factory = create_session_factory(async_url)
    message_repository = SqlAlchemyMessageRepository(session_factory)
    decision_service = HandleDoctorDecisionService(
        case_repository=SqlAlchemyCaseRepository(session_factory),
        audit_repository=SqlAlchemyAuditRepository(session_factory),
        job_queue=SqlAlchemyJobQueueRepository(session_factory),
        message_repository=message_repository,
        matrix_poster=sync_client,
        room2_id="!room2:example.org",
    )
    room2_reply_service = Room2ReplyService(
        room2_id="!room2:example.org",
        decision_service=decision_service,
        membership_authorizer=sync_client,
    )

    next_since, routed_count = await poll_room2_reply_events_once(
        matrix_client=sync_client,
        room2_reply_service=room2_reply_service,
        message_repository=message_repository,
        room2_id="!room2:example.org",
        bot_user_id="@bot:example.org",
        since_token=None,
        sync_timeout_ms=5_000,
    )

    assert next_since == "s-room2-unauthorized"
    assert routed_count == 0
    assert len(sync_client.reply_calls) == 1
    error_body = sync_client.reply_calls[0][2]
    assert "resultado: erro" in error_body
    assert "codigo_erro: authorization_failed" in error_body
    assert f"caso: {case_id}" in error_body
    assert sync_client.send_calls == []

    engine = sa.create_engine(sync_url)
    with engine.begin() as connection:
        case_row = connection.execute(
            sa.text(
                "SELECT status, doctor_decision, doctor_support_flag, doctor_user_id "
                "FROM cases WHERE case_id = :case_id"
            ),
            {"case_id": case_id.hex},
        ).mappings().one()
        jobs_count = connection.execute(
            sa.text("SELECT COUNT(*) FROM jobs WHERE case_id = :case_id"),
            {"case_id": case_id.hex},
        ).scalar_one()

    assert case_row["status"] == "WAIT_DOCTOR"
    assert case_row["doctor_decision"] is None
    assert case_row["doctor_support_flag"] is None
    assert case_row["doctor_user_id"] is None
    assert int(jobs_count) == 0


@pytest.mark.asyncio
async def test_runtime_listener_emits_error_feedback_when_case_not_waiting_doctor(
    tmp_path: Path,
) -> None:
    sync_url, async_url = _upgrade_head(tmp_path, "room2_reply_listener_wrong_state.db")
    case_id, root_event_id = await _setup_case_with_status(
        async_url,
        origin_event_id="$origin-room2-listener-wrong-state",
        status=CaseStatus.DOCTOR_ACCEPTED,
    )
    body = (
        "decision: accept\n"
        "support_flag: none\n"
        "reason: criterios atendidos\n"
        f"case_id: {case_id}"
    )
    sync_client = FakeMatrixRuntimeClient(
        _sync_payload(
            next_batch="s-room2-wrong-state",
            room_id="!room2:example.org",
            events=[
                _room2_reply_event(
                    event_id="$doctor-room2-reply-wrong-state",
                    sender="@doctor:example.org",
                    body=body,
                    reply_to_event_id=root_event_id,
                )
            ],
        )
    )

    session_factory = create_session_factory(async_url)
    message_repository = SqlAlchemyMessageRepository(session_factory)
    decision_service = HandleDoctorDecisionService(
        case_repository=SqlAlchemyCaseRepository(session_factory),
        audit_repository=SqlAlchemyAuditRepository(session_factory),
        job_queue=SqlAlchemyJobQueueRepository(session_factory),
        message_repository=message_repository,
        matrix_poster=sync_client,
        room2_id="!room2:example.org",
    )
    room2_reply_service = Room2ReplyService(
        room2_id="!room2:example.org",
        decision_service=decision_service,
        membership_authorizer=sync_client,
    )

    next_since, routed_count = await poll_room2_reply_events_once(
        matrix_client=sync_client,
        room2_reply_service=room2_reply_service,
        message_repository=message_repository,
        room2_id="!room2:example.org",
        bot_user_id="@bot:example.org",
        since_token=None,
        sync_timeout_ms=5_000,
    )

    assert next_since == "s-room2-wrong-state"
    assert routed_count == 0
    assert len(sync_client.reply_calls) == 1
    error_body = sync_client.reply_calls[0][2]
    assert "resultado: erro" in error_body
    assert "codigo_erro: state_conflict" in error_body
    assert f"caso: {case_id}" in error_body


@pytest.mark.asyncio
async def test_runtime_listener_ignores_room2_message_without_reply_relation(
    tmp_path: Path,
) -> None:
    sync_url, async_url = _upgrade_head(tmp_path, "room2_reply_listener_non_reply.db")
    case_id, _root_event_id = await _setup_wait_doctor_case(
        async_url,
        origin_event_id="$origin-room2-listener-non-reply",
    )
    body = (
        "decision: accept\n"
        "support_flag: none\n"
        "reason: criterios atendidos\n"
        f"case_id: {case_id}"
    )
    sync_client = FakeMatrixRuntimeClient(
        _sync_payload(
            next_batch="s-room2-non-reply",
            room_id="!room2:example.org",
            events=[
                _room2_non_reply_message_event(
                    event_id="$doctor-room2-non-reply",
                    sender="@doctor:example.org",
                    body=body,
                )
            ],
        )
    )

    session_factory = create_session_factory(async_url)
    message_repository = SqlAlchemyMessageRepository(session_factory)
    decision_service = HandleDoctorDecisionService(
        case_repository=SqlAlchemyCaseRepository(session_factory),
        audit_repository=SqlAlchemyAuditRepository(session_factory),
        job_queue=SqlAlchemyJobQueueRepository(session_factory),
        message_repository=message_repository,
        matrix_poster=sync_client,
        room2_id="!room2:example.org",
    )
    room2_reply_service = Room2ReplyService(
        room2_id="!room2:example.org",
        decision_service=decision_service,
        membership_authorizer=sync_client,
    )

    next_since, routed_count = await poll_room2_reply_events_once(
        matrix_client=sync_client,
        room2_reply_service=room2_reply_service,
        message_repository=message_repository,
        room2_id="!room2:example.org",
        bot_user_id="@bot:example.org",
        since_token=None,
        sync_timeout_ms=5_000,
    )

    assert next_since == "s-room2-non-reply"
    assert routed_count == 0
    assert sync_client.reply_calls == []
    assert sync_client.send_calls == []

    engine = sa.create_engine(sync_url)
    with engine.begin() as connection:
        case_row = connection.execute(
            sa.text(
                "SELECT status, doctor_decision, doctor_support_flag, doctor_user_id "
                "FROM cases WHERE case_id = :case_id"
            ),
            {"case_id": case_id.hex},
        ).mappings().one()

    assert case_row["status"] == "WAIT_DOCTOR"
    assert case_row["doctor_decision"] is None
    assert case_row["doctor_support_flag"] is None
    assert case_row["doctor_user_id"] is None


@pytest.mark.asyncio
async def test_runtime_listener_ignores_reply_target_not_mapped_to_active_root(
    tmp_path: Path,
) -> None:
    sync_url, async_url = _upgrade_head(tmp_path, "room2_reply_listener_unmapped_target.db")
    case_id, _root_event_id = await _setup_wait_doctor_case(
        async_url,
        origin_event_id="$origin-room2-listener-unmapped-target",
    )
    body = (
        "decision: accept\n"
        "support_flag: none\n"
        "reason: criterios atendidos\n"
        f"case_id: {case_id}"
    )
    sync_client = FakeMatrixRuntimeClient(
        _sync_payload(
            next_batch="s-room2-unmapped-target",
            room_id="!room2:example.org",
            events=[
                _room2_reply_event(
                    event_id="$doctor-room2-unmapped-target",
                    sender="@doctor:example.org",
                    body=body,
                    reply_to_event_id="$unknown-room2-root",
                )
            ],
        )
    )

    session_factory = create_session_factory(async_url)
    message_repository = SqlAlchemyMessageRepository(session_factory)
    decision_service = HandleDoctorDecisionService(
        case_repository=SqlAlchemyCaseRepository(session_factory),
        audit_repository=SqlAlchemyAuditRepository(session_factory),
        job_queue=SqlAlchemyJobQueueRepository(session_factory),
        message_repository=message_repository,
        matrix_poster=sync_client,
        room2_id="!room2:example.org",
    )
    room2_reply_service = Room2ReplyService(
        room2_id="!room2:example.org",
        decision_service=decision_service,
        membership_authorizer=sync_client,
    )

    next_since, routed_count = await poll_room2_reply_events_once(
        matrix_client=sync_client,
        room2_reply_service=room2_reply_service,
        message_repository=message_repository,
        room2_id="!room2:example.org",
        bot_user_id="@bot:example.org",
        since_token=None,
        sync_timeout_ms=5_000,
    )

    assert next_since == "s-room2-unmapped-target"
    assert routed_count == 0
    assert sync_client.reply_calls == []
    assert sync_client.send_calls == []

    engine = sa.create_engine(sync_url)
    with engine.begin() as connection:
        case_row = connection.execute(
            sa.text(
                "SELECT status, doctor_decision, doctor_support_flag, doctor_user_id "
                "FROM cases WHERE case_id = :case_id"
            ),
            {"case_id": case_id.hex},
        ).mappings().one()

    assert case_row["status"] == "WAIT_DOCTOR"
    assert case_row["doctor_decision"] is None
    assert case_row["doctor_support_flag"] is None
    assert case_row["doctor_user_id"] is None


@pytest.mark.asyncio
async def test_runtime_listener_ignores_room2_reply_authored_by_bot_user(
    tmp_path: Path,
) -> None:
    sync_url, async_url = _upgrade_head(tmp_path, "room2_reply_listener_bot_sender.db")
    case_id, root_event_id = await _setup_wait_doctor_case(
        async_url,
        origin_event_id="$origin-room2-listener-bot-sender",
    )
    body = (
        "decision: accept\n"
        "support_flag: none\n"
        "reason: mensagem do proprio bot\n"
        f"case_id: {case_id}"
    )
    sync_client = FakeMatrixRuntimeClient(
        _sync_payload(
            next_batch="s-room2-bot-sender",
            room_id="!room2:example.org",
            events=[
                _room2_reply_event(
                    event_id="$bot-room2-reply",
                    sender="@bot:example.org",
                    body=body,
                    reply_to_event_id=root_event_id,
                )
            ],
        )
    )

    session_factory = create_session_factory(async_url)
    message_repository = SqlAlchemyMessageRepository(session_factory)
    decision_service = HandleDoctorDecisionService(
        case_repository=SqlAlchemyCaseRepository(session_factory),
        audit_repository=SqlAlchemyAuditRepository(session_factory),
        job_queue=SqlAlchemyJobQueueRepository(session_factory),
        message_repository=message_repository,
        matrix_poster=sync_client,
        room2_id="!room2:example.org",
    )
    room2_reply_service = Room2ReplyService(
        room2_id="!room2:example.org",
        decision_service=decision_service,
        membership_authorizer=sync_client,
    )

    next_since, routed_count = await poll_room2_reply_events_once(
        matrix_client=sync_client,
        room2_reply_service=room2_reply_service,
        message_repository=message_repository,
        room2_id="!room2:example.org",
        bot_user_id="@bot:example.org",
        since_token=None,
        sync_timeout_ms=5_000,
    )

    assert next_since == "s-room2-bot-sender"
    assert routed_count == 0
    assert sync_client.reply_calls == []
    assert sync_client.send_calls == []

    engine = sa.create_engine(sync_url)
    with engine.begin() as connection:
        case_row = connection.execute(
            sa.text(
                "SELECT status, doctor_decision, doctor_support_flag, doctor_user_id "
                "FROM cases WHERE case_id = :case_id"
            ),
            {"case_id": case_id.hex},
        ).mappings().one()

    assert case_row["status"] == "WAIT_DOCTOR"
    assert case_row["doctor_decision"] is None
    assert case_row["doctor_support_flag"] is None
    assert case_row["doctor_user_id"] is None

from __future__ import annotations

from pathlib import Path
from uuid import UUID, uuid4

import pytest
import sqlalchemy as sa
from alembic.config import Config

from alembic import command
from apps.bot_matrix.main import poll_room3_reply_events_once
from triage_automation.application.ports.case_repository_port import CaseCreateInput
from triage_automation.application.ports.message_repository_port import (
    CaseMessageCreateInput,
)
from triage_automation.application.services.room3_reply_service import (
    Room3ReplyEvent,
    Room3ReplyService,
)
from triage_automation.domain.case_status import CaseStatus
from triage_automation.infrastructure.db.audit_repository import SqlAlchemyAuditRepository
from triage_automation.infrastructure.db.case_repository import SqlAlchemyCaseRepository
from triage_automation.infrastructure.db.job_queue_repository import SqlAlchemyJobQueueRepository
from triage_automation.infrastructure.db.message_repository import SqlAlchemyMessageRepository
from triage_automation.infrastructure.db.session import create_session_factory


class _FakeSyncClient:
    def __init__(self, payload: dict[str, object]) -> None:
        self._payload = payload
        self.calls: list[tuple[str | None, int]] = []

    async def sync(self, *, since: str | None, timeout_ms: int) -> dict[str, object]:
        self.calls.append((since, timeout_ms))
        return self._payload

    async def reply_text(self, *, room_id: str, event_id: str, body: str) -> str:
        _ = room_id, event_id, body
        raise AssertionError("reply_text should not be called on _FakeSyncClient")

    async def send_text(self, *, room_id: str, body: str) -> str:
        _ = room_id, body
        raise AssertionError("send_text should not be called on _FakeSyncClient")


class FakeMatrixPoster:
    def __init__(self) -> None:
        self.reply_calls: list[tuple[str, str, str]] = []
        self._counter = 0

    async def reply_text(self, *, room_id: str, event_id: str, body: str) -> str:
        self.reply_calls.append((room_id, event_id, body))
        self._counter += 1
        return f"$reprompt-{self._counter}"


def _upgrade_head(tmp_path: Path, filename: str) -> tuple[str, str]:
    db_path = tmp_path / filename
    sync_url = f"sqlite+pysqlite:///{db_path}"
    async_url = f"sqlite+aiosqlite:///{db_path}"

    alembic_config = Config("alembic.ini")
    alembic_config.set_main_option("sqlalchemy.url", sync_url)
    command.upgrade(alembic_config, "head")

    return sync_url, async_url


async def _setup_wait_appt_case(async_url: str, *, origin_event_id: str) -> tuple[UUID, str]:
    session_factory = create_session_factory(async_url)
    case_repo = SqlAlchemyCaseRepository(session_factory)
    message_repo = SqlAlchemyMessageRepository(session_factory)

    case = await case_repo.create_case(
        CaseCreateInput(
            case_id=uuid4(),
            status=CaseStatus.WAIT_APPT,
            room1_origin_room_id="!room1:example.org",
            room1_origin_event_id=origin_event_id,
            room1_sender_user_id="@human:example.org",
        )
    )

    request_event_id = "$room3-request"
    await message_repo.add_message(
        CaseMessageCreateInput(
            case_id=case.case_id,
            room_id="!room3:example.org",
            event_id=request_event_id,
            kind="room3_request",
            sender_user_id=None,
        )
    )

    return case.case_id, request_event_id


def _build_service(async_url: str, matrix_poster: FakeMatrixPoster) -> Room3ReplyService:
    session_factory = create_session_factory(async_url)
    return Room3ReplyService(
        room3_id="!room3:example.org",
        case_repository=SqlAlchemyCaseRepository(session_factory),
        audit_repository=SqlAlchemyAuditRepository(session_factory),
        message_repository=SqlAlchemyMessageRepository(session_factory),
        job_queue=SqlAlchemyJobQueueRepository(session_factory),
        matrix_poster=matrix_poster,
    )


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


def _room3_reply_event(
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


@pytest.mark.asyncio
async def test_non_reply_or_wrong_target_is_ignored(tmp_path: Path) -> None:
    sync_url, async_url = _upgrade_head(tmp_path, "room3_ignore.db")
    case_id, _ = await _setup_wait_appt_case(async_url, origin_event_id="$origin-room3-1")
    matrix_poster = FakeMatrixPoster()
    service = _build_service(async_url, matrix_poster)

    result = await service.handle_reply(
        Room3ReplyEvent(
            room_id="!room3:example.org",
            event_id="$scheduler-1",
            sender_user_id="@scheduler:example.org",
            body="denied\nreason: x\ncase: 00000000-0000-0000-0000-000000000000",
            reply_to_event_id=None,
        )
    )

    assert result.processed is False
    assert result.reason == "not_reply"
    assert matrix_poster.reply_calls == []

    engine = sa.create_engine(sync_url)
    with engine.begin() as connection:
        status = connection.execute(
            sa.text("SELECT status FROM cases WHERE case_id = :case_id"),
            {"case_id": case_id.hex},
        ).scalar_one()
    assert status == "WAIT_APPT"


@pytest.mark.asyncio
async def test_case_mismatch_is_audited_and_no_next_job_enqueued(tmp_path: Path) -> None:
    sync_url, async_url = _upgrade_head(tmp_path, "room3_case_mismatch.db")
    case_id, request_event_id = await _setup_wait_appt_case(
        async_url,
        origin_event_id="$origin-room3-2",
    )
    matrix_poster = FakeMatrixPoster()
    service = _build_service(async_url, matrix_poster)

    result = await service.handle_reply(
        Room3ReplyEvent(
            room_id="!room3:example.org",
            event_id="$scheduler-2",
            sender_user_id="@scheduler:example.org",
            body=f"denied\nreason: sem agenda\ncase: {uuid4()}",
            reply_to_event_id=request_event_id,
        )
    )

    assert result.processed is False
    assert result.reason == "invalid_template"

    engine = sa.create_engine(sync_url)
    with engine.begin() as connection:
        status = connection.execute(
            sa.text("SELECT status FROM cases WHERE case_id = :case_id"),
            {"case_id": case_id.hex},
        ).scalar_one()
        audit_events = connection.execute(
            sa.text(
                "SELECT COUNT(*) FROM case_events WHERE case_id = :case_id "
                "AND event_type = 'ROOM3_TEMPLATE_INVALID_CASE_LINE'"
            ),
            {"case_id": case_id.hex},
        ).scalar_one()
        job_count = connection.execute(
            sa.text("SELECT COUNT(*) FROM jobs WHERE case_id = :case_id"),
            {"case_id": case_id.hex},
        ).scalar_one()

    assert status == "WAIT_APPT"
    assert int(audit_events) == 1
    assert int(job_count) == 0


@pytest.mark.asyncio
async def test_invalid_format_reprompts_and_keeps_wait_appt(tmp_path: Path) -> None:
    sync_url, async_url = _upgrade_head(tmp_path, "room3_invalid_format.db")
    case_id, request_event_id = await _setup_wait_appt_case(
        async_url,
        origin_event_id="$origin-room3-3",
    )
    matrix_poster = FakeMatrixPoster()
    service = _build_service(async_url, matrix_poster)

    result = await service.handle_reply(
        Room3ReplyEvent(
            room_id="!room3:example.org",
            event_id="$scheduler-3",
            sender_user_id="@scheduler:example.org",
            body=f"hello\ncase: {case_id}",
            reply_to_event_id=request_event_id,
        )
    )

    assert result.processed is False
    assert result.reason == "invalid_template"
    assert len(matrix_poster.reply_calls) == 1
    assert matrix_poster.reply_calls[0][1] == "$scheduler-3"

    engine = sa.create_engine(sync_url)
    with engine.begin() as connection:
        status = connection.execute(
            sa.text("SELECT status FROM cases WHERE case_id = :case_id"),
            {"case_id": case_id.hex},
        ).scalar_one()
        reprompt_count = connection.execute(
            sa.text(
                "SELECT COUNT(*) FROM case_messages WHERE case_id = :case_id "
                "AND kind = 'bot_reformat_prompt_room3'"
            ),
            {"case_id": case_id.hex},
        ).scalar_one()

    assert status == "WAIT_APPT"
    assert int(reprompt_count) == 1


@pytest.mark.asyncio
async def test_confirmed_template_enqueues_final_appointment_job(tmp_path: Path) -> None:
    sync_url, async_url = _upgrade_head(tmp_path, "room3_confirmed.db")
    case_id, request_event_id = await _setup_wait_appt_case(
        async_url,
        origin_event_id="$origin-room3-4",
    )
    matrix_poster = FakeMatrixPoster()
    service = _build_service(async_url, matrix_poster)

    body = (
        "Confirmed:\n"
        "16-02-2026 14:30 BRT\n"
        "location: Sala 2\n"
        "instructions: Jejum 8h\n"
        f"case: {case_id}"
    )

    result = await service.handle_reply(
        Room3ReplyEvent(
            room_id="!room3:example.org",
            event_id="$scheduler-4",
            sender_user_id="@scheduler:example.org",
            body=body,
            reply_to_event_id=request_event_id,
        )
    )

    assert result.processed is True
    assert len(matrix_poster.reply_calls) == 1
    assert matrix_poster.reply_calls[0][1] == "$scheduler-4"
    assert "Reaja com +1 para confirmar." in matrix_poster.reply_calls[0][2]

    engine = sa.create_engine(sync_url)
    with engine.begin() as connection:
        status = connection.execute(
            sa.text("SELECT status FROM cases WHERE case_id = :case_id"),
            {"case_id": case_id.hex},
        ).scalar_one()
        job_type = connection.execute(
            sa.text(
                "SELECT job_type FROM jobs WHERE case_id = :case_id "
                "ORDER BY job_id DESC LIMIT 1"
            ),
            {"case_id": case_id.hex},
        ).scalar_one()
        ack_count = connection.execute(
            sa.text(
                "SELECT COUNT(*) FROM case_messages WHERE case_id = :case_id "
                "AND kind = 'bot_ack'"
            ),
            {"case_id": case_id.hex},
        ).scalar_one()
        scheduler_reply_count = connection.execute(
            sa.text(
                "SELECT COUNT(*) FROM case_messages WHERE case_id = :case_id "
                "AND kind = 'room3_reply'"
            ),
            {"case_id": case_id.hex},
        ).scalar_one()
        transcript_rows = connection.execute(
            sa.text(
                "SELECT message_type, sender, message_text, reply_to_event_id "
                "FROM case_matrix_message_transcripts "
                "WHERE case_id = :case_id "
                "AND message_type IN ('room3_reply', 'bot_ack') "
                "ORDER BY id"
            ),
            {"case_id": case_id.hex},
        ).mappings().all()

    assert status == "APPT_CONFIRMED"
    assert job_type == "post_room1_final_appt"
    assert int(ack_count) == 1
    assert int(scheduler_reply_count) == 1
    assert len(transcript_rows) == 2
    assert transcript_rows[0]["message_type"] == "room3_reply"
    assert transcript_rows[0]["sender"] == "@scheduler:example.org"
    assert transcript_rows[0]["message_text"] == body
    assert transcript_rows[0]["reply_to_event_id"] == request_event_id
    assert transcript_rows[1]["message_type"] == "bot_ack"
    assert transcript_rows[1]["sender"] == "bot"
    assert transcript_rows[1]["message_text"] == matrix_poster.reply_calls[0][2]
    assert transcript_rows[1]["reply_to_event_id"] == "$scheduler-4"


@pytest.mark.asyncio
async def test_status_template_reply_to_room3_template_message_is_accepted(tmp_path: Path) -> None:
    sync_url, async_url = _upgrade_head(tmp_path, "room3_status_template_reply.db")
    case_id, _request_event_id = await _setup_wait_appt_case(
        async_url,
        origin_event_id="$origin-room3-status-template",
    )
    template_event_id = "$room3-template"
    session_factory = create_session_factory(async_url)
    message_repository = SqlAlchemyMessageRepository(session_factory)
    await message_repository.add_message(
        CaseMessageCreateInput(
            case_id=case_id,
            room_id="!room3:example.org",
            event_id=template_event_id,
            kind="room3_template",
            sender_user_id=None,
        )
    )
    matrix_poster = FakeMatrixPoster()
    service = _build_service(async_url, matrix_poster)

    body = (
        "status: confirmado\n"
        "data_hora: 16-02-2026 14:30 BRT\n"
        "local: Sala 2\n"
        "instrucoes: Jejum 8h\n"
        "motivo: (opcional)\n"
        f"caso: {case_id}"
    )
    result = await service.handle_reply(
        Room3ReplyEvent(
            room_id="!room3:example.org",
            event_id="$scheduler-status-template-1",
            sender_user_id="@scheduler:example.org",
            body=body,
            reply_to_event_id=template_event_id,
        )
    )

    assert result.processed is True
    assert len(matrix_poster.reply_calls) == 1
    assert matrix_poster.reply_calls[0][1] == "$scheduler-status-template-1"
    assert "Reaja com +1 para confirmar." in matrix_poster.reply_calls[0][2]

    engine = sa.create_engine(sync_url)
    with engine.begin() as connection:
        status = connection.execute(
            sa.text("SELECT status FROM cases WHERE case_id = :case_id"),
            {"case_id": case_id.hex},
        ).scalar_one()
        job_type = connection.execute(
            sa.text(
                "SELECT job_type FROM jobs WHERE case_id = :case_id "
                "ORDER BY job_id DESC LIMIT 1"
            ),
            {"case_id": case_id.hex},
        ).scalar_one()
        ack_count = connection.execute(
            sa.text(
                "SELECT COUNT(*) FROM case_messages WHERE case_id = :case_id "
                "AND kind = 'bot_ack'"
            ),
            {"case_id": case_id.hex},
        ).scalar_one()

    assert status == "APPT_CONFIRMED"
    assert job_type == "post_room1_final_appt"
    assert int(ack_count) == 1


@pytest.mark.asyncio
async def test_runtime_listener_routes_valid_room3_reply_to_service(tmp_path: Path) -> None:
    sync_url, async_url = _upgrade_head(tmp_path, "room3_listener_valid.db")
    case_id, request_event_id = await _setup_wait_appt_case(
        async_url,
        origin_event_id="$origin-room3-listener-valid",
    )
    matrix_poster = FakeMatrixPoster()
    service = _build_service(async_url, matrix_poster)

    body = (
        "Confirmed:\n"
        "16-02-2026 14:30 BRT\n"
        "location: Sala 2\n"
        "instructions: Jejum 8h\n"
        f"case: {case_id}"
    )
    sync_client = _FakeSyncClient(
        _sync_payload(
            next_batch="s-room3-valid",
            room_id="!room3:example.org",
            events=[
                _room3_reply_event(
                    event_id="$scheduler-listener-valid",
                    sender="@scheduler:example.org",
                    body=body,
                    reply_to_event_id=request_event_id,
                )
            ],
        )
    )

    next_since, routed_count = await poll_room3_reply_events_once(
        matrix_client=sync_client,
        room3_reply_service=service,
        room3_id="!room3:example.org",
        bot_user_id="@bot:example.org",
        since_token=None,
        sync_timeout_ms=5_000,
    )

    assert next_since == "s-room3-valid"
    assert routed_count == 1
    assert len(matrix_poster.reply_calls) == 1
    assert matrix_poster.reply_calls[0][1] == "$scheduler-listener-valid"
    assert "Reaja com +1 para confirmar." in matrix_poster.reply_calls[0][2]

    engine = sa.create_engine(sync_url)
    with engine.begin() as connection:
        status = connection.execute(
            sa.text("SELECT status FROM cases WHERE case_id = :case_id"),
            {"case_id": case_id.hex},
        ).scalar_one()
        job_type = connection.execute(
            sa.text(
                "SELECT job_type FROM jobs WHERE case_id = :case_id "
                "ORDER BY job_id DESC LIMIT 1"
            ),
            {"case_id": case_id.hex},
        ).scalar_one()
        ack_count = connection.execute(
            sa.text(
                "SELECT COUNT(*) FROM case_messages WHERE case_id = :case_id "
                "AND kind = 'bot_ack'"
            ),
            {"case_id": case_id.hex},
        ).scalar_one()

    assert status == "APPT_CONFIRMED"
    assert job_type == "post_room1_final_appt"
    assert int(ack_count) == 1


@pytest.mark.asyncio
async def test_runtime_listener_invalid_template_reprompts_and_keeps_wait_appt(
    tmp_path: Path,
) -> None:
    sync_url, async_url = _upgrade_head(tmp_path, "room3_listener_invalid.db")
    case_id, request_event_id = await _setup_wait_appt_case(
        async_url,
        origin_event_id="$origin-room3-listener-invalid",
    )
    matrix_poster = FakeMatrixPoster()
    service = _build_service(async_url, matrix_poster)

    sync_client = _FakeSyncClient(
        _sync_payload(
            next_batch="s-room3-invalid",
            room_id="!room3:example.org",
            events=[
                _room3_reply_event(
                    event_id="$scheduler-listener-invalid",
                    sender="@scheduler:example.org",
                    body=f"hello\ncase: {case_id}",
                    reply_to_event_id=request_event_id,
                )
            ],
        )
    )

    next_since, routed_count = await poll_room3_reply_events_once(
        matrix_client=sync_client,
        room3_reply_service=service,
        room3_id="!room3:example.org",
        bot_user_id="@bot:example.org",
        since_token="s-prev",
        sync_timeout_ms=5_000,
    )

    assert next_since == "s-room3-invalid"
    assert routed_count == 1
    assert len(matrix_poster.reply_calls) == 1
    assert matrix_poster.reply_calls[0][1] == "$scheduler-listener-invalid"

    engine = sa.create_engine(sync_url)
    with engine.begin() as connection:
        status = connection.execute(
            sa.text("SELECT status FROM cases WHERE case_id = :case_id"),
            {"case_id": case_id.hex},
        ).scalar_one()
        reprompt_count = connection.execute(
            sa.text(
                "SELECT COUNT(*) FROM case_messages WHERE case_id = :case_id "
                "AND kind = 'bot_reformat_prompt_room3'"
            ),
            {"case_id": case_id.hex},
        ).scalar_one()

    assert status == "WAIT_APPT"
    assert int(reprompt_count) == 1

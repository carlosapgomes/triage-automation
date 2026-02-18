from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

import pytest
import sqlalchemy as sa
from alembic.config import Config

from alembic import command
from triage_automation.application.ports.audit_repository_port import AuditEventCreateInput
from triage_automation.application.ports.case_repository_port import (
    CaseCreateInput,
    DuplicateCaseOriginEventError,
)
from triage_automation.application.ports.message_repository_port import (
    CaseMessageCreateInput,
    DuplicateCaseMessageError,
)
from triage_automation.domain.case_status import CaseStatus
from triage_automation.infrastructure.db.audit_repository import SqlAlchemyAuditRepository
from triage_automation.infrastructure.db.case_repository import SqlAlchemyCaseRepository
from triage_automation.infrastructure.db.message_repository import SqlAlchemyMessageRepository
from triage_automation.infrastructure.db.session import create_session_factory


def _upgrade_head(tmp_path: Path, filename: str) -> tuple[str, str]:
    db_path = tmp_path / filename
    sync_url = f"sqlite+pysqlite:///{db_path}"
    async_url = f"sqlite+aiosqlite:///{db_path}"

    alembic_config = Config("alembic.ini")
    alembic_config.set_main_option("sqlalchemy.url", sync_url)
    command.upgrade(alembic_config, "head")

    return sync_url, async_url


@pytest.mark.asyncio
async def test_case_insert_works(tmp_path: Path) -> None:
    _, async_url = _upgrade_head(tmp_path, "case_insert.db")
    session_factory = create_session_factory(async_url)
    repo = SqlAlchemyCaseRepository(session_factory)

    case_id = uuid4()
    created = await repo.create_case(
        CaseCreateInput(
            case_id=case_id,
            status=CaseStatus.NEW,
            room1_origin_room_id="!room1:example.org",
            room1_origin_event_id="$event-1",
            room1_sender_user_id="@human:example.org",
        )
    )

    loaded = await repo.get_case_by_origin_event_id("$event-1")

    assert created.case_id == case_id
    assert loaded is not None
    assert loaded.case_id == case_id
    assert loaded.status is CaseStatus.NEW


@pytest.mark.asyncio
async def test_duplicate_room1_origin_event_is_handled_deterministically(tmp_path: Path) -> None:
    _, async_url = _upgrade_head(tmp_path, "case_duplicate.db")
    session_factory = create_session_factory(async_url)
    repo = SqlAlchemyCaseRepository(session_factory)

    payload = CaseCreateInput(
        case_id=uuid4(),
        status=CaseStatus.NEW,
        room1_origin_room_id="!room1:example.org",
        room1_origin_event_id="$event-dup",
        room1_sender_user_id="@human:example.org",
    )

    await repo.create_case(payload)

    with pytest.raises(DuplicateCaseOriginEventError):
        await repo.create_case(
            CaseCreateInput(
                case_id=uuid4(),
                status=payload.status,
                room1_origin_room_id=payload.room1_origin_room_id,
                room1_origin_event_id=payload.room1_origin_event_id,
                room1_sender_user_id=payload.room1_sender_user_id,
            )
        )


@pytest.mark.asyncio
async def test_append_only_audit_event_persistence(tmp_path: Path) -> None:
    sync_url, async_url = _upgrade_head(tmp_path, "audit_insert.db")
    session_factory = create_session_factory(async_url)
    case_repo = SqlAlchemyCaseRepository(session_factory)
    audit_repo = SqlAlchemyAuditRepository(session_factory)

    case_id = uuid4()
    await case_repo.create_case(
        CaseCreateInput(
            case_id=case_id,
            status=CaseStatus.NEW,
            room1_origin_room_id="!room1:example.org",
            room1_origin_event_id="$event-audit",
            room1_sender_user_id="@human:example.org",
        )
    )

    event_id = await audit_repo.append_event(
        AuditEventCreateInput(
            case_id=case_id,
            actor_type="system",
            event_type="CASE_CREATED",
            payload={"source": "test"},
        )
    )

    engine = sa.create_engine(sync_url)
    with engine.begin() as connection:
        row = connection.execute(
            sa.text("SELECT id, case_id, event_type FROM case_events WHERE id = :id"),
            {"id": event_id},
        ).mappings().one()

    assert row["id"] == event_id
    assert UUID(str(row["case_id"])) == case_id
    assert row["event_type"] == "CASE_CREATED"


@pytest.mark.asyncio
async def test_duplicate_case_message_room_event_is_rejected_safely(tmp_path: Path) -> None:
    sync_url, async_url = _upgrade_head(tmp_path, "message_duplicate.db")
    session_factory = create_session_factory(async_url)
    case_repo = SqlAlchemyCaseRepository(session_factory)
    message_repo = SqlAlchemyMessageRepository(session_factory)

    case_id = uuid4()
    await case_repo.create_case(
        CaseCreateInput(
            case_id=case_id,
            status=CaseStatus.NEW,
            room1_origin_room_id="!room1:example.org",
            room1_origin_event_id="$event-message",
            room1_sender_user_id="@human:example.org",
        )
    )

    await message_repo.add_message(
        CaseMessageCreateInput(
            case_id=case_id,
            room_id="!room1:example.org",
            event_id="$message-1",
            sender_user_id="@bot:example.org",
            kind="bot_processing",
        )
    )

    with pytest.raises(DuplicateCaseMessageError):
        await message_repo.add_message(
            CaseMessageCreateInput(
                case_id=case_id,
                room_id="!room1:example.org",
                event_id="$message-1",
                sender_user_id="@bot:example.org",
                kind="bot_processing",
            )
        )

    engine = sa.create_engine(sync_url)
    with engine.begin() as connection:
        count = connection.execute(
            sa.text(
                "SELECT COUNT(*) FROM case_messages "
                "WHERE room_id = :room_id AND event_id = :event_id"
            ),
            {"room_id": "!room1:example.org", "event_id": "$message-1"},
        ).scalar_one()

    assert count == 1


@pytest.mark.asyncio
async def test_full_transcript_persistence_and_chronological_timeline_per_case(
    tmp_path: Path,
) -> None:
    sync_url, async_url = _upgrade_head(tmp_path, "full_transcript_timeline_case.db")
    session_factory = create_session_factory(async_url)
    case_repo = SqlAlchemyCaseRepository(session_factory)

    target_case_id = uuid4()
    other_case_id = uuid4()
    await case_repo.create_case(
        CaseCreateInput(
            case_id=target_case_id,
            status=CaseStatus.WAIT_DOCTOR,
            room1_origin_room_id="!room1:example.org",
            room1_origin_event_id="$event-target-case",
            room1_sender_user_id="@human:example.org",
        )
    )
    await case_repo.create_case(
        CaseCreateInput(
            case_id=other_case_id,
            status=CaseStatus.WAIT_DOCTOR,
            room1_origin_room_id="!room1:example.org",
            room1_origin_event_id="$event-other-case",
            room1_sender_user_id="@human:example.org",
        )
    )

    base = datetime(2026, 2, 18, 9, 0, 0, tzinfo=UTC)
    engine = sa.create_engine(sync_url)
    with engine.begin() as connection:
        connection.execute(
            sa.text(
                "INSERT INTO case_llm_interactions ("
                "case_id, stage, input_payload, output_payload, "
                "prompt_system_name, prompt_system_version, "
                "prompt_user_name, prompt_user_version, model_name, captured_at"
                ") VALUES ("
                ":case_id, 'LLM2', :input_payload, :output_payload, "
                "'llm2_system', 7, 'llm2_user', 8, 'gpt-4o-mini', :captured_at"
                ")"
            ),
            {
                "case_id": target_case_id.hex,
                "captured_at": base,
                "input_payload": '{"input":{"a":1,"b":["x","y"]}}',
                "output_payload": '{"output":{"decision":"accept","score":0.91}}',
            },
        )
        connection.execute(
            sa.text(
                "INSERT INTO case_report_transcripts (case_id, extracted_text, captured_at) "
                "VALUES (:case_id, :extracted_text, :captured_at)"
            ),
            {
                "case_id": target_case_id.hex,
                "captured_at": base + timedelta(minutes=5),
                "extracted_text": "relatorio completo alvo",
            },
        )
        connection.execute(
            sa.text(
                "INSERT INTO case_matrix_message_transcripts ("
                "case_id, room_id, event_id, sender, message_type, message_text, "
                "reply_to_event_id, captured_at"
                ") VALUES ("
                ":case_id, '!room2:example.org', :event_id, '@doctor:example.org', "
                "'room2_doctor_reply', 'decisao: aceitar', :reply_to_event_id, :captured_at"
                ")"
            ),
            {
                "case_id": target_case_id.hex,
                "captured_at": base + timedelta(minutes=10),
                "event_id": "$evt-target-reply",
                "reply_to_event_id": "$evt-target-root",
            },
        )
        connection.execute(
            sa.text(
                "INSERT INTO case_report_transcripts (case_id, extracted_text, captured_at) "
                "VALUES (:case_id, :extracted_text, :captured_at)"
            ),
            {
                "case_id": other_case_id.hex,
                "captured_at": base + timedelta(minutes=2),
                "extracted_text": "relatorio completo outro caso",
            },
        )

    detail = await case_repo.get_case_monitoring_detail(case_id=target_case_id)

    assert detail is not None
    assert detail.case_id == target_case_id
    assert [item.source for item in detail.timeline] == ["llm", "pdf", "matrix"]
    assert [item.event_type for item in detail.timeline] == [
        "LLM2",
        "pdf_report_extracted",
        "room2_doctor_reply",
    ]
    assert detail.timeline[0].payload == {
        "input_payload": {"input": {"a": 1, "b": ["x", "y"]}},
        "output_payload": {"output": {"decision": "accept", "score": 0.91}},
        "prompt_system_name": "llm2_system",
        "prompt_system_version": 7,
        "prompt_user_name": "llm2_user",
        "prompt_user_version": 8,
        "model_name": "gpt-4o-mini",
    }
    assert detail.timeline[1].content_text == "relatorio completo alvo"
    assert detail.timeline[2].content_text == "decisao: aceitar"
    assert detail.timeline[2].payload == {
        "event_id": "$evt-target-reply",
        "reply_to_event_id": "$evt-target-root",
    }

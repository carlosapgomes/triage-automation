from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.config import Config

from alembic import command
from triage_automation.application.services.room1_intake_service import Room1IntakeService
from triage_automation.infrastructure.db.audit_repository import SqlAlchemyAuditRepository
from triage_automation.infrastructure.db.case_repository import SqlAlchemyCaseRepository
from triage_automation.infrastructure.db.job_queue_repository import SqlAlchemyJobQueueRepository
from triage_automation.infrastructure.db.message_repository import SqlAlchemyMessageRepository
from triage_automation.infrastructure.db.session import create_session_factory
from triage_automation.infrastructure.matrix.event_parser import parse_room1_pdf_intake_event


class FakeMatrixPoster:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, str]] = []
        self._counter = 0

    async def reply_text(self, *, room_id: str, event_id: str, body: str) -> str:
        self.calls.append((room_id, event_id, body))
        self._counter += 1
        return f"$processing-{self._counter}"


def _upgrade_head(tmp_path: Path, filename: str) -> tuple[str, str]:
    db_path = tmp_path / filename
    sync_url = f"sqlite+pysqlite:///{db_path}"
    async_url = f"sqlite+aiosqlite:///{db_path}"

    alembic_config = Config("alembic.ini")
    alembic_config.set_main_option("sqlalchemy.url", sync_url)
    command.upgrade(alembic_config, "head")

    return sync_url, async_url


def _make_raw_pdf_event(event_id: str) -> dict[str, object]:
    return {
        "event_id": event_id,
        "sender": "@human:example.org",
        "content": {
            "msgtype": "m.file",
            "body": "intake.pdf",
            "url": "mxc://example.org/pdf",
            "info": {"mimetype": "application/pdf"},
        },
    }


@pytest.mark.asyncio
async def test_valid_pdf_creates_case_and_enqueues_job(tmp_path: Path) -> None:
    sync_url, async_url = _upgrade_head(tmp_path, "intake_valid.db")
    session_factory = create_session_factory(async_url)
    matrix_poster = FakeMatrixPoster()

    service = Room1IntakeService(
        case_repository=SqlAlchemyCaseRepository(session_factory),
        audit_repository=SqlAlchemyAuditRepository(session_factory),
        message_repository=SqlAlchemyMessageRepository(session_factory),
        job_queue=SqlAlchemyJobQueueRepository(session_factory),
        matrix_poster=matrix_poster,
    )

    parsed = parse_room1_pdf_intake_event(
        room_id="!room1:example.org",
        event=_make_raw_pdf_event("$origin-1"),
        bot_user_id="@bot:example.org",
    )
    assert parsed is not None

    result = await service.ingest_pdf_event(parsed)

    assert result.processed is True
    assert result.case_id is not None
    assert matrix_poster.calls == [("!room1:example.org", "$origin-1", "processing...")]

    engine = sa.create_engine(sync_url)
    with engine.begin() as connection:
        case_count = connection.execute(sa.text("SELECT COUNT(*) FROM cases")).scalar_one()
        job_count = connection.execute(
            sa.text("SELECT COUNT(*) FROM jobs WHERE job_type = 'process_pdf_case'")
        )
        message_kinds = connection.execute(
            sa.text("SELECT kind FROM case_messages ORDER BY id")
        ).scalars().all()

    assert int(case_count) == 1
    assert int(job_count.scalar_one()) == 1
    assert list(message_kinds) == ["room1_origin", "bot_processing"]


@pytest.mark.asyncio
async def test_duplicate_intake_event_is_ignored(tmp_path: Path) -> None:
    sync_url, async_url = _upgrade_head(tmp_path, "intake_duplicate.db")
    session_factory = create_session_factory(async_url)
    matrix_poster = FakeMatrixPoster()

    service = Room1IntakeService(
        case_repository=SqlAlchemyCaseRepository(session_factory),
        audit_repository=SqlAlchemyAuditRepository(session_factory),
        message_repository=SqlAlchemyMessageRepository(session_factory),
        job_queue=SqlAlchemyJobQueueRepository(session_factory),
        matrix_poster=matrix_poster,
    )

    parsed = parse_room1_pdf_intake_event(
        room_id="!room1:example.org",
        event=_make_raw_pdf_event("$origin-dup"),
        bot_user_id="@bot:example.org",
    )
    assert parsed is not None

    first = await service.ingest_pdf_event(parsed)
    second = await service.ingest_pdf_event(parsed)

    assert first.processed is True
    assert second.processed is False
    assert second.reason == "duplicate_origin_event"

    engine = sa.create_engine(sync_url)
    with engine.begin() as connection:
        case_count = connection.execute(sa.text("SELECT COUNT(*) FROM cases")).scalar_one()
        job_count = connection.execute(sa.text("SELECT COUNT(*) FROM jobs")).scalar_one()

    assert int(case_count) == 1
    assert int(job_count) == 1
    assert len(matrix_poster.calls) == 1


@pytest.mark.asyncio
async def test_concurrent_same_event_creates_single_case(tmp_path: Path) -> None:
    sync_url, async_url = _upgrade_head(tmp_path, "intake_race.db")
    session_factory = create_session_factory(async_url)
    matrix_poster = FakeMatrixPoster()

    service = Room1IntakeService(
        case_repository=SqlAlchemyCaseRepository(session_factory),
        audit_repository=SqlAlchemyAuditRepository(session_factory),
        message_repository=SqlAlchemyMessageRepository(session_factory),
        job_queue=SqlAlchemyJobQueueRepository(session_factory),
        matrix_poster=matrix_poster,
    )

    parsed = parse_room1_pdf_intake_event(
        room_id="!room1:example.org",
        event=_make_raw_pdf_event("$origin-race"),
        bot_user_id="@bot:example.org",
    )
    assert parsed is not None

    first, second = await asyncio.gather(
        service.ingest_pdf_event(parsed),
        service.ingest_pdf_event(parsed),
    )

    assert {first.processed, second.processed} == {True, False}

    engine = sa.create_engine(sync_url)
    with engine.begin() as connection:
        case_count = connection.execute(sa.text("SELECT COUNT(*) FROM cases")).scalar_one()
        job_count = connection.execute(sa.text("SELECT COUNT(*) FROM jobs")).scalar_one()

    assert int(case_count) == 1
    assert int(job_count) == 1
    assert len(matrix_poster.calls) == 1

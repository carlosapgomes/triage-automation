from __future__ import annotations

from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.config import Config

from alembic import command
from apps.bot_matrix.main import poll_room1_intake_once
from triage_automation.application.services.room1_intake_service import Room1IntakeService
from triage_automation.infrastructure.db.audit_repository import SqlAlchemyAuditRepository
from triage_automation.infrastructure.db.case_repository import SqlAlchemyCaseRepository
from triage_automation.infrastructure.db.job_queue_repository import SqlAlchemyJobQueueRepository
from triage_automation.infrastructure.db.message_repository import SqlAlchemyMessageRepository
from triage_automation.infrastructure.db.session import create_session_factory


class FakeMatrixRuntimeClient:
    def __init__(self, sync_payloads: list[dict[str, object]]) -> None:
        self._sync_payloads = list(sync_payloads)
        self.sync_calls: list[tuple[str | None, int]] = []
        self.reply_calls: list[tuple[str, str, str]] = []
        self._counter = 0

    async def sync(self, *, since: str | None, timeout_ms: int) -> dict[str, object]:
        self.sync_calls.append((since, timeout_ms))
        if self._sync_payloads:
            return self._sync_payloads.pop(0)
        return {"next_batch": since or "s-idle", "rooms": {"join": {}}}

    async def reply_text(self, *, room_id: str, event_id: str, body: str) -> str:
        self.reply_calls.append((room_id, event_id, body))
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


def _make_pdf_event(event_id: str) -> dict[str, object]:
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


def _build_room1_sync_payload(
    *,
    next_batch: str,
    events: list[dict[str, object]],
) -> dict[str, object]:
    return {
        "next_batch": next_batch,
        "rooms": {
            "join": {
                "!room1:example.org": {
                    "timeline": {
                        "events": events,
                    }
                }
            }
        },
    }


def _build_intake_service(
    async_url: str,
    matrix_client: FakeMatrixRuntimeClient,
) -> Room1IntakeService:
    session_factory = create_session_factory(async_url)
    return Room1IntakeService(
        case_repository=SqlAlchemyCaseRepository(session_factory),
        audit_repository=SqlAlchemyAuditRepository(session_factory),
        message_repository=SqlAlchemyMessageRepository(session_factory),
        job_queue=SqlAlchemyJobQueueRepository(session_factory),
        matrix_poster=matrix_client,
    )


@pytest.mark.asyncio
async def test_valid_room1_pdf_event_routes_through_runtime_listener(tmp_path: Path) -> None:
    sync_url, async_url = _upgrade_head(tmp_path, "bot_matrix_runtime_room1_valid.db")
    matrix_client = FakeMatrixRuntimeClient(
        [
            _build_room1_sync_payload(
                next_batch="s1",
                events=[_make_pdf_event("$origin-1")],
            )
        ]
    )
    intake_service = _build_intake_service(async_url, matrix_client)

    next_since, routed_count = await poll_room1_intake_once(
        matrix_client=matrix_client,
        intake_service=intake_service,
        room1_id="!room1:example.org",
        bot_user_id="@bot:example.org",
        since_token=None,
        sync_timeout_ms=5_000,
    )

    assert next_since == "s1"
    assert routed_count == 1
    assert matrix_client.reply_calls == [("!room1:example.org", "$origin-1", "processing...")]

    engine = sa.create_engine(sync_url)
    with engine.begin() as connection:
        case_count = connection.execute(sa.text("SELECT COUNT(*) FROM cases")).scalar_one()
        job_count = connection.execute(sa.text("SELECT COUNT(*) FROM jobs")).scalar_one()

    assert int(case_count) == 1
    assert int(job_count) == 1


@pytest.mark.asyncio
async def test_unsupported_events_are_ignored_by_runtime_listener(tmp_path: Path) -> None:
    sync_url, async_url = _upgrade_head(tmp_path, "bot_matrix_runtime_room1_ignored.db")
    matrix_client = FakeMatrixRuntimeClient(
        [
            _build_room1_sync_payload(
                next_batch="s2",
                events=[
                    {
                        "event_id": "$msg-1",
                        "sender": "@human:example.org",
                        "content": {"msgtype": "m.text", "body": "hello"},
                    }
                ],
            )
        ]
    )
    intake_service = _build_intake_service(async_url, matrix_client)

    next_since, routed_count = await poll_room1_intake_once(
        matrix_client=matrix_client,
        intake_service=intake_service,
        room1_id="!room1:example.org",
        bot_user_id="@bot:example.org",
        since_token="s1",
        sync_timeout_ms=5_000,
    )

    assert next_since == "s2"
    assert routed_count == 0
    assert matrix_client.reply_calls == []

    engine = sa.create_engine(sync_url)
    with engine.begin() as connection:
        case_count = connection.execute(sa.text("SELECT COUNT(*) FROM cases")).scalar_one()
        job_count = connection.execute(sa.text("SELECT COUNT(*) FROM jobs")).scalar_one()

    assert int(case_count) == 0
    assert int(job_count) == 0

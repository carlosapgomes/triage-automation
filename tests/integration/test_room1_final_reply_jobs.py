from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

import pytest
import sqlalchemy as sa
from alembic.config import Config

from alembic import command
from triage_automation.application.ports.case_repository_port import CaseCreateInput
from triage_automation.application.services.post_room1_final_service import (
    PostRoom1FinalService,
)
from triage_automation.domain.case_status import CaseStatus
from triage_automation.infrastructure.db.audit_repository import SqlAlchemyAuditRepository
from triage_automation.infrastructure.db.case_repository import SqlAlchemyCaseRepository
from triage_automation.infrastructure.db.message_repository import SqlAlchemyMessageRepository
from triage_automation.infrastructure.db.session import create_session_factory


class FakeMatrixPoster:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, str]] = []
        self._counter = 0

    async def reply_text(self, *, room_id: str, event_id: str, body: str) -> str:
        self.calls.append((room_id, event_id, body))
        self._counter += 1
        return f"$room1-final-{self._counter}"


def _upgrade_head(tmp_path: Path, filename: str) -> tuple[str, str]:
    db_path = tmp_path / filename
    sync_url = f"sqlite+pysqlite:///{db_path}"
    async_url = f"sqlite+aiosqlite:///{db_path}"

    alembic_config = Config("alembic.ini")
    alembic_config.set_main_option("sqlalchemy.url", sync_url)
    command.upgrade(alembic_config, "head")

    return sync_url, async_url


async def _create_case(
    case_repo: SqlAlchemyCaseRepository,
    *,
    status: CaseStatus,
    event_id: str,
) -> UUID:
    case = await case_repo.create_case(
        CaseCreateInput(
            case_id=uuid4(),
            status=status,
            room1_origin_room_id="!room1:example.org",
            room1_origin_event_id=event_id,
            room1_sender_user_id="@human:example.org",
        )
    )
    return case.case_id


@pytest.mark.asyncio
async def test_final_replies_match_templates_and_reply_to_origin(tmp_path: Path) -> None:
    sync_url, async_url = _upgrade_head(tmp_path, "room1_final_variants.db")
    session_factory = create_session_factory(async_url)

    case_repo = SqlAlchemyCaseRepository(session_factory)
    audit_repo = SqlAlchemyAuditRepository(session_factory)
    message_repo = SqlAlchemyMessageRepository(session_factory)
    matrix_poster = FakeMatrixPoster()

    service = PostRoom1FinalService(
        case_repository=case_repo,
        audit_repository=audit_repo,
        message_repository=message_repo,
        matrix_poster=matrix_poster,
    )

    denied_triage_id = await _create_case(
        case_repo,
        status=CaseStatus.DOCTOR_DENIED,
        event_id="$origin-final-deny-triage",
    )
    appt_confirmed_id = await _create_case(
        case_repo,
        status=CaseStatus.APPT_CONFIRMED,
        event_id="$origin-final-appt-ok",
    )
    appt_denied_id = await _create_case(
        case_repo,
        status=CaseStatus.APPT_DENIED,
        event_id="$origin-final-appt-deny",
    )
    failed_id = await _create_case(
        case_repo,
        status=CaseStatus.FAILED,
        event_id="$origin-final-failed",
    )

    engine = sa.create_engine(sync_url)
    with engine.begin() as connection:
        connection.execute(
            sa.text(
                "UPDATE cases SET doctor_reason = :reason WHERE case_id = :case_id"
            ),
            {"reason": "critério clínico", "case_id": denied_triage_id.hex},
        )
        connection.execute(
            sa.text(
                "UPDATE cases SET appointment_at = :appointment_at, "
                "appointment_location = :location, "
                "appointment_instructions = :instructions "
                "WHERE case_id = :case_id"
            ),
            {
                "appointment_at": datetime(2026, 2, 16, 14, 30, tzinfo=UTC),
                "location": "Sala 2",
                "instructions": "Jejum 8h",
                "case_id": appt_confirmed_id.hex,
            },
        )
        connection.execute(
            sa.text(
                "UPDATE cases SET appointment_reason = :reason WHERE case_id = :case_id"
            ),
            {"reason": "sem agenda", "case_id": appt_denied_id.hex},
        )

    await service.post(case_id=denied_triage_id, job_type="post_room1_final_denial_triage")
    await service.post(case_id=appt_confirmed_id, job_type="post_room1_final_appt")
    await service.post(case_id=appt_denied_id, job_type="post_room1_final_appt_denied")
    await service.post(
        case_id=failed_id,
        job_type="post_room1_final_failure",
        payload={"cause": "llm", "details": "schema mismatch"},
    )

    assert len(matrix_poster.calls) == 4

    assert matrix_poster.calls[0] == (
        "!room1:example.org",
        "$origin-final-deny-triage",
        f"❌ denied (triage)\nreason: critério clínico\ncase: {denied_triage_id}",
    )
    assert matrix_poster.calls[1] == (
        "!room1:example.org",
        "$origin-final-appt-ok",
        (
            "✅ accepted\n"
            "appointment: 16-02-2026 14:30 BRT\n"
            "location: Sala 2\n"
            "instructions: Jejum 8h\n"
            f"case: {appt_confirmed_id}"
        ),
    )
    assert matrix_poster.calls[2] == (
        "!room1:example.org",
        "$origin-final-appt-deny",
        f"❌ denied (appointment)\nreason: sem agenda\ncase: {appt_denied_id}",
    )
    assert matrix_poster.calls[3] == (
        "!room1:example.org",
        "$origin-final-failed",
        (
            "⚠️ processing failed\n"
            "cause: llm\n"
            "details: schema mismatch\n"
            f"case: {failed_id}"
        ),
    )

    with engine.begin() as connection:
        rows = connection.execute(
            sa.text(
                "SELECT case_id, status, room1_final_reply_event_id "
                "FROM cases ORDER BY room1_origin_event_id"
            )
        ).mappings().all()
        room1_final_message_count = connection.execute(
            sa.text("SELECT COUNT(*) FROM case_messages WHERE kind = 'room1_final'")
        ).scalar_one()

    assert len(rows) == 4
    assert all(row["status"] == "WAIT_R1_CLEANUP_THUMBS" for row in rows)
    assert all(row["room1_final_reply_event_id"] is not None for row in rows)
    assert int(room1_final_message_count) == 4

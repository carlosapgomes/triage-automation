from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
import sqlalchemy as sa
from alembic.config import Config

from alembic import command
from triage_automation.application.ports.case_repository_port import CaseCreateInput
from triage_automation.application.services.post_room3_request_service import (
    PostRoom3RequestService,
)
from triage_automation.domain.case_status import CaseStatus
from triage_automation.infrastructure.db.audit_repository import SqlAlchemyAuditRepository
from triage_automation.infrastructure.db.case_repository import SqlAlchemyCaseRepository
from triage_automation.infrastructure.db.message_repository import SqlAlchemyMessageRepository
from triage_automation.infrastructure.db.session import create_session_factory


class FakeMatrixPoster:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []
        self._counter = 0

    async def send_text(self, *, room_id: str, body: str) -> str:
        self.calls.append((room_id, body))
        self._counter += 1
        return f"$room3-{self._counter}"


def _upgrade_head(tmp_path: Path, filename: str) -> tuple[str, str]:
    db_path = tmp_path / filename
    sync_url = f"sqlite+pysqlite:///{db_path}"
    async_url = f"sqlite+aiosqlite:///{db_path}"

    alembic_config = Config("alembic.ini")
    alembic_config.set_main_option("sqlalchemy.url", sync_url)
    command.upgrade(alembic_config, "head")

    return sync_url, async_url


@pytest.mark.asyncio
async def test_room3_request_posts_request_and_template_and_moves_wait_appt(tmp_path: Path) -> None:
    sync_url, async_url = _upgrade_head(tmp_path, "room3_request_ok.db")
    session_factory = create_session_factory(async_url)

    case_repo = SqlAlchemyCaseRepository(session_factory)
    audit_repo = SqlAlchemyAuditRepository(session_factory)
    message_repo = SqlAlchemyMessageRepository(session_factory)
    matrix_poster = FakeMatrixPoster()

    case = await case_repo.create_case(
        CaseCreateInput(
            case_id=uuid4(),
            status=CaseStatus.DOCTOR_ACCEPTED,
            room1_origin_room_id="!room1:example.org",
            room1_origin_event_id="$origin-room3-1",
            room1_sender_user_id="@human:example.org",
        )
    )
    await case_repo.store_pdf_extraction(
        case_id=case.case_id,
        pdf_mxc_url="mxc://example.org/report",
        extracted_text="texto extraido",
        agency_record_number="4777300",
    )
    await case_repo.store_llm1_artifacts(
        case_id=case.case_id,
        structured_data_json={
            "patient": {
                "name": "EVALDO CARDOSO DOS SANTOS",
                "age": 42,
            }
        },
        summary_text="Resumo",
    )

    service = PostRoom3RequestService(
        room3_id="!room3:example.org",
        case_repository=case_repo,
        audit_repository=audit_repo,
        message_repository=message_repo,
        matrix_poster=matrix_poster,
    )

    result = await service.post_request(case_id=case.case_id)

    assert result.posted is True
    assert len(matrix_poster.calls) == 2

    request_room_id, request_body = matrix_poster.calls[0]
    assert request_room_id == "!room3:example.org"
    assert str(case.case_id) in request_body
    assert "registro: 4777300" in request_body
    assert "paciente: EVALDO CARDOSO DOS SANTOS" in request_body
    assert "idade: 42" in request_body
    assert "caso esperado" in request_body.lower()
    assert "copie a proxima mensagem" in request_body.lower()

    template_room_id, template_body = matrix_poster.calls[1]
    assert template_room_id == "!room3:example.org"
    assert "status: confirmado" in template_body
    assert "data_hora: DD-MM-YYYY HH:MM BRT" in template_body
    assert f"caso: {case.case_id}" in template_body

    engine = sa.create_engine(sync_url)
    with engine.begin() as connection:
        status = connection.execute(
            sa.text("SELECT status FROM cases WHERE case_id = :case_id"),
            {"case_id": case.case_id.hex},
        ).scalar_one()
        kinds = connection.execute(
            sa.text(
                "SELECT kind FROM case_messages "
                "WHERE case_id = :case_id ORDER BY id"
            ),
            {"case_id": case.case_id.hex},
        ).scalars().all()

    assert status == "WAIT_APPT"
    assert list(kinds) == ["room3_request", "room3_template"]


@pytest.mark.asyncio
async def test_duplicate_job_execution_is_idempotent(tmp_path: Path) -> None:
    sync_url, async_url = _upgrade_head(tmp_path, "room3_request_idempotent.db")
    session_factory = create_session_factory(async_url)

    case_repo = SqlAlchemyCaseRepository(session_factory)
    audit_repo = SqlAlchemyAuditRepository(session_factory)
    message_repo = SqlAlchemyMessageRepository(session_factory)
    matrix_poster = FakeMatrixPoster()

    case = await case_repo.create_case(
        CaseCreateInput(
            case_id=uuid4(),
            status=CaseStatus.DOCTOR_ACCEPTED,
            room1_origin_room_id="!room1:example.org",
            room1_origin_event_id="$origin-room3-2",
            room1_sender_user_id="@human:example.org",
        )
    )

    service = PostRoom3RequestService(
        room3_id="!room3:example.org",
        case_repository=case_repo,
        audit_repository=audit_repo,
        message_repository=message_repo,
        matrix_poster=matrix_poster,
    )

    first = await service.post_request(case_id=case.case_id)
    second = await service.post_request(case_id=case.case_id)

    assert first.posted is True
    assert second.posted is False
    assert len(matrix_poster.calls) == 2

    engine = sa.create_engine(sync_url)
    with engine.begin() as connection:
        message_count = connection.execute(
            sa.text("SELECT COUNT(*) FROM case_messages WHERE case_id = :case_id"),
            {"case_id": case.case_id.hex},
        ).scalar_one()

    assert int(message_count) == 2

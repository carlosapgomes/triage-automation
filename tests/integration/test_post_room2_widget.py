from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, cast
from uuid import UUID, uuid4

import pytest
import sqlalchemy as sa
from alembic.config import Config

from alembic import command
from triage_automation.application.ports.case_repository_port import CaseCreateInput
from triage_automation.application.services.post_room2_widget_service import PostRoom2WidgetService
from triage_automation.domain.case_status import CaseStatus
from triage_automation.infrastructure.db.audit_repository import SqlAlchemyAuditRepository
from triage_automation.infrastructure.db.case_repository import SqlAlchemyCaseRepository
from triage_automation.infrastructure.db.message_repository import SqlAlchemyMessageRepository
from triage_automation.infrastructure.db.prior_case_queries import SqlAlchemyPriorCaseQueries
from triage_automation.infrastructure.db.session import create_session_factory


class FakeMatrixPoster:
    def __init__(self) -> None:
        self.send_calls: list[tuple[str, str, str, str | None]] = []
        self.send_file_calls: list[tuple[str, str, str, str, str]] = []
        self.reply_calls: list[tuple[str, str, str, str, str | None]] = []
        self._counter = 0

    async def send_text(
        self,
        *,
        room_id: str,
        body: str,
        formatted_body: str | None = None,
    ) -> str:
        self._counter += 1
        event_id = f"$room2-{self._counter}"
        self.send_calls.append((room_id, body, event_id, formatted_body))
        return event_id

    async def send_file_from_mxc(
        self,
        *,
        room_id: str,
        filename: str,
        mxc_url: str,
        mimetype: str,
    ) -> str:
        self._counter += 1
        event_id = f"$room2-{self._counter}"
        self.send_file_calls.append((room_id, filename, mxc_url, mimetype, event_id))
        return event_id

    async def reply_text(
        self,
        *,
        room_id: str,
        event_id: str,
        body: str,
        formatted_body: str | None = None,
    ) -> str:
        self._counter += 1
        reply_event_id = f"$room2-{self._counter}"
        self.reply_calls.append((room_id, event_id, body, reply_event_id, formatted_body))
        return reply_event_id

    async def reply_file_from_mxc(
        self,
        *,
        room_id: str,
        event_id: str,
        filename: str,
        mxc_url: str,
        mimetype: str,
    ) -> str:
        _ = room_id, event_id, filename, mxc_url, mimetype
        self._counter += 1
        return f"$room2-reply-file-{self._counter}"


def _upgrade_head(tmp_path: Path, filename: str) -> tuple[str, str]:
    db_path = tmp_path / filename
    sync_url = f"sqlite+pysqlite:///{db_path}"
    async_url = f"sqlite+aiosqlite:///{db_path}"

    alembic_config = Config("alembic.ini")
    alembic_config.set_main_option("sqlalchemy.url", sync_url)
    command.upgrade(alembic_config, "head")

    return sync_url, async_url


def _structured_data(agency_record_number: str) -> dict[str, Any]:
    return {
        "schema_version": "1.1",
        "language": "pt-BR",
        "agency_record_number": agency_record_number,
        "patient": {"name": "Paciente", "age": 52, "sex": "F", "document_id": None},
        "eda": {
            "indication_category": "dyspepsia",
            "exclusion_type": "none",
            "is_pediatric": False,
            "foreign_body_suspected": False,
            "requested_procedure": {"name": "EDA", "urgency": "eletivo"},
            "labs": {
                "hb_g_dl": 10.5,
                "platelets_per_mm3": 130000,
                "inr": 1.2,
                "source_text_hint": None,
            },
            "ecg": {
                "report_present": "yes",
                "abnormal_flag": "no",
                "source_text_hint": None,
            },
            "asa": {"class": "II", "confidence": "media", "rationale": None},
            "cardiovascular_risk": {"level": "low", "confidence": "media", "rationale": None},
        },
        "policy_precheck": {
            "excluded_from_eda_flow": False,
            "exclusion_reason": None,
            "labs_required": True,
            "labs_pass": "yes",
            "labs_failed_items": [],
            "ecg_required": True,
            "ecg_present": "yes",
            "pediatric_flag": False,
            "notes": None,
        },
        "summary": {"one_liner": "Resumo LLM1", "bullet_points": ["a", "b", "c"]},
        "extraction_quality": {"confidence": "media", "missing_fields": [], "notes": None},
    }


def _suggested_action(case_id: UUID, agency_record_number: str) -> dict[str, Any]:
    return {
        "schema_version": "1.1",
        "language": "pt-BR",
        "case_id": str(case_id),
        "agency_record_number": agency_record_number,
        "suggestion": "deny",
        "support_recommendation": "anesthesist",
        "rationale": {
            "short_reason": "Informacoes insuficientes",
            "details": ["d1", "d2"],
            "missing_info_questions": ["q1"],
        },
        "policy_alignment": {
            "excluded_request": False,
            "labs_ok": "unknown",
            "ecg_ok": "unknown",
            "pediatric_flag": False,
            "notes": None,
        },
        "confidence": "media",
    }


def _extract_payload_from_widget_body(body: str) -> dict[str, Any]:
    marker = "```json\n"
    start = body.index(marker) + len(marker)
    end = body.index("\n```", start)
    parsed = json.loads(body[start:end])
    return cast(dict[str, Any], parsed)


@pytest.mark.asyncio
async def test_post_room2_widget_includes_prior_and_moves_to_wait_doctor(tmp_path: Path) -> None:
    sync_url, async_url = _upgrade_head(tmp_path, "post_room2_widget.db")
    session_factory = create_session_factory(async_url)

    case_repo = SqlAlchemyCaseRepository(session_factory)
    audit_repo = SqlAlchemyAuditRepository(session_factory)
    message_repo = SqlAlchemyMessageRepository(session_factory)
    prior_queries = SqlAlchemyPriorCaseQueries(session_factory)
    matrix_poster = FakeMatrixPoster()

    prior_case = await case_repo.create_case(
        CaseCreateInput(
            case_id=uuid4(),
            status=CaseStatus.DOCTOR_DENIED,
            room1_origin_room_id="!room1:example.org",
            room1_origin_event_id="$origin-prior",
            room1_sender_user_id="@human:example.org",
        )
    )
    await case_repo.store_pdf_extraction(
        case_id=prior_case.case_id,
        pdf_mxc_url="mxc://example.org/prior",
        extracted_text="prior text",
        agency_record_number="12345",
    )

    now = datetime.now(tz=UTC)
    engine = sa.create_engine(sync_url)
    with engine.begin() as connection:
        connection.execute(
            sa.text(
                "UPDATE cases SET created_at = :created_at, doctor_decision = 'deny', "
                "doctor_reason = 'prior denial', doctor_decided_at = :decided_at "
                "WHERE case_id = :case_id"
            ),
            {
                "created_at": now - timedelta(days=2),
                "decided_at": now - timedelta(days=2),
                "case_id": prior_case.case_id.hex,
            },
        )

    current_case = await case_repo.create_case(
        CaseCreateInput(
            case_id=uuid4(),
            status=CaseStatus.LLM_SUGGEST,
            room1_origin_room_id="!room1:example.org",
            room1_origin_event_id="$origin-current",
            room1_sender_user_id="@human:example.org",
        )
    )
    await case_repo.store_pdf_extraction(
        case_id=current_case.case_id,
        pdf_mxc_url="mxc://example.org/current",
        extracted_text="current text",
        agency_record_number="12345",
    )
    await case_repo.store_llm1_artifacts(
        case_id=current_case.case_id,
        structured_data_json=_structured_data("12345"),
        summary_text="Resumo LLM1",
    )
    await case_repo.store_llm2_artifacts(
        case_id=current_case.case_id,
        suggested_action_json=_suggested_action(current_case.case_id, "12345"),
    )

    service = PostRoom2WidgetService(
        room2_id="!room2:example.org",
        widget_public_base_url="https://bot-api.example.org",
        case_repository=case_repo,
        audit_repository=audit_repo,
        message_repository=message_repo,
        prior_case_queries=prior_queries,
        matrix_poster=matrix_poster,
    )

    await service.post_widget(case_id=current_case.case_id)

    assert len(matrix_poster.send_calls) == 0
    assert len(matrix_poster.send_file_calls) == 1
    assert len(matrix_poster.reply_calls) == 3

    root_room_id, root_filename, root_mxc_url, root_mimetype, root_event_id = (
        matrix_poster.send_file_calls[0]
    )
    assert root_room_id == "!room2:example.org"
    assert root_filename == f"caso-{current_case.case_id}-relatorio-original.pdf"
    assert root_mxc_url == "mxc://example.org/current"
    assert root_mimetype == "application/pdf"

    (
        summary_room_id,
        summary_parent,
        summary_body,
        _summary_event_id,
        summary_formatted_body,
    ) = matrix_poster.reply_calls[0]
    assert summary_room_id == "!room2:example.org"
    assert summary_parent == root_event_id
    assert f"caso: {current_case.case_id}" in summary_body
    assert "Resumo LLM1" in summary_body
    assert "# Resumo técnico da triagem" in summary_body
    assert "## Dados extraídos:" in summary_body
    assert "## Recomendação do sistema:" in summary_body
    assert "sugestao" in summary_body.lower()
    assert "negar" in summary_body
    assert "deny" not in summary_body
    assert "- prechecagem_politica:" in summary_body
    assert "laboratorio_aprovado=sim" in summary_body
    assert "é pediátrico?=nao" in summary_body
    assert "- eda:" in summary_body
    assert "ecg.sinal de alerta=nao" in summary_body
    assert "ecg.laudo_presente=sim" in summary_body
    assert "```json" not in summary_body
    assert summary_formatted_body is not None
    assert "<h1>Resumo técnico da triagem</h1>" in summary_formatted_body
    assert "<h2>Dados extraídos:</h2>" in summary_formatted_body
    assert "<li>prechecagem_politica:" in summary_formatted_body

    (
        instructions_room_id,
        instructions_parent,
        instructions_body,
        _instructions_event_id,
        instructions_formatted_body,
    ) = matrix_poster.reply_calls[1]
    assert instructions_room_id == "!room2:example.org"
    assert instructions_parent == root_event_id
    assert "copie a próxima mensagem" in instructions_body.lower()
    assert "responda como resposta a ela" in instructions_body.lower()
    assert "decisão:aceitar" in instructions_body
    assert instructions_formatted_body is not None
    assert "<h1>Instrução de decisão médica</h1>" in instructions_formatted_body
    assert "<ol>" in instructions_formatted_body

    (
        template_room_id,
        template_parent,
        template_body,
        _template_event_id,
        template_formatted_body,
    ) = matrix_poster.reply_calls[2]
    assert template_room_id == "!room2:example.org"
    assert template_parent == root_event_id
    assert template_body.startswith("decisao: aceitar\n")
    assert "suporte: nenhum\n" in template_body
    assert "motivo: (opcional)\n" in template_body
    assert template_formatted_body is not None
    assert template_formatted_body.startswith("<p>")
    assert "<br>" in template_formatted_body
    assert template_formatted_body.endswith("</p>")

    with engine.begin() as connection:
        status = connection.execute(
            sa.text("SELECT status FROM cases WHERE case_id = :case_id"),
            {"case_id": current_case.case_id.hex},
        ).scalar_one()
        kinds = connection.execute(
            sa.text(
                "SELECT kind FROM case_messages "
                "WHERE case_id = :case_id ORDER BY id"
            ),
            {"case_id": current_case.case_id.hex},
        ).scalars().all()
        status_event_payload = connection.execute(
            sa.text(
                "SELECT payload FROM case_events "
                "WHERE case_id = :case_id AND event_type = 'CASE_STATUS_CHANGED' "
                "ORDER BY id DESC LIMIT 1"
            ),
            {"case_id": current_case.case_id.hex},
        ).scalar_one()
        root_case_id = connection.execute(
            sa.text(
                "SELECT case_id FROM case_messages "
                "WHERE room_id = :room_id AND event_id = :event_id AND kind = 'room2_case_root' "
                "LIMIT 1"
            ),
            {"room_id": "!room2:example.org", "event_id": root_event_id},
        ).scalar_one_or_none()
        transcript_rows = connection.execute(
            sa.text(
                "SELECT event_id, message_type, sender, message_text, reply_to_event_id "
                "FROM case_matrix_message_transcripts "
                "WHERE case_id = :case_id "
                "ORDER BY id"
            ),
            {"case_id": current_case.case_id.hex},
        ).mappings().all()

    assert status == "WAIT_DOCTOR"
    assert list(kinds) == [
        "room2_case_root",
        "room2_case_summary",
        "room2_case_instructions",
        "room2_case_template",
    ]
    assert root_case_id is not None
    assert UUID(str(root_case_id)) == current_case.case_id
    assert len(transcript_rows) == 4
    assert transcript_rows[0]["message_type"] == "room2_case_root"
    assert transcript_rows[0]["sender"] == "bot"
    assert root_filename in str(transcript_rows[0]["message_text"])
    assert transcript_rows[0]["reply_to_event_id"] is None
    assert transcript_rows[1]["message_type"] == "room2_case_summary"
    assert transcript_rows[1]["message_text"] == summary_body
    assert transcript_rows[1]["reply_to_event_id"] == root_event_id
    assert transcript_rows[2]["message_type"] == "room2_case_instructions"
    assert transcript_rows[2]["message_text"] == instructions_body
    assert transcript_rows[2]["reply_to_event_id"] == root_event_id
    assert transcript_rows[3]["message_type"] == "room2_case_template"
    assert transcript_rows[3]["message_text"] == template_body
    assert transcript_rows[3]["reply_to_event_id"] == root_event_id
    parsed_status_payload = (
        status_event_payload
        if isinstance(status_event_payload, dict)
        else json.loads(status_event_payload)
    )
    assert parsed_status_payload == {
        "from_status": "R2_POST_WIDGET",
        "to_status": "WAIT_DOCTOR",
    }

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest
import sqlalchemy as sa
from alembic.config import Config

from alembic import command
from triage_automation.application.dto.webhook_models import TriageDecisionWebhookPayload
from triage_automation.application.ports.job_queue_port import JobRecord
from triage_automation.application.services.execute_cleanup_service import ExecuteCleanupService
from triage_automation.application.services.handle_doctor_decision_service import (
    HandleDoctorDecisionOutcome,
    HandleDoctorDecisionService,
)
from triage_automation.application.services.job_failure_service import JobFailureService
from triage_automation.application.services.llm1_service import Llm1Service
from triage_automation.application.services.llm2_service import Llm2Service
from triage_automation.application.services.post_room1_final_service import PostRoom1FinalService
from triage_automation.application.services.post_room2_widget_service import PostRoom2WidgetService
from triage_automation.application.services.post_room3_request_service import (
    PostRoom3RequestService,
)
from triage_automation.application.services.process_pdf_case_service import ProcessPdfCaseService
from triage_automation.application.services.reaction_service import ReactionEvent, ReactionService
from triage_automation.application.services.room1_intake_service import Room1IntakeService
from triage_automation.application.services.room3_reply_service import (
    Room3ReplyEvent,
    Room3ReplyService,
)
from triage_automation.application.services.worker_runtime import WorkerRuntime
from triage_automation.domain.case_status import CaseStatus
from triage_automation.infrastructure.db.audit_repository import SqlAlchemyAuditRepository
from triage_automation.infrastructure.db.case_repository import SqlAlchemyCaseRepository
from triage_automation.infrastructure.db.job_queue_repository import SqlAlchemyJobQueueRepository
from triage_automation.infrastructure.db.message_repository import SqlAlchemyMessageRepository
from triage_automation.infrastructure.db.prior_case_queries import SqlAlchemyPriorCaseQueries
from triage_automation.infrastructure.db.session import create_session_factory
from triage_automation.infrastructure.matrix.event_parser import parse_room1_pdf_intake_event
from triage_automation.infrastructure.matrix.mxc_downloader import MatrixMxcDownloader
from triage_automation.infrastructure.pdf.text_extractor import PdfTextExtractor


class FakeMatrixClient:
    def __init__(self) -> None:
        self._counter = 0
        self.send_calls: list[tuple[str, str, str]] = []
        self.reply_calls: list[tuple[str, str, str, str]] = []
        self.reply_file_calls: list[tuple[str, str, str, str, str]] = []
        self.redactions: list[tuple[str, str]] = []

    def _next_event_id(self) -> str:
        self._counter += 1
        return f"$event-{self._counter}"

    async def send_text(
        self,
        *,
        room_id: str,
        body: str,
        formatted_body: str | None = None,
    ) -> str:
        _ = formatted_body
        event_id = self._next_event_id()
        self.send_calls.append((room_id, body, event_id))
        return event_id

    async def reply_text(
        self,
        *,
        room_id: str,
        event_id: str,
        body: str,
        formatted_body: str | None = None,
    ) -> str:
        _ = formatted_body
        response_event_id = self._next_event_id()
        self.reply_calls.append((room_id, event_id, body, response_event_id))
        return response_event_id

    async def reply_file_text(
        self,
        *,
        room_id: str,
        event_id: str,
        filename: str,
        text_content: str,
    ) -> str:
        response_event_id = self._next_event_id()
        self.reply_file_calls.append(
            (room_id, event_id, filename, text_content, response_event_id)
        )
        return response_event_id

    async def redact_event(self, *, room_id: str, event_id: str) -> None:
        self.redactions.append((room_id, event_id))


class FakeMatrixMediaClient:
    def __init__(self, payload: bytes) -> None:
        self._payload = payload

    async def download_mxc(self, mxc_url: str) -> bytes:
        return self._payload


class FakeLlm1Client:
    async def complete(self, *, system_prompt: str, user_prompt: str) -> str:
        return json.dumps(_valid_llm1_payload("12345"))


class FakeLlm2Client:
    async def complete(self, *, system_prompt: str, user_prompt: str) -> str:
        case_match = re.search(r"case_id:\s*([0-9a-fA-F-]{36})", user_prompt)
        record_match = re.search(r"agency_record_number:\s*([0-9]{5,})", user_prompt)
        assert case_match is not None
        assert record_match is not None
        payload = _valid_llm2_payload(
            case_id=case_match.group(1),
            agency_record_number=record_match.group(1),
        )
        return json.dumps(
            payload
        )


def _build_simple_pdf(text: str) -> bytes:
    stream = f"BT /F1 24 Tf 72 72 Td ({text}) Tj ET"
    objects = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 144] "
        "/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        f"<< /Length {len(stream)} >>\nstream\n{stream}\nendstream",
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]

    parts: list[bytes] = [b"%PDF-1.4\n"]
    offsets = [0]

    for index, body in enumerate(objects, start=1):
        offsets.append(sum(len(part) for part in parts))
        parts.append(f"{index} 0 obj\n{body}\nendobj\n".encode("latin-1"))

    xref_start = sum(len(part) for part in parts)
    size = len(objects) + 1

    xref_lines = [f"xref\n0 {size}\n", "0000000000 65535 f \n"]
    xref_lines.extend(f"{offset:010d} 00000 n \n" for offset in offsets[1:])
    trailer = (
        f"trailer\n<< /Size {size} /Root 1 0 R >>\n"
        f"startxref\n{xref_start}\n%%EOF\n"
    )

    parts.append("".join(xref_lines).encode("latin-1"))
    parts.append(trailer.encode("latin-1"))
    return b"".join(parts)


def _valid_llm1_payload(agency_record_number: str) -> dict[str, object]:
    return {
        "schema_version": "1.1",
        "language": "pt-BR",
        "agency_record_number": agency_record_number,
        "patient": {"name": "Paciente", "age": 49, "sex": "F", "document_id": None},
        "eda": {
            "indication_category": "dyspepsia",
            "exclusion_type": "none",
            "is_pediatric": False,
            "foreign_body_suspected": False,
            "requested_procedure": {"name": "EDA", "urgency": "eletivo"},
            "labs": {
                "hb_g_dl": 11.2,
                "platelets_per_mm3": 180000,
                "inr": 1.1,
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
        "summary": {"one_liner": "Resumo", "bullet_points": ["a", "b", "c"]},
        "extraction_quality": {"confidence": "media", "missing_fields": [], "notes": None},
    }


def _valid_llm2_payload(*, case_id: str, agency_record_number: str) -> dict[str, object]:
    return {
        "schema_version": "1.1",
        "language": "pt-BR",
        "case_id": case_id,
        "agency_record_number": agency_record_number,
        "suggestion": "accept",
        "support_recommendation": "none",
        "rationale": {
            "short_reason": "Apto",
            "details": ["ok", "criterios atendidos"],
            "missing_info_questions": [],
        },
        "policy_alignment": {
            "excluded_request": False,
            "labs_ok": "yes",
            "ecg_ok": "yes",
            "pediatric_flag": False,
            "notes": None,
        },
        "confidence": "media",
    }


def _upgrade_head(tmp_path: Path, filename: str) -> tuple[str, str]:
    db_path = tmp_path / filename
    sync_url = f"sqlite+pysqlite:///{db_path}"
    async_url = f"sqlite+aiosqlite:///{db_path}"

    alembic_config = Config("alembic.ini")
    alembic_config.set_main_option("sqlalchemy.url", sync_url)
    command.upgrade(alembic_config, "head")

    return sync_url, async_url


async def _no_sleep(seconds: float) -> None:
    _ = seconds


async def _drain_queue(runtime: WorkerRuntime, *, max_iterations: int = 40) -> None:
    for _ in range(max_iterations):
        claimed = await runtime.run_once()
        if claimed == 0:
            return
    raise AssertionError("queue drain exceeded max_iterations")


def _build_handlers(
    *,
    process_service: ProcessPdfCaseService,
    room2_service: PostRoom2WidgetService,
    room3_service: PostRoom3RequestService,
    room1_final_service: PostRoom1FinalService,
    cleanup_service: ExecuteCleanupService,
) -> dict[str, Any]:
    async def handle_process_pdf_case(job: JobRecord) -> None:
        assert job.case_id is not None
        pdf_mxc_url = job.payload.get("pdf_mxc_url")
        assert isinstance(pdf_mxc_url, str)
        await process_service.process_case(case_id=job.case_id, pdf_mxc_url=pdf_mxc_url)

    async def handle_post_room2_widget(job: JobRecord) -> None:
        assert job.case_id is not None
        await room2_service.post_widget(case_id=job.case_id)

    async def handle_post_room3_request(job: JobRecord) -> None:
        assert job.case_id is not None
        await room3_service.post_request(case_id=job.case_id)

    async def handle_post_room1_final(job: JobRecord) -> None:
        assert job.case_id is not None
        await room1_final_service.post(
            case_id=job.case_id,
            job_type=job.job_type,
            payload=job.payload,
        )

    async def handle_cleanup(job: JobRecord) -> None:
        assert job.case_id is not None
        await cleanup_service.execute(case_id=job.case_id)

    return {
        "process_pdf_case": handle_process_pdf_case,
        "post_room2_widget": handle_post_room2_widget,
        "post_room3_request": handle_post_room3_request,
        "post_room1_final_denial_triage": handle_post_room1_final,
        "post_room1_final_appt": handle_post_room1_final,
        "post_room1_final_appt_denied": handle_post_room1_final,
        "post_room1_final_failure": handle_post_room1_final,
        "execute_cleanup": handle_cleanup,
    }


def _find_case_row(sync_url: str, case_id: UUID) -> dict[str, object]:
    engine = sa.create_engine(sync_url)
    with engine.begin() as connection:
        row = connection.execute(
            sa.text(
                "SELECT status, room1_final_reply_event_id, cleanup_completed_at "
                "FROM cases WHERE case_id = :case_id"
            ),
            {"case_id": case_id.hex},
        ).mappings().one()
    return dict(row)


def _find_message_event_id(sync_url: str, *, case_id: UUID, kind: str) -> str:
    engine = sa.create_engine(sync_url)
    with engine.begin() as connection:
        value = connection.execute(
            sa.text(
                "SELECT event_id FROM case_messages "
                "WHERE case_id = :case_id AND kind = :kind "
                "ORDER BY id DESC LIMIT 1"
            ),
            {"case_id": case_id.hex, "kind": kind},
        ).scalar_one()
    return str(value)


def _count_case_messages(sync_url: str, *, case_id: UUID) -> int:
    engine = sa.create_engine(sync_url)
    with engine.begin() as connection:
        value = connection.execute(
            sa.text("SELECT COUNT(*) FROM case_messages WHERE case_id = :case_id"),
            {"case_id": case_id.hex},
        ).scalar_one()
    return int(value)


def _count_room3_requests(sync_url: str, *, case_id: UUID) -> int:
    engine = sa.create_engine(sync_url)
    with engine.begin() as connection:
        value = connection.execute(
            sa.text(
                "SELECT COUNT(*) FROM case_messages "
                "WHERE case_id = :case_id AND kind = 'room3_request'"
            ),
            {"case_id": case_id.hex},
        ).scalar_one()
    return int(value)


def _count_cleanup_events(sync_url: str, *, case_id: UUID) -> int:
    engine = sa.create_engine(sync_url)
    with engine.begin() as connection:
        value = connection.execute(
            sa.text(
                "SELECT COUNT(*) FROM case_events "
                "WHERE case_id = :case_id AND event_type = 'CLEANUP_COMPLETED'"
            ),
            {"case_id": case_id.hex},
        ).scalar_one()
    return int(value)


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
async def test_happy_path_reaches_cleaned_with_cleanup_redactions(tmp_path: Path) -> None:
    sync_url, async_url = _upgrade_head(tmp_path, "e2e_happy_path.db")
    session_factory = create_session_factory(async_url)
    matrix_client = FakeMatrixClient()

    case_repo = SqlAlchemyCaseRepository(session_factory)
    audit_repo = SqlAlchemyAuditRepository(session_factory)
    message_repo = SqlAlchemyMessageRepository(session_factory)
    queue_repo = SqlAlchemyJobQueueRepository(session_factory)

    process_service = ProcessPdfCaseService(
        case_repository=case_repo,
        mxc_downloader=MatrixMxcDownloader(
            FakeMatrixMediaClient(
                _build_simple_pdf(
                    "RELATORIO DE OCORRENCIAS 12345 " "Texto clinico 12345"
                )
            )
        ),
        text_extractor=PdfTextExtractor(),
        llm1_service=Llm1Service(llm_client=FakeLlm1Client()),
        llm2_service=Llm2Service(llm_client=FakeLlm2Client()),
        audit_repository=audit_repo,
        job_queue=queue_repo,
    )
    room2_service = PostRoom2WidgetService(
        room2_id="!room2:example.org",
        widget_public_base_url="https://webhook.example.org",
        case_repository=case_repo,
        audit_repository=audit_repo,
        message_repository=message_repo,
        prior_case_queries=SqlAlchemyPriorCaseQueries(session_factory),
        matrix_poster=matrix_client,
    )
    room3_service = PostRoom3RequestService(
        room3_id="!room3:example.org",
        case_repository=case_repo,
        audit_repository=audit_repo,
        message_repository=message_repo,
        matrix_poster=matrix_client,
    )
    room1_final_service = PostRoom1FinalService(
        case_repository=case_repo,
        audit_repository=audit_repo,
        message_repository=message_repo,
        matrix_poster=matrix_client,
    )
    cleanup_service = ExecuteCleanupService(
        case_repository=case_repo,
        audit_repository=audit_repo,
        message_repository=message_repo,
        matrix_redactor=matrix_client,
    )
    failure_service = JobFailureService(
        case_repository=case_repo,
        audit_repository=audit_repo,
        job_queue=queue_repo,
    )
    runtime = WorkerRuntime(
        queue=queue_repo,
        handlers=_build_handlers(
            process_service=process_service,
            room2_service=room2_service,
            room3_service=room3_service,
            room1_final_service=room1_final_service,
            cleanup_service=cleanup_service,
        ),
        audit_repository=audit_repo,
        job_failure_service=failure_service,
        poll_interval_seconds=0,
        sleep=_no_sleep,
    )

    intake_service = Room1IntakeService(
        case_repository=case_repo,
        audit_repository=audit_repo,
        message_repository=message_repo,
        job_queue=queue_repo,
        matrix_poster=matrix_client,
    )
    doctor_decision_service = HandleDoctorDecisionService(
        case_repository=case_repo,
        audit_repository=audit_repo,
        job_queue=queue_repo,
    )
    room3_reply_service = Room3ReplyService(
        room3_id="!room3:example.org",
        case_repository=case_repo,
        audit_repository=audit_repo,
        message_repository=message_repo,
        job_queue=queue_repo,
        matrix_poster=matrix_client,
    )
    reaction_service = ReactionService(
        room1_id="!room1:example.org",
        room2_id="!room2:example.org",
        room3_id="!room3:example.org",
        case_repository=case_repo,
        audit_repository=audit_repo,
        message_repository=message_repo,
        job_queue=queue_repo,
    )

    parsed = parse_room1_pdf_intake_event(
        room_id="!room1:example.org",
        event=_make_raw_pdf_event("$origin-e2e-1"),
        bot_user_id="@bot:example.org",
    )
    assert parsed is not None

    intake_result = await intake_service.ingest_pdf_event(parsed)
    assert intake_result.processed is True
    assert intake_result.case_id is not None
    case_id = UUID(intake_result.case_id)

    await _drain_queue(runtime)

    case_row = _find_case_row(sync_url, case_id)
    assert case_row["status"] == CaseStatus.WAIT_DOCTOR.value

    decision_result = await doctor_decision_service.handle(
        TriageDecisionWebhookPayload(
            case_id=case_id,
            doctor_user_id="@doctor:example.org",
            decision="accept",
            support_flag="none",
            reason=None,
        )
    )
    assert decision_result.outcome == HandleDoctorDecisionOutcome.APPLIED

    await _drain_queue(runtime)

    case_row = _find_case_row(sync_url, case_id)
    assert case_row["status"] == CaseStatus.WAIT_APPT.value

    room3_request_event_id = _find_message_event_id(
        sync_url,
        case_id=case_id,
        kind="room3_request",
    )
    room3_result = await room3_reply_service.handle_reply(
        Room3ReplyEvent(
            room_id="!room3:example.org",
            event_id="$scheduler-e2e-1",
            sender_user_id="@scheduler:example.org",
            body=(
                "16-02-2026 14:30 BRT\n"
                "location: Sala 2\n"
                "instructions: Jejum 8h\n"
                f"case: {case_id}"
            ),
            reply_to_event_id=room3_request_event_id,
        )
    )
    assert room3_result.processed is True

    await _drain_queue(runtime)

    case_row = _find_case_row(sync_url, case_id)
    assert case_row["status"] == CaseStatus.WAIT_R1_CLEANUP_THUMBS.value
    assert isinstance(case_row["room1_final_reply_event_id"], str)
    final_reply_event_id = str(case_row["room1_final_reply_event_id"])

    reaction_result = await reaction_service.handle(
        ReactionEvent(
            room_id="!room1:example.org",
            reaction_event_id="$thumbs-e2e-1",
            reactor_user_id="@nurse:example.org",
            related_event_id=final_reply_event_id,
            reaction_key="👍",
        )
    )
    assert reaction_result.processed is True

    await _drain_queue(runtime)

    case_row = _find_case_row(sync_url, case_id)
    assert case_row["status"] == CaseStatus.CLEANED.value
    assert case_row["cleanup_completed_at"] is not None
    assert _count_cleanup_events(sync_url, case_id=case_id) == 1

    case_message_count = _count_case_messages(sync_url, case_id=case_id)
    assert len(matrix_client.redactions) == case_message_count


@pytest.mark.asyncio
async def test_doctor_deny_path_posts_room1_final_without_room3_request(tmp_path: Path) -> None:
    sync_url, async_url = _upgrade_head(tmp_path, "e2e_doctor_deny.db")
    session_factory = create_session_factory(async_url)
    matrix_client = FakeMatrixClient()

    case_repo = SqlAlchemyCaseRepository(session_factory)
    audit_repo = SqlAlchemyAuditRepository(session_factory)
    message_repo = SqlAlchemyMessageRepository(session_factory)
    queue_repo = SqlAlchemyJobQueueRepository(session_factory)

    process_service = ProcessPdfCaseService(
        case_repository=case_repo,
        mxc_downloader=MatrixMxcDownloader(
            FakeMatrixMediaClient(
                _build_simple_pdf(
                    "RELATORIO DE OCORRENCIAS 12345 " "Texto clinico 12345"
                )
            )
        ),
        text_extractor=PdfTextExtractor(),
        llm1_service=Llm1Service(llm_client=FakeLlm1Client()),
        llm2_service=Llm2Service(llm_client=FakeLlm2Client()),
        audit_repository=audit_repo,
        job_queue=queue_repo,
    )
    room2_service = PostRoom2WidgetService(
        room2_id="!room2:example.org",
        widget_public_base_url="https://webhook.example.org",
        case_repository=case_repo,
        audit_repository=audit_repo,
        message_repository=message_repo,
        prior_case_queries=SqlAlchemyPriorCaseQueries(session_factory),
        matrix_poster=matrix_client,
    )
    room1_final_service = PostRoom1FinalService(
        case_repository=case_repo,
        audit_repository=audit_repo,
        message_repository=message_repo,
        matrix_poster=matrix_client,
    )
    cleanup_service = ExecuteCleanupService(
        case_repository=case_repo,
        audit_repository=audit_repo,
        message_repository=message_repo,
        matrix_redactor=matrix_client,
    )
    failure_service = JobFailureService(
        case_repository=case_repo,
        audit_repository=audit_repo,
        job_queue=queue_repo,
    )
    runtime = WorkerRuntime(
        queue=queue_repo,
        handlers=_build_handlers(
            process_service=process_service,
            room2_service=room2_service,
            room3_service=PostRoom3RequestService(
                room3_id="!room3:example.org",
                case_repository=case_repo,
                audit_repository=audit_repo,
                message_repository=message_repo,
                matrix_poster=matrix_client,
            ),
            room1_final_service=room1_final_service,
            cleanup_service=cleanup_service,
        ),
        audit_repository=audit_repo,
        job_failure_service=failure_service,
        poll_interval_seconds=0,
        sleep=_no_sleep,
    )

    intake_service = Room1IntakeService(
        case_repository=case_repo,
        audit_repository=audit_repo,
        message_repository=message_repo,
        job_queue=queue_repo,
        matrix_poster=matrix_client,
    )
    doctor_decision_service = HandleDoctorDecisionService(
        case_repository=case_repo,
        audit_repository=audit_repo,
        job_queue=queue_repo,
    )

    parsed = parse_room1_pdf_intake_event(
        room_id="!room1:example.org",
        event=_make_raw_pdf_event("$origin-e2e-2"),
        bot_user_id="@bot:example.org",
    )
    assert parsed is not None

    intake_result = await intake_service.ingest_pdf_event(parsed)
    assert intake_result.processed is True
    assert intake_result.case_id is not None
    case_id = UUID(intake_result.case_id)

    await _drain_queue(runtime)

    decision_result = await doctor_decision_service.handle(
        TriageDecisionWebhookPayload(
            case_id=case_id,
            doctor_user_id="@doctor:example.org",
            decision="deny",
            support_flag="none",
            reason="sem criterio clinico",
        )
    )
    assert decision_result.outcome == HandleDoctorDecisionOutcome.APPLIED

    await _drain_queue(runtime)

    case_row = _find_case_row(sync_url, case_id)
    assert case_row["status"] == CaseStatus.WAIT_R1_CLEANUP_THUMBS.value
    assert case_row["room1_final_reply_event_id"] is not None
    assert _count_room3_requests(sync_url, case_id=case_id) == 0

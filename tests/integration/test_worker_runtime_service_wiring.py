from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

import pytest
import sqlalchemy as sa
from alembic.config import Config

from alembic import command
from apps.worker.main import build_worker_runtime
from triage_automation.application.ports.case_repository_port import CaseCreateInput
from triage_automation.application.ports.job_queue_port import JobEnqueueInput
from triage_automation.application.ports.message_repository_port import CaseMessageCreateInput
from triage_automation.config.settings import Settings
from triage_automation.domain.case_status import CaseStatus
from triage_automation.infrastructure.db.case_repository import SqlAlchemyCaseRepository
from triage_automation.infrastructure.db.job_queue_repository import SqlAlchemyJobQueueRepository
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


def _set_required_env(monkeypatch: pytest.MonkeyPatch) -> Settings:
    monkeypatch.setenv("ROOM1_ID", "!room1:example.org")
    monkeypatch.setenv("ROOM2_ID", "!room2:example.org")
    monkeypatch.setenv("ROOM3_ID", "!room3:example.org")
    monkeypatch.setenv("MATRIX_HOMESERVER_URL", "https://matrix.example.org")
    monkeypatch.setenv("MATRIX_BOT_USER_ID", "@bot:example.org")
    monkeypatch.setenv("MATRIX_ACCESS_TOKEN", "matrix-token")
    monkeypatch.setenv("MATRIX_SYNC_TIMEOUT_MS", "30000")
    monkeypatch.setenv("MATRIX_POLL_INTERVAL_SECONDS", "0")
    monkeypatch.setenv("WORKER_POLL_INTERVAL_SECONDS", "0")
    monkeypatch.setenv("WEBHOOK_PUBLIC_URL", "https://webhook.example.org")
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///unused.db")
    monkeypatch.setenv("WEBHOOK_HMAC_SECRET", "secret")
    monkeypatch.setenv("LLM_RUNTIME_MODE", "deterministic")
    monkeypatch.setenv("LOG_LEVEL", "INFO")
    return Settings()


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


class FakeMatrixRuntimeClient:
    def __init__(self) -> None:
        self._counter = 0
        self.send_calls: list[tuple[str, str]] = []
        self.reply_calls: list[tuple[str, str, str]] = []
        self.reply_file_calls: list[tuple[str, str, str, str]] = []
        self.redaction_calls: list[tuple[str, str]] = []
        self._pdf_bytes = _build_simple_pdf(
            "RELATORIO DE OCORRENCIAS 12345 "
            "laudo 12345 com watermark 12345 e fim"
        )

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
        self.send_calls.append((room_id, body))
        return self._next_event_id()

    async def reply_text(
        self,
        *,
        room_id: str,
        event_id: str,
        body: str,
        formatted_body: str | None = None,
    ) -> str:
        _ = formatted_body
        self.reply_calls.append((room_id, event_id, body))
        return self._next_event_id()

    async def reply_file_text(
        self,
        *,
        room_id: str,
        event_id: str,
        filename: str,
        text_content: str,
    ) -> str:
        self.reply_file_calls.append((room_id, event_id, filename, text_content))
        return self._next_event_id()

    async def redact_event(self, *, room_id: str, event_id: str) -> None:
        self.redaction_calls.append((room_id, event_id))

    async def download_mxc(self, mxc_url: str) -> bytes:
        _ = mxc_url
        return self._pdf_bytes


class FakeLlm1Client:
    async def complete(self, *, system_prompt: str, user_prompt: str) -> str:
        _ = system_prompt, user_prompt
        return json.dumps(_valid_llm1_payload("12345"))


class FakeLlm2Client:
    async def complete(self, *, system_prompt: str, user_prompt: str) -> str:
        _ = system_prompt
        case_match = re.search(r"case_id:\s*([0-9a-fA-F-]{36})", user_prompt)
        record_match = re.search(r"agency_record_number:\s*([0-9]{5,})", user_prompt)
        assert case_match is not None
        assert record_match is not None
        return json.dumps(
            _valid_llm2_payload(
                case_id=case_match.group(1),
                agency_record_number=record_match.group(1),
            )
        )


async def _create_case(
    case_repo: SqlAlchemyCaseRepository,
    *,
    status: CaseStatus,
    origin_event_id: str,
) -> UUID:
    created = await case_repo.create_case(
        CaseCreateInput(
            case_id=uuid4(),
            status=status,
            room1_origin_room_id="!room1:example.org",
            room1_origin_event_id=origin_event_id,
            room1_sender_user_id="@human:example.org",
        )
    )
    return created.case_id


@pytest.mark.asyncio
async def test_runtime_worker_handlers_execute_all_supported_job_types(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sync_url, async_url = _upgrade_head(tmp_path, "worker_runtime_wiring_all_jobs.db")
    settings = _set_required_env(monkeypatch)
    session_factory = create_session_factory(async_url)

    case_repo = SqlAlchemyCaseRepository(session_factory)
    queue_repo = SqlAlchemyJobQueueRepository(session_factory)
    message_repo = SqlAlchemyMessageRepository(session_factory)
    matrix_client = FakeMatrixRuntimeClient()

    process_case_id = await _create_case(
        case_repo,
        status=CaseStatus.NEW,
        origin_event_id="$origin-process",
    )
    room2_case_id = await _create_case(
        case_repo,
        status=CaseStatus.LLM_SUGGEST,
        origin_event_id="$origin-room2",
    )
    room3_case_id = await _create_case(
        case_repo,
        status=CaseStatus.DOCTOR_ACCEPTED,
        origin_event_id="$origin-room3",
    )
    denied_case_id = await _create_case(
        case_repo,
        status=CaseStatus.DOCTOR_DENIED,
        origin_event_id="$origin-final-denied",
    )
    appt_case_id = await _create_case(
        case_repo,
        status=CaseStatus.APPT_CONFIRMED,
        origin_event_id="$origin-final-appt",
    )
    appt_denied_case_id = await _create_case(
        case_repo,
        status=CaseStatus.APPT_DENIED,
        origin_event_id="$origin-final-appt-denied",
    )
    failed_case_id = await _create_case(
        case_repo,
        status=CaseStatus.FAILED,
        origin_event_id="$origin-final-failed",
    )
    cleanup_case_id = await _create_case(
        case_repo,
        status=CaseStatus.CLEANUP_RUNNING,
        origin_event_id="$origin-cleanup",
    )

    await case_repo.store_pdf_extraction(
        case_id=room2_case_id,
        pdf_mxc_url="mxc://example.org/ready.pdf",
        extracted_text="texto limpo",
        agency_record_number="12345",
        agency_record_extracted_at=datetime.now(tz=UTC),
    )
    await case_repo.store_llm1_artifacts(
        case_id=room2_case_id,
        structured_data_json=_valid_llm1_payload("12345"),
        summary_text="Resumo",
    )
    await case_repo.store_llm2_artifacts(
        case_id=room2_case_id,
        suggested_action_json=_valid_llm2_payload(
            case_id=str(room2_case_id),
            agency_record_number="12345",
        ),
    )

    engine = sa.create_engine(sync_url)
    with engine.begin() as connection:
        connection.execute(
            sa.text(
                "UPDATE cases SET doctor_reason = :reason WHERE case_id = :case_id"
            ),
            {"reason": "criterio clinico", "case_id": denied_case_id.hex},
        )
        connection.execute(
            sa.text(
                "UPDATE cases SET appointment_at = :appointment_at, "
                "appointment_location = :location, appointment_instructions = :instructions "
                "WHERE case_id = :case_id"
            ),
            {
                "appointment_at": datetime(2026, 2, 16, 14, 30, tzinfo=UTC),
                "location": "Sala 2",
                "instructions": "Jejum 8h",
                "case_id": appt_case_id.hex,
            },
        )
        connection.execute(
            sa.text(
                "UPDATE cases SET appointment_reason = :reason WHERE case_id = :case_id"
            ),
            {"reason": "sem agenda", "case_id": appt_denied_case_id.hex},
        )

    await message_repo.add_message(
        CaseMessageCreateInput(
            case_id=cleanup_case_id,
            room_id="!room1:example.org",
            event_id="$origin-cleanup",
            kind="room1_origin",
            sender_user_id="@human:example.org",
        )
    )

    process_job = await queue_repo.enqueue(
        JobEnqueueInput(
            case_id=process_case_id,
            job_type="process_pdf_case",
            payload={"pdf_mxc_url": "mxc://example.org/process.pdf"},
        )
    )
    room2_job = await queue_repo.enqueue(
        JobEnqueueInput(case_id=room2_case_id, job_type="post_room2_widget", payload={})
    )
    room3_job = await queue_repo.enqueue(
        JobEnqueueInput(case_id=room3_case_id, job_type="post_room3_request", payload={})
    )
    denied_job = await queue_repo.enqueue(
        JobEnqueueInput(
            case_id=denied_case_id,
            job_type="post_room1_final_denial_triage",
            payload={},
        )
    )
    appt_job = await queue_repo.enqueue(
        JobEnqueueInput(case_id=appt_case_id, job_type="post_room1_final_appt", payload={})
    )
    appt_denied_job = await queue_repo.enqueue(
        JobEnqueueInput(
            case_id=appt_denied_case_id,
            job_type="post_room1_final_appt_denied",
            payload={},
        )
    )
    failed_job = await queue_repo.enqueue(
        JobEnqueueInput(
            case_id=failed_case_id,
            job_type="post_room1_final_failure",
            payload={"cause": "llm", "details": "schema mismatch"},
        )
    )
    cleanup_job = await queue_repo.enqueue(
        JobEnqueueInput(case_id=cleanup_case_id, job_type="execute_cleanup", payload={})
    )
    target_job_ids = {
        process_job.job_id,
        room2_job.job_id,
        room3_job.job_id,
        denied_job.job_id,
        appt_job.job_id,
        appt_denied_job.job_id,
        failed_job.job_id,
        cleanup_job.job_id,
    }

    runtime = build_worker_runtime(
        settings=settings,
        session_factory=session_factory,
        matrix_client=matrix_client,
        llm1_client=FakeLlm1Client(),
        llm2_client=FakeLlm2Client(),
    )
    claimed_count = await runtime.run_once()

    assert claimed_count >= len(target_job_ids)

    with engine.begin() as connection:
        rows = connection.execute(
            sa.text(
                "SELECT job_id, status FROM jobs WHERE job_id IN "
                "(:j1, :j2, :j3, :j4, :j5, :j6, :j7, :j8) ORDER BY job_id"
            ),
            {
                "j1": process_job.job_id,
                "j2": room2_job.job_id,
                "j3": room3_job.job_id,
                "j4": denied_job.job_id,
                "j5": appt_job.job_id,
                "j6": appt_denied_job.job_id,
                "j7": failed_job.job_id,
                "j8": cleanup_job.job_id,
            },
        ).mappings().all()

    assert all(str(row["status"]) == "done" for row in rows)
    assert matrix_client.send_calls
    assert matrix_client.reply_calls
    assert matrix_client.redaction_calls


@pytest.mark.asyncio
async def test_runtime_worker_wiring_preserves_success_and_retry_transitions(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sync_url, async_url = _upgrade_head(tmp_path, "worker_runtime_wiring_transitions.db")
    settings = _set_required_env(monkeypatch)
    session_factory = create_session_factory(async_url)

    case_repo = SqlAlchemyCaseRepository(session_factory)
    queue_repo = SqlAlchemyJobQueueRepository(session_factory)
    matrix_client = FakeMatrixRuntimeClient()

    success_case_id = await _create_case(
        case_repo,
        status=CaseStatus.DOCTOR_DENIED,
        origin_event_id="$origin-success",
    )
    retry_case_id = await _create_case(
        case_repo,
        status=CaseStatus.WAIT_DOCTOR,
        origin_event_id="$origin-retry",
    )

    engine = sa.create_engine(sync_url)
    with engine.begin() as connection:
        connection.execute(
            sa.text(
                "UPDATE cases SET doctor_reason = :reason WHERE case_id = :case_id"
            ),
            {"reason": "criterio clinico", "case_id": success_case_id.hex},
        )

    success_job = await queue_repo.enqueue(
        JobEnqueueInput(
            case_id=success_case_id,
            job_type="post_room1_final_denial_triage",
            payload={},
            max_attempts=3,
        )
    )
    retry_job = await queue_repo.enqueue(
        JobEnqueueInput(
            case_id=retry_case_id,
            job_type="post_room3_request",
            payload={},
            max_attempts=3,
        )
    )

    runtime = build_worker_runtime(
        settings=settings,
        session_factory=session_factory,
        matrix_client=matrix_client,
        llm1_client=FakeLlm1Client(),
        llm2_client=FakeLlm2Client(),
    )
    claimed_count = await runtime.run_once()

    assert claimed_count == 2

    with engine.begin() as connection:
        success_row = connection.execute(
            sa.text("SELECT status, attempts FROM jobs WHERE job_id = :job_id"),
            {"job_id": success_job.job_id},
        ).mappings().one()
        retry_row = connection.execute(
            sa.text("SELECT status, attempts, last_error FROM jobs WHERE job_id = :job_id"),
            {"job_id": retry_job.job_id},
        ).mappings().one()

    assert success_row["status"] == "done"
    assert int(success_row["attempts"]) == 0
    assert retry_row["status"] == "queued"
    assert int(retry_row["attempts"]) == 1
    assert "not ready for Room-3 request post" in str(retry_row["last_error"])


@pytest.mark.asyncio
async def test_runtime_worker_deterministic_mode_processes_llm_path_without_injected_clients(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sync_url, async_url = _upgrade_head(tmp_path, "worker_runtime_deterministic_llm.db")
    settings = _set_required_env(monkeypatch)
    session_factory = create_session_factory(async_url)

    case_repo = SqlAlchemyCaseRepository(session_factory)
    queue_repo = SqlAlchemyJobQueueRepository(session_factory)
    matrix_client = FakeMatrixRuntimeClient()

    case_id = await _create_case(
        case_repo,
        status=CaseStatus.NEW,
        origin_event_id="$origin-deterministic-llm",
    )
    process_job = await queue_repo.enqueue(
        JobEnqueueInput(
            case_id=case_id,
            job_type="process_pdf_case",
            payload={"pdf_mxc_url": "mxc://example.org/process.pdf"},
        )
    )

    runtime = build_worker_runtime(
        settings=settings,
        session_factory=session_factory,
        matrix_client=matrix_client,
    )
    claimed_count = await runtime.run_once()

    assert claimed_count == 1

    engine = sa.create_engine(sync_url)
    with engine.begin() as connection:
        process_row = connection.execute(
            sa.text("SELECT status, attempts, last_error FROM jobs WHERE job_id = :job_id"),
            {"job_id": process_job.job_id},
        ).mappings().one()
        case_row = connection.execute(
            sa.text(
                "SELECT status, structured_data_json, suggested_action_json "
                "FROM cases WHERE case_id = :case_id"
            ),
            {"case_id": case_id.hex},
        ).mappings().one()
        room2_job_count = connection.execute(
            sa.text(
                "SELECT COUNT(*) FROM jobs "
                "WHERE case_id = :case_id AND job_type = 'post_room2_widget' AND status = 'queued'"
            ),
            {"case_id": case_id.hex},
        ).scalar_one()
        llm1_event_count = connection.execute(
            sa.text(
                "SELECT COUNT(*) FROM case_events "
                "WHERE case_id = :case_id AND event_type = 'LLM1_STRUCTURED_SUMMARY_OK'"
            ),
            {"case_id": case_id.hex},
        ).scalar_one()
        llm2_event_count = connection.execute(
            sa.text(
                "SELECT COUNT(*) FROM case_events "
                "WHERE case_id = :case_id AND event_type = 'LLM2_SUGGESTION_OK'"
            ),
            {"case_id": case_id.hex},
        ).scalar_one()

    assert process_row["status"] == "done"
    assert int(process_row["attempts"]) == 0
    assert process_row["last_error"] is None
    assert case_row["status"] == "LLM_SUGGEST"
    assert case_row["structured_data_json"] is not None
    assert case_row["suggested_action_json"] is not None
    assert int(room2_job_count) == 1
    assert int(llm1_event_count) == 1
    assert int(llm2_event_count) == 1

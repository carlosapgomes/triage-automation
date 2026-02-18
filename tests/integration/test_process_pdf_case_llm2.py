from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
import sqlalchemy as sa
from alembic.config import Config

from alembic import command
from triage_automation.application.ports.case_repository_port import CaseCreateInput
from triage_automation.application.services.llm1_service import Llm1Service
from triage_automation.application.services.llm2_service import Llm2Service
from triage_automation.application.services.process_pdf_case_service import (
    ProcessPdfCaseRetriableError,
    ProcessPdfCaseService,
)
from triage_automation.domain.case_status import CaseStatus
from triage_automation.infrastructure.db.audit_repository import SqlAlchemyAuditRepository
from triage_automation.infrastructure.db.case_repository import SqlAlchemyCaseRepository
from triage_automation.infrastructure.db.job_queue_repository import SqlAlchemyJobQueueRepository
from triage_automation.infrastructure.db.session import create_session_factory
from triage_automation.infrastructure.llm.openai_client import (
    OpenAiChatCompletionsClient,
    OpenAiHttpResponse,
)
from triage_automation.infrastructure.matrix.mxc_downloader import MatrixMxcDownloader
from triage_automation.infrastructure.pdf.text_extractor import PdfTextExtractor


class FakeMatrixMediaClient:
    def __init__(self, payload: bytes) -> None:
        self._payload = payload

    async def download_mxc(self, mxc_url: str) -> bytes:
        return self._payload


class FakeLlmClient:
    def __init__(self, response_text: str) -> None:
        self._response_text = response_text

    async def complete(self, *, system_prompt: str, user_prompt: str) -> str:
        return self._response_text


class FakeOpenAiTransport:
    def __init__(self, payloads: list[dict[str, object]]) -> None:
        self._payloads = payloads

    async def request(
        self,
        *,
        method: str,
        url: str,
        headers: dict[str, str],
        body: bytes | None,
        timeout_seconds: float,
    ) -> OpenAiHttpResponse:
        _ = method, url, headers, body, timeout_seconds
        payload = self._payloads.pop(0)
        return OpenAiHttpResponse(
            status_code=200,
            body_bytes=json.dumps(payload).encode("utf-8"),
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

    for idx, body in enumerate(objects, start=1):
        offsets.append(sum(len(part) for part in parts))
        parts.append(f"{idx} 0 obj\n{body}\nendobj\n".encode("latin-1"))

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


def _upgrade_head(tmp_path: Path, filename: str) -> tuple[str, str]:
    db_path = tmp_path / filename
    sync_url = f"sqlite+pysqlite:///{db_path}"
    async_url = f"sqlite+aiosqlite:///{db_path}"

    alembic_config = Config("alembic.ini")
    alembic_config.set_main_option("sqlalchemy.url", sync_url)
    command.upgrade(alembic_config, "head")

    return sync_url, async_url


def _valid_llm1_payload(agency_record_number: str) -> dict[str, object]:
    return {
        "schema_version": "1.1",
        "language": "pt-BR",
        "agency_record_number": agency_record_number,
        "patient": {"name": "Paciente", "age": 50, "sex": "F", "document_id": None},
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


def _valid_llm2_payload(case_id: str, agency_record_number: str) -> dict[str, object]:
    return {
        "schema_version": "1.1",
        "language": "pt-BR",
        "case_id": case_id,
        "agency_record_number": agency_record_number,
        "suggestion": "accept",
        "support_recommendation": "none",
        "rationale": {
            "short_reason": "Apto para fluxo padrao",
            "details": ["criterio 1", "criterio 2"],
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


def _decode_json(value: Any) -> dict[str, Any]:
    if isinstance(value, str):
        parsed = json.loads(value)
        assert isinstance(parsed, dict)
        return parsed
    assert isinstance(value, dict)
    return value


@pytest.mark.asyncio
async def test_llm2_persists_suggestion_and_enqueues_room2_widget_job(tmp_path: Path) -> None:
    sync_url, async_url = _upgrade_head(tmp_path, "llm2_ok.db")
    session_factory = create_session_factory(async_url)

    case_repo = SqlAlchemyCaseRepository(session_factory)
    queue_repo = SqlAlchemyJobQueueRepository(session_factory)

    case = await case_repo.create_case(
        CaseCreateInput(
            case_id=uuid4(),
            status=CaseStatus.R1_ACK_PROCESSING,
            room1_origin_room_id="!room1:example.org",
            room1_origin_event_id="$origin-llm2-1",
            room1_sender_user_id="@human:example.org",
        )
    )

    llm1_service = Llm1Service(
        llm_client=FakeLlmClient(json.dumps(_valid_llm1_payload("12345")))
    )
    llm2_service = Llm2Service(
        llm_client=FakeLlmClient(json.dumps(_valid_llm2_payload(str(case.case_id), "12345")))
    )

    service = ProcessPdfCaseService(
        case_repository=case_repo,
        mxc_downloader=MatrixMxcDownloader(
            FakeMatrixMediaClient(
                _build_simple_pdf(
                    "RELATORIO DE OCORRENCIAS 12345 " "clinical text 12345"
                )
            )
        ),
        text_extractor=PdfTextExtractor(),
        llm1_service=llm1_service,
        llm2_service=llm2_service,
        job_queue=queue_repo,
    )

    await service.process_case(case_id=case.case_id, pdf_mxc_url="mxc://example.org/pdf")

    engine = sa.create_engine(sync_url)
    with engine.begin() as connection:
        row = connection.execute(
            sa.text(
                "SELECT status, suggested_action_json "
                "FROM cases ORDER BY created_at DESC LIMIT 1"
            )
        ).mappings().one()
        interaction_rows = connection.execute(
            sa.text(
                "SELECT stage, input_payload, output_payload, "
                "prompt_system_name, prompt_system_version, "
                "prompt_user_name, prompt_user_version, model_name "
                "FROM case_llm_interactions "
                "WHERE case_id = :case_id "
                "ORDER BY id"
            ),
            {"case_id": case.case_id.hex},
        ).mappings().all()
        job_count = connection.execute(
            sa.text("SELECT COUNT(*) FROM jobs WHERE job_type = 'post_room2_widget'")
        ).scalar_one()

    suggested_action = _decode_json(row["suggested_action_json"])

    assert row["status"] == "LLM_SUGGEST"
    assert suggested_action["suggestion"] == "accept"
    assert job_count == 1
    assert len(interaction_rows) == 2

    llm1_row = interaction_rows[0]
    llm1_input = _decode_json(llm1_row["input_payload"])
    llm1_output = _decode_json(llm1_row["output_payload"])
    assert llm1_row["stage"] == "LLM1"
    assert llm1_row["prompt_system_name"] == "llm1_system"
    assert llm1_row["prompt_system_version"] == 0
    assert llm1_row["prompt_user_name"] == "llm1_user"
    assert llm1_row["prompt_user_version"] == 0
    assert llm1_row["model_name"] is None
    assert "system_prompt" in llm1_input
    assert "user_prompt" in llm1_input
    assert llm1_output["raw_response"] == json.dumps(_valid_llm1_payload("12345"))

    llm2_row = interaction_rows[1]
    llm2_input = _decode_json(llm2_row["input_payload"])
    llm2_output = _decode_json(llm2_row["output_payload"])
    assert llm2_row["stage"] == "LLM2"
    assert llm2_row["prompt_system_name"] == "llm2_system"
    assert llm2_row["prompt_system_version"] == 0
    assert llm2_row["prompt_user_name"] == "llm2_user"
    assert llm2_row["prompt_user_version"] == 0
    assert llm2_row["model_name"] is None
    assert "system_prompt" in llm2_input
    assert "user_prompt" in llm2_input
    assert str(case.case_id) in str(llm2_input["user_prompt"])
    assert llm2_output["raw_response"] == json.dumps(
        _valid_llm2_payload(str(case.case_id), "12345")
    )


@pytest.mark.asyncio
async def test_llm2_contradiction_emits_audit_event_and_forces_deny(tmp_path: Path) -> None:
    sync_url, async_url = _upgrade_head(tmp_path, "llm2_contradiction.db")
    session_factory = create_session_factory(async_url)

    case_repo = SqlAlchemyCaseRepository(session_factory)
    queue_repo = SqlAlchemyJobQueueRepository(session_factory)
    audit_repo = SqlAlchemyAuditRepository(session_factory)

    case = await case_repo.create_case(
        CaseCreateInput(
            case_id=uuid4(),
            status=CaseStatus.R1_ACK_PROCESSING,
            room1_origin_room_id="!room1:example.org",
            room1_origin_event_id="$origin-llm2-2",
            room1_sender_user_id="@human:example.org",
        )
    )

    llm1_payload = _valid_llm1_payload("12345")
    llm1_payload["policy_precheck"] = {
        "excluded_from_eda_flow": True,
        "exclusion_reason": "fora do fluxo",
        "labs_required": True,
        "labs_pass": "no",
        "labs_failed_items": ["hb"],
        "ecg_required": True,
        "ecg_present": "no",
        "pediatric_flag": False,
        "notes": None,
    }

    llm2_payload = _valid_llm2_payload(str(case.case_id), "12345")
    llm2_payload["suggestion"] = "accept"
    llm2_payload["policy_alignment"] = {
        "excluded_request": False,
        "labs_ok": "yes",
        "ecg_ok": "yes",
        "pediatric_flag": False,
        "notes": None,
    }

    llm1_service = Llm1Service(llm_client=FakeLlmClient(json.dumps(llm1_payload)))
    llm2_service = Llm2Service(llm_client=FakeLlmClient(json.dumps(llm2_payload)))

    service = ProcessPdfCaseService(
        case_repository=case_repo,
        mxc_downloader=MatrixMxcDownloader(
            FakeMatrixMediaClient(
                _build_simple_pdf(
                    "RELATORIO DE OCORRENCIAS 12345 " "clinical text 12345"
                )
            )
        ),
        text_extractor=PdfTextExtractor(),
        llm1_service=llm1_service,
        llm2_service=llm2_service,
        audit_repository=audit_repo,
        job_queue=queue_repo,
    )

    await service.process_case(case_id=case.case_id, pdf_mxc_url="mxc://example.org/pdf")

    engine = sa.create_engine(sync_url)
    with engine.begin() as connection:
        row = connection.execute(
            sa.text("SELECT suggested_action_json FROM cases ORDER BY created_at DESC LIMIT 1")
        ).mappings().one()
        contradiction_events = connection.execute(
            sa.text(
                "SELECT COUNT(*) FROM case_events "
                "WHERE event_type = 'LLM_CONTRADICTION_DETECTED'"
            )
        ).scalar_one()

    suggested_action = _decode_json(row["suggested_action_json"])

    assert suggested_action["suggestion"] == "deny"
    assert suggested_action["policy_alignment"]["excluded_request"] is True
    assert contradiction_events == 1


@pytest.mark.asyncio
async def test_runtime_provider_adapter_preserves_llm2_retriable_mapping(
    tmp_path: Path,
) -> None:
    sync_url, async_url = _upgrade_head(tmp_path, "llm2_provider_non_json.db")
    session_factory = create_session_factory(async_url)

    case_repo = SqlAlchemyCaseRepository(session_factory)
    queue_repo = SqlAlchemyJobQueueRepository(session_factory)

    case = await case_repo.create_case(
        CaseCreateInput(
            case_id=uuid4(),
            status=CaseStatus.R1_ACK_PROCESSING,
            room1_origin_room_id="!room1:example.org",
            room1_origin_event_id="$origin-llm2-provider-1",
            room1_sender_user_id="@human:example.org",
        )
    )

    llm1_payload: dict[str, object] = {
        "choices": [{"message": {"content": json.dumps(_valid_llm1_payload("12345"))}}]
    }
    llm2_payload: dict[str, object] = {
        "choices": [{"message": {"content": "not-json"}}]
    }

    llm1_service = Llm1Service(
        llm_client=OpenAiChatCompletionsClient(
            api_key="sk-test",
            model="gpt-4o-mini",
            transport=FakeOpenAiTransport([llm1_payload]),
        )
    )
    llm2_service = Llm2Service(
        llm_client=OpenAiChatCompletionsClient(
            api_key="sk-test",
            model="gpt-4o-mini",
            transport=FakeOpenAiTransport([llm2_payload]),
        )
    )

    service = ProcessPdfCaseService(
        case_repository=case_repo,
        mxc_downloader=MatrixMxcDownloader(
            FakeMatrixMediaClient(
                _build_simple_pdf(
                    "RELATORIO DE OCORRENCIAS 12345 " "clinical text 12345"
                )
            )
        ),
        text_extractor=PdfTextExtractor(),
        llm1_service=llm1_service,
        llm2_service=llm2_service,
        job_queue=queue_repo,
    )

    with pytest.raises(ProcessPdfCaseRetriableError) as error_info:
        await service.process_case(case_id=case.case_id, pdf_mxc_url="mxc://example.org/pdf")

    engine = sa.create_engine(sync_url)
    with engine.begin() as connection:
        interaction_rows = connection.execute(
            sa.text(
                "SELECT stage, model_name, output_payload "
                "FROM case_llm_interactions "
                "WHERE case_id = :case_id "
                "ORDER BY id"
            ),
            {"case_id": case.case_id.hex},
        ).mappings().all()

    assert error_info.value.cause == "llm2"
    assert "LLM2 returned non-JSON payload" in error_info.value.details
    assert len(interaction_rows) == 2
    assert interaction_rows[0]["stage"] == "LLM1"
    assert interaction_rows[0]["model_name"] == "gpt-4o-mini"
    assert interaction_rows[1]["stage"] == "LLM2"
    assert interaction_rows[1]["model_name"] == "gpt-4o-mini"
    assert _decode_json(interaction_rows[1]["output_payload"])["raw_response"] == "not-json"

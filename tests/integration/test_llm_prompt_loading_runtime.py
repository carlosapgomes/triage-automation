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
from triage_automation.application.services.prompt_template_service import PromptTemplateService
from triage_automation.domain.case_status import CaseStatus
from triage_automation.infrastructure.db.audit_repository import SqlAlchemyAuditRepository
from triage_automation.infrastructure.db.case_repository import SqlAlchemyCaseRepository
from triage_automation.infrastructure.db.job_queue_repository import SqlAlchemyJobQueueRepository
from triage_automation.infrastructure.db.prompt_template_repository import (
    SqlAlchemyPromptTemplateRepository,
)
from triage_automation.infrastructure.db.session import create_session_factory
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
        self.calls: list[tuple[str, str]] = []

    async def complete(self, *, system_prompt: str, user_prompt: str) -> str:
        self.calls.append((system_prompt, user_prompt))
        return self._response_text


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


def _insert_prompt(
    *,
    connection: sa.Connection,
    name: str,
    version: int,
    content: str,
    is_active: bool,
) -> None:
    connection.execute(
        sa.text(
            "INSERT INTO prompt_templates (id, name, version, content, is_active) "
            "VALUES (:id, :name, :version, :content, :is_active)"
        ),
        {
            "id": uuid4().hex,
            "name": name,
            "version": version,
            "content": content,
            "is_active": is_active,
        },
    )


@pytest.mark.asyncio
async def test_llm1_and_llm2_load_active_prompts_and_audit_prompt_versions(
    tmp_path: Path,
) -> None:
    sync_url, async_url = _upgrade_head(tmp_path, "llm_prompt_loading_runtime.db")
    session_factory = create_session_factory(async_url)
    engine = sa.create_engine(sync_url)

    with engine.begin() as connection:
        _insert_prompt(
            connection=connection,
            name="custom_llm1_system",
            version=2,
            content="CUSTOM LLM1 SYSTEM",
            is_active=True,
        )
        _insert_prompt(
            connection=connection,
            name="custom_llm1_user",
            version=5,
            content="CUSTOM LLM1 USER",
            is_active=True,
        )
        _insert_prompt(
            connection=connection,
            name="custom_llm2_system",
            version=4,
            content="CUSTOM LLM2 SYSTEM",
            is_active=True,
        )
        _insert_prompt(
            connection=connection,
            name="custom_llm2_user",
            version=6,
            content="CUSTOM LLM2 USER",
            is_active=True,
        )

    prompt_service = PromptTemplateService(
        prompt_templates=SqlAlchemyPromptTemplateRepository(session_factory)
    )
    llm1_client = FakeLlmClient(json.dumps(_valid_llm1_payload("12345")))
    llm2_case_id = uuid4()
    llm2_client = FakeLlmClient(json.dumps(_valid_llm2_payload(str(llm2_case_id), "12345")))

    case_repo = SqlAlchemyCaseRepository(session_factory)
    queue_repo = SqlAlchemyJobQueueRepository(session_factory)
    audit_repo = SqlAlchemyAuditRepository(session_factory)
    case = await case_repo.create_case(
        CaseCreateInput(
            case_id=uuid4(),
            status=CaseStatus.R1_ACK_PROCESSING,
            room1_origin_room_id="!room1:example.org",
            room1_origin_event_id="$origin-llm-prompts-1",
            room1_sender_user_id="@human:example.org",
        )
    )
    llm2_client._response_text = json.dumps(_valid_llm2_payload(str(case.case_id), "12345"))

    service = ProcessPdfCaseService(
        case_repository=case_repo,
        mxc_downloader=MatrixMxcDownloader(
            FakeMatrixMediaClient(_build_simple_pdf("12345 clinical text 12345"))
        ),
        text_extractor=PdfTextExtractor(),
        llm1_service=Llm1Service(
            llm_client=llm1_client,
            prompt_templates=prompt_service,
            system_prompt_name="custom_llm1_system",
            user_prompt_name="custom_llm1_user",
        ),
        llm2_service=Llm2Service(
            llm_client=llm2_client,
            prompt_templates=prompt_service,
            system_prompt_name="custom_llm2_system",
            user_prompt_name="custom_llm2_user",
        ),
        audit_repository=audit_repo,
        job_queue=queue_repo,
    )

    await service.process_case(case_id=case.case_id, pdf_mxc_url="mxc://example.org/pdf")

    llm1_system_prompt, llm1_user_prompt = llm1_client.calls[0]
    assert llm1_system_prompt == "CUSTOM LLM1 SYSTEM"
    assert "CUSTOM LLM1 USER" in llm1_user_prompt

    llm2_system_prompt, llm2_user_prompt = llm2_client.calls[0]
    assert llm2_system_prompt == "CUSTOM LLM2 SYSTEM"
    assert "CUSTOM LLM2 USER" in llm2_user_prompt

    with engine.begin() as connection:
        llm1_event = connection.execute(
            sa.text(
                "SELECT payload FROM case_events "
                "WHERE case_id = :case_id AND event_type = 'LLM1_STRUCTURED_SUMMARY_OK'"
            ),
            {"case_id": case.case_id.hex},
        ).scalar_one()
        llm2_event = connection.execute(
            sa.text(
                "SELECT payload FROM case_events "
                "WHERE case_id = :case_id AND event_type = 'LLM2_SUGGESTION_OK'"
            ),
            {"case_id": case.case_id.hex},
        ).scalar_one()

    llm1_payload = _decode_json(llm1_event)
    assert llm1_payload["prompt_system_name"] == "custom_llm1_system"
    assert llm1_payload["prompt_system_version"] == 2
    assert llm1_payload["prompt_user_name"] == "custom_llm1_user"
    assert llm1_payload["prompt_user_version"] == 5

    llm2_payload = _decode_json(llm2_event)
    assert llm2_payload["prompt_system_name"] == "custom_llm2_system"
    assert llm2_payload["prompt_system_version"] == 4
    assert llm2_payload["prompt_user_name"] == "custom_llm2_user"
    assert llm2_payload["prompt_user_version"] == 6


@pytest.mark.asyncio
async def test_default_prompt_names_resolve_seeded_rows(tmp_path: Path) -> None:
    _, async_url = _upgrade_head(tmp_path, "llm_prompt_seeded_defaults.db")
    session_factory = create_session_factory(async_url)

    prompt_service = PromptTemplateService(
        prompt_templates=SqlAlchemyPromptTemplateRepository(session_factory)
    )
    llm1_client = FakeLlmClient(json.dumps(_valid_llm1_payload("12345")))
    llm2_case_id = uuid4()
    llm2_client = FakeLlmClient(json.dumps(_valid_llm2_payload(str(llm2_case_id), "12345")))

    llm1 = Llm1Service(llm_client=llm1_client, prompt_templates=prompt_service)
    llm2 = Llm2Service(llm_client=llm2_client, prompt_templates=prompt_service)

    llm1_result = await llm1.run(
        case_id=uuid4(),
        agency_record_number="12345",
        clean_text="texto",
    )
    llm2_result = await llm2.run(
        case_id=llm2_case_id,
        agency_record_number="12345",
        llm1_structured_data=_valid_llm1_payload("12345"),
    )

    llm1_system_prompt, llm1_user_prompt = llm1_client.calls[0]
    assert llm1_system_prompt == "DEFAULT LLM1 SYSTEM PROMPT v1"
    assert "DEFAULT LLM1 USER PROMPT v1" in llm1_user_prompt
    assert llm1_result.prompt_system_name == "llm1_system"
    assert llm1_result.prompt_user_name == "llm1_user"

    llm2_system_prompt, llm2_user_prompt = llm2_client.calls[0]
    assert llm2_system_prompt == "DEFAULT LLM2 SYSTEM PROMPT v1"
    assert "DEFAULT LLM2 USER PROMPT v1" in llm2_user_prompt
    assert llm2_result.prompt_system_name == "llm2_system"
    assert llm2_result.prompt_user_name == "llm2_user"


@pytest.mark.asyncio
async def test_missing_active_prompt_is_explicit_and_retriable_for_job_path(tmp_path: Path) -> None:
    _, async_url = _upgrade_head(tmp_path, "llm_prompt_missing.db")
    session_factory = create_session_factory(async_url)

    prompt_service = PromptTemplateService(
        prompt_templates=SqlAlchemyPromptTemplateRepository(session_factory)
    )
    llm1_client = FakeLlmClient(json.dumps(_valid_llm1_payload("12345")))

    case_repo = SqlAlchemyCaseRepository(session_factory)
    case = await case_repo.create_case(
        CaseCreateInput(
            case_id=uuid4(),
            status=CaseStatus.R1_ACK_PROCESSING,
            room1_origin_room_id="!room1:example.org",
            room1_origin_event_id="$origin-llm-prompts-2",
            room1_sender_user_id="@human:example.org",
        )
    )

    service = ProcessPdfCaseService(
        case_repository=case_repo,
        mxc_downloader=MatrixMxcDownloader(
            FakeMatrixMediaClient(_build_simple_pdf("12345 clinical text 12345"))
        ),
        text_extractor=PdfTextExtractor(),
        llm1_service=Llm1Service(
            llm_client=llm1_client,
            prompt_templates=prompt_service,
            system_prompt_name="missing_system_prompt",
            user_prompt_name="missing_user_prompt",
        ),
    )

    with pytest.raises(ProcessPdfCaseRetriableError) as error_info:
        await service.process_case(case_id=case.case_id, pdf_mxc_url="mxc://example.org/pdf")

    assert error_info.value.cause == "llm1"
    assert "Missing active prompt template" in error_info.value.details

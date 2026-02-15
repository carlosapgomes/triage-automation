from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

import pytest
import sqlalchemy as sa
from alembic.config import Config

from alembic import command
from triage_automation.application.ports.case_repository_port import CaseCreateInput
from triage_automation.application.services.llm1_service import Llm1Service
from triage_automation.application.services.process_pdf_case_service import (
    ProcessPdfCaseRetriableError,
    ProcessPdfCaseService,
)
from triage_automation.domain.case_status import CaseStatus
from triage_automation.infrastructure.db.case_repository import SqlAlchemyCaseRepository
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

    async def complete(self, *, system_prompt: str, user_prompt: str) -> str:
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
            "ecg": {"report_present": "yes", "abnormal_flag": "no", "source_text_hint": None},
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


@pytest.mark.asyncio
async def test_valid_llm1_response_persists_structured_data_and_summary(tmp_path: Path) -> None:
    sync_url, async_url = _upgrade_head(tmp_path, "llm1_ok.db")
    session_factory = create_session_factory(async_url)
    case_repo = SqlAlchemyCaseRepository(session_factory)

    case = await case_repo.create_case(
        CaseCreateInput(
            case_id=uuid4(),
            status=CaseStatus.R1_ACK_PROCESSING,
            room1_origin_room_id="!room1:example.org",
            room1_origin_event_id="$origin-llm1-1",
            room1_sender_user_id="@human:example.org",
        )
    )

    llm1_service = Llm1Service(
        llm_client=FakeLlmClient(json.dumps(_valid_llm1_payload("12345")))
    )
    service = ProcessPdfCaseService(
        case_repository=case_repo,
        mxc_downloader=MatrixMxcDownloader(
            FakeMatrixMediaClient(_build_simple_pdf("12345 clinical text 12345"))
        ),
        text_extractor=PdfTextExtractor(),
        llm1_service=llm1_service,
    )

    cleaned = await service.process_case(case_id=case.case_id, pdf_mxc_url="mxc://example.org/pdf")

    assert cleaned == "clinical text"

    engine = sa.create_engine(sync_url)
    with engine.begin() as connection:
        row = connection.execute(
            sa.text(
                "SELECT status, structured_data_json, summary_text "
                "FROM cases ORDER BY created_at DESC LIMIT 1"
            )
        ).mappings().one()

    assert row["status"] == "LLM_STRUCT"
    assert row["structured_data_json"] is not None
    assert row["summary_text"] == "Resumo LLM1"


@pytest.mark.asyncio
async def test_invalid_llm1_schema_maps_to_retriable_llm1_error(tmp_path: Path) -> None:
    _, async_url = _upgrade_head(tmp_path, "llm1_schema_fail.db")
    session_factory = create_session_factory(async_url)
    case_repo = SqlAlchemyCaseRepository(session_factory)

    case = await case_repo.create_case(
        CaseCreateInput(
            case_id=uuid4(),
            status=CaseStatus.R1_ACK_PROCESSING,
            room1_origin_room_id="!room1:example.org",
            room1_origin_event_id="$origin-llm1-2",
            room1_sender_user_id="@human:example.org",
        )
    )

    llm1_service = Llm1Service(llm_client=FakeLlmClient(json.dumps({"schema_version": "1.1"})))
    service = ProcessPdfCaseService(
        case_repository=case_repo,
        mxc_downloader=MatrixMxcDownloader(
            FakeMatrixMediaClient(_build_simple_pdf("12345 clinical text 12345"))
        ),
        text_extractor=PdfTextExtractor(),
        llm1_service=llm1_service,
    )

    with pytest.raises(ProcessPdfCaseRetriableError) as exc_info:
        await service.process_case(case_id=case.case_id, pdf_mxc_url="mxc://example.org/pdf")

    assert exc_info.value.cause == "llm1"

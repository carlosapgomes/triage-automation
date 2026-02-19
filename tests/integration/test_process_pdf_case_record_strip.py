from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
import sqlalchemy as sa
from alembic.config import Config

from alembic import command
from triage_automation.application.ports.case_repository_port import CaseCreateInput
from triage_automation.application.services.process_pdf_case_service import ProcessPdfCaseService
from triage_automation.domain.case_status import CaseStatus
from triage_automation.infrastructure.db.case_repository import SqlAlchemyCaseRepository
from triage_automation.infrastructure.db.session import create_session_factory
from triage_automation.infrastructure.matrix.mxc_downloader import MatrixMxcDownloader
from triage_automation.infrastructure.pdf.text_extractor import PdfTextExtractor


class FakeMatrixMediaClient:
    def __init__(self, *, payload: bytes | None = None) -> None:
        self._payload = payload

    async def download_mxc(self, mxc_url: str) -> bytes:
        assert self._payload is not None
        return self._payload


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


@pytest.mark.asyncio
async def test_record_number_persisted_and_stripped_from_text(tmp_path: Path) -> None:
    sync_url, async_url = _upgrade_head(tmp_path, "record_strip_ok.db")
    session_factory = create_session_factory(async_url)
    case_repo = SqlAlchemyCaseRepository(session_factory)

    case = await case_repo.create_case(
        CaseCreateInput(
            case_id=uuid4(),
            status=CaseStatus.R1_ACK_PROCESSING,
            room1_origin_room_id="!room1:example.org",
            room1_origin_event_id="$origin-rs-1",
            room1_sender_user_id="@human:example.org",
        )
    )

    text = "RELATORIO DE OCORRENCIAS 12345 patient data 12345 details 99999 12345"
    service = ProcessPdfCaseService(
        case_repository=case_repo,
        mxc_downloader=MatrixMxcDownloader(
            FakeMatrixMediaClient(payload=_build_simple_pdf(text))
        ),
        text_extractor=PdfTextExtractor(),
    )

    cleaned = await service.process_case(case_id=case.case_id, pdf_mxc_url="mxc://example.org/pdf")

    assert cleaned == "RELATORIO DE OCORRENCIAS patient data details 99999"

    engine = sa.create_engine(sync_url)
    with engine.begin() as connection:
        row = connection.execute(
            sa.text(
                "SELECT agency_record_number, agency_record_extracted_at, extracted_text "
                "FROM cases ORDER BY created_at DESC LIMIT 1"
            )
        ).mappings().one()
        transcript_row = connection.execute(
            sa.text(
                "SELECT extracted_text, captured_at "
                "FROM case_report_transcripts "
                "WHERE case_id = :case_id "
                "ORDER BY id DESC LIMIT 1"
            ),
            {"case_id": case.case_id.hex},
        ).mappings().one()

    assert row["agency_record_number"] == "12345"
    assert row["agency_record_extracted_at"] is not None
    assert row["extracted_text"] == "RELATORIO DE OCORRENCIAS patient data details 99999"
    assert transcript_row["extracted_text"] == "RELATORIO DE OCORRENCIAS patient data details 99999"
    assert transcript_row["captured_at"] is not None


@pytest.mark.asyncio
async def test_missing_record_number_falls_back_to_epoch_millis(tmp_path: Path) -> None:
    sync_url, async_url = _upgrade_head(tmp_path, "record_strip_fallback.db")
    session_factory = create_session_factory(async_url)
    case_repo = SqlAlchemyCaseRepository(session_factory)

    case = await case_repo.create_case(
        CaseCreateInput(
            case_id=uuid4(),
            status=CaseStatus.R1_ACK_PROCESSING,
            room1_origin_room_id="!room1:example.org",
            room1_origin_event_id="$origin-rs-2",
            room1_sender_user_id="@human:example.org",
        )
    )

    service = ProcessPdfCaseService(
        case_repository=case_repo,
        mxc_downloader=MatrixMxcDownloader(
            FakeMatrixMediaClient(payload=_build_simple_pdf("no token"))
        ),
        text_extractor=PdfTextExtractor(),
    )

    cleaned = await service.process_case(case_id=case.case_id, pdf_mxc_url="mxc://example.org/pdf")

    assert cleaned == "no token"

    engine = sa.create_engine(sync_url)
    with engine.begin() as connection:
        row = connection.execute(
            sa.text(
                "SELECT agency_record_number, agency_record_extracted_at, extracted_text "
                "FROM cases ORDER BY created_at DESC LIMIT 1"
            )
        ).mappings().one()

    assert row["agency_record_extracted_at"] is not None
    assert isinstance(row["agency_record_number"], str)
    assert row["agency_record_number"].isdigit()
    assert len(row["agency_record_number"]) >= 13
    assert row["extracted_text"] == "no token"

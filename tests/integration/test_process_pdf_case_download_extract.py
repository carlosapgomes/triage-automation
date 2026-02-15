from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
import sqlalchemy as sa
from alembic.config import Config

from alembic import command
from triage_automation.application.ports.case_repository_port import CaseCreateInput
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
    def __init__(self, *, payload: bytes | None = None, should_fail: bool = False) -> None:
        self._payload = payload
        self._should_fail = should_fail

    async def download_mxc(self, mxc_url: str) -> bytes:
        if self._should_fail:
            raise RuntimeError(f"download failed for {mxc_url}")
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
async def test_download_extract_updates_case_status_and_text(tmp_path: Path) -> None:
    sync_url, async_url = _upgrade_head(tmp_path, "process_ok.db")
    session_factory = create_session_factory(async_url)
    case_repo = SqlAlchemyCaseRepository(session_factory)

    case = await case_repo.create_case(
        CaseCreateInput(
            case_id=uuid4(),
            status=CaseStatus.R1_ACK_PROCESSING,
            room1_origin_room_id="!room1:example.org",
            room1_origin_event_id="$origin-1",
            room1_sender_user_id="@human:example.org",
        )
    )

    service = ProcessPdfCaseService(
        case_repository=case_repo,
        mxc_downloader=MatrixMxcDownloader(
            FakeMatrixMediaClient(payload=_build_simple_pdf("Clinical text"))
        ),
        text_extractor=PdfTextExtractor(),
    )

    extracted = await service.process_case(case_id=case.case_id, pdf_mxc_url="mxc://example.org/pdf")

    assert "Clinical text" in extracted

    engine = sa.create_engine(sync_url)
    with engine.begin() as connection:
        row = connection.execute(
            sa.text(
                "SELECT status, extracted_text, pdf_mxc_url "
                "FROM cases ORDER BY created_at DESC LIMIT 1"
            )
        ).mappings().one()

    assert row["status"] == "EXTRACTING"
    assert "Clinical text" in str(row["extracted_text"])
    assert row["pdf_mxc_url"] == "mxc://example.org/pdf"


@pytest.mark.asyncio
async def test_download_failure_maps_to_retriable_download_error(tmp_path: Path) -> None:
    sync_url, async_url = _upgrade_head(tmp_path, "process_download_fail.db")
    session_factory = create_session_factory(async_url)
    case_repo = SqlAlchemyCaseRepository(session_factory)

    case = await case_repo.create_case(
        CaseCreateInput(
            case_id=uuid4(),
            status=CaseStatus.R1_ACK_PROCESSING,
            room1_origin_room_id="!room1:example.org",
            room1_origin_event_id="$origin-2",
            room1_sender_user_id="@human:example.org",
        )
    )

    service = ProcessPdfCaseService(
        case_repository=case_repo,
        mxc_downloader=MatrixMxcDownloader(FakeMatrixMediaClient(should_fail=True)),
        text_extractor=PdfTextExtractor(),
    )

    with pytest.raises(ProcessPdfCaseRetriableError) as exc_info:
        await service.process_case(case_id=case.case_id, pdf_mxc_url="mxc://example.org/pdf")

    assert exc_info.value.cause == "download"

    engine = sa.create_engine(sync_url)
    with engine.begin() as connection:
        status = connection.execute(
            sa.text("SELECT status FROM cases ORDER BY created_at DESC LIMIT 1"),
        ).scalar_one()

    assert status == "EXTRACTING"


@pytest.mark.asyncio
async def test_extraction_failure_maps_to_retriable_extract_error(tmp_path: Path) -> None:
    sync_url, async_url = _upgrade_head(tmp_path, "process_extract_fail.db")
    session_factory = create_session_factory(async_url)
    case_repo = SqlAlchemyCaseRepository(session_factory)

    case = await case_repo.create_case(
        CaseCreateInput(
            case_id=uuid4(),
            status=CaseStatus.R1_ACK_PROCESSING,
            room1_origin_room_id="!room1:example.org",
            room1_origin_event_id="$origin-3",
            room1_sender_user_id="@human:example.org",
        )
    )

    service = ProcessPdfCaseService(
        case_repository=case_repo,
        mxc_downloader=MatrixMxcDownloader(FakeMatrixMediaClient(payload=b"not a pdf")),
        text_extractor=PdfTextExtractor(),
    )

    with pytest.raises(ProcessPdfCaseRetriableError) as exc_info:
        await service.process_case(case_id=case.case_id, pdf_mxc_url="mxc://example.org/pdf")

    assert exc_info.value.cause == "extract"

    engine = sa.create_engine(sync_url)
    with engine.begin() as connection:
        status = connection.execute(
            sa.text("SELECT status FROM cases ORDER BY created_at DESC LIMIT 1"),
        ).scalar_one()

    assert status == "EXTRACTING"

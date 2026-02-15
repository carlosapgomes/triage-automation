"""Service layer for process_pdf_case job (download + extract segment)."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from triage_automation.application.ports.case_repository_port import CaseRepositoryPort
from triage_automation.domain.case_status import CaseStatus
from triage_automation.infrastructure.matrix.mxc_downloader import (
    MatrixMxcDownloader,
    MxcDownloadError,
)
from triage_automation.infrastructure.pdf.text_extractor import (
    PdfTextExtractionError,
    PdfTextExtractor,
)


@dataclass(frozen=True)
class ProcessPdfCaseRetriableError(RuntimeError):
    """Retriable processing error with explicit failure cause category."""

    cause: str
    details: str

    def __str__(self) -> str:
        return f"{self.cause}: {self.details}"


class ProcessPdfCaseService:
    """Run download/extraction stages for PDF case processing."""

    def __init__(
        self,
        *,
        case_repository: CaseRepositoryPort,
        mxc_downloader: MatrixMxcDownloader,
        text_extractor: PdfTextExtractor,
    ) -> None:
        self._case_repository = case_repository
        self._mxc_downloader = mxc_downloader
        self._text_extractor = text_extractor

    async def process_case(self, *, case_id: UUID, pdf_mxc_url: str) -> str:
        """Download and extract case PDF content with retriable failure mapping."""

        await self._case_repository.update_status(case_id=case_id, status=CaseStatus.EXTRACTING)

        try:
            pdf_bytes = await self._mxc_downloader.download_pdf(pdf_mxc_url)
        except MxcDownloadError as error:
            raise ProcessPdfCaseRetriableError(cause="download", details=str(error)) from error

        try:
            extracted_text = self._text_extractor.extract_text(pdf_bytes)
            if not extracted_text:
                raise PdfTextExtractionError("PDF extraction produced empty text")
        except PdfTextExtractionError as error:
            raise ProcessPdfCaseRetriableError(cause="extract", details=str(error)) from error

        await self._case_repository.store_pdf_extraction(
            case_id=case_id,
            pdf_mxc_url=pdf_mxc_url,
            extracted_text=extracted_text,
        )

        return extracted_text

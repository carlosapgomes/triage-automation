"""Service layer for process_pdf_case job (download + extract segment)."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from triage_automation.application.ports.audit_repository_port import (
    AuditEventCreateInput,
    AuditRepositoryPort,
)
from triage_automation.application.ports.case_repository_port import CaseRepositoryPort
from triage_automation.application.ports.job_queue_port import JobEnqueueInput, JobQueuePort
from triage_automation.application.services.llm1_service import (
    Llm1RetriableError,
    Llm1Service,
)
from triage_automation.application.services.llm2_service import (
    Llm2RetriableError,
    Llm2Service,
)
from triage_automation.domain.case_status import CaseStatus
from triage_automation.domain.record_number import (
    extract_and_strip_agency_record_number,
)
from triage_automation.infrastructure.matrix.mxc_downloader import (
    MatrixMxcDownloader,
    MxcDownloadError,
)
from triage_automation.infrastructure.pdf.text_extractor import (
    PdfTextExtractionError,
    PdfTextExtractor,
)

logger = logging.getLogger(__name__)


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
        llm1_service: Llm1Service | None = None,
        llm2_service: Llm2Service | None = None,
        audit_repository: AuditRepositoryPort | None = None,
        job_queue: JobQueuePort | None = None,
    ) -> None:
        if llm2_service is not None and job_queue is None:
            raise ValueError("job_queue is required when llm2_service is enabled")

        self._case_repository = case_repository
        self._mxc_downloader = mxc_downloader
        self._text_extractor = text_extractor
        self._llm1_service = llm1_service
        self._llm2_service = llm2_service
        self._audit_repository = audit_repository
        self._job_queue = job_queue

    async def process_case(self, *, case_id: UUID, pdf_mxc_url: str) -> str:
        """Download and extract case PDF content with retriable failure mapping."""

        logger.info("process_pdf_case_started case_id=%s mxc_url=%s", case_id, pdf_mxc_url)
        await self._case_repository.update_status(case_id=case_id, status=CaseStatus.EXTRACTING)

        try:
            pdf_bytes = await self._mxc_downloader.download_pdf(pdf_mxc_url)
        except MxcDownloadError as error:
            logger.warning("process_pdf_case_download_failed case_id=%s error=%s", case_id, error)
            raise ProcessPdfCaseRetriableError(cause="download", details=str(error)) from error
        logger.info("process_pdf_case_download_ok case_id=%s bytes=%s", case_id, len(pdf_bytes))

        try:
            extracted_text = self._text_extractor.extract_text(pdf_bytes)
            if not extracted_text:
                raise PdfTextExtractionError("PDF extraction produced empty text")
        except PdfTextExtractionError as error:
            logger.warning("process_pdf_case_extract_failed case_id=%s error=%s", case_id, error)
            raise ProcessPdfCaseRetriableError(cause="extract", details=str(error)) from error
        logger.info(
            "process_pdf_case_extract_ok case_id=%s text_chars=%s",
            case_id,
            len(extracted_text),
        )
        record_result = extract_and_strip_agency_record_number(extracted_text)
        logger.info(
            "process_pdf_case_record_extract_ok case_id=%s agency_record_number=%s",
            case_id,
            record_result.agency_record_number,
        )
        await self._case_repository.append_case_report_transcript(
            case_id=case_id,
            extracted_text=record_result.cleaned_text,
        )
        logger.info("process_pdf_case_report_transcript_appended case_id=%s", case_id)

        await self._case_repository.store_pdf_extraction(
            case_id=case_id,
            pdf_mxc_url=pdf_mxc_url,
            extracted_text=record_result.cleaned_text,
            agency_record_number=record_result.agency_record_number,
            agency_record_extracted_at=datetime.now(tz=UTC),
        )
        logger.info("process_pdf_case_persist_pdf_ok case_id=%s", case_id)

        if self._llm1_service is not None:
            await self._case_repository.update_status(case_id=case_id, status=CaseStatus.LLM_STRUCT)
            logger.info("process_pdf_case_llm1_started case_id=%s", case_id)
            try:
                llm1_result = await self._llm1_service.run(
                    case_id=case_id,
                    agency_record_number=record_result.agency_record_number,
                    clean_text=record_result.cleaned_text,
                    interaction_repository=self._case_repository,
                )
            except Llm1RetriableError as error:
                if self._audit_repository is not None:
                    await self._audit_repository.append_event(
                        AuditEventCreateInput(
                            case_id=case_id,
                            actor_type="system",
                            event_type="LLM1_FAILED",
                            payload={"error": str(error)},
                        )
                    )
                logger.warning("process_pdf_case_llm1_failed case_id=%s error=%s", case_id, error)
                raise ProcessPdfCaseRetriableError(cause="llm1", details=str(error)) from error

            await self._case_repository.store_llm1_artifacts(
                case_id=case_id,
                structured_data_json=llm1_result.structured_data_json,
                summary_text=llm1_result.summary_text,
            )
            logger.info(
                (
                    "process_pdf_case_llm1_ok case_id=%s "
                    "prompt_system=%s@%s prompt_user=%s@%s"
                ),
                case_id,
                llm1_result.prompt_system_name,
                llm1_result.prompt_system_version,
                llm1_result.prompt_user_name,
                llm1_result.prompt_user_version,
            )
            if self._audit_repository is not None:
                await self._audit_repository.append_event(
                    AuditEventCreateInput(
                        case_id=case_id,
                        actor_type="system",
                        event_type="LLM1_STRUCTURED_SUMMARY_OK",
                        payload=build_llm_prompt_version_audit_payload(
                            system_prompt_name=llm1_result.prompt_system_name,
                            system_prompt_version=llm1_result.prompt_system_version,
                            user_prompt_name=llm1_result.prompt_user_name,
                            user_prompt_version=llm1_result.prompt_user_version,
                        ),
                    )
                )

            if self._llm2_service is not None:
                await self._case_repository.update_status(
                    case_id=case_id,
                    status=CaseStatus.LLM_SUGGEST,
                )
                logger.info("process_pdf_case_llm2_started case_id=%s", case_id)
                try:
                    llm2_result = await self._llm2_service.run(
                        case_id=case_id,
                        agency_record_number=record_result.agency_record_number,
                        llm1_structured_data=llm1_result.structured_data_json,
                        interaction_repository=self._case_repository,
                    )
                except Llm2RetriableError as error:
                    if self._audit_repository is not None:
                        await self._audit_repository.append_event(
                            AuditEventCreateInput(
                                case_id=case_id,
                                actor_type="system",
                                event_type="LLM2_FAILED",
                                payload={"error": str(error)},
                            )
                        )
                    logger.warning(
                        "process_pdf_case_llm2_failed case_id=%s error=%s",
                        case_id,
                        error,
                    )
                    raise ProcessPdfCaseRetriableError(cause="llm2", details=str(error)) from error

                await self._case_repository.store_llm2_artifacts(
                    case_id=case_id,
                    suggested_action_json=llm2_result.suggested_action_json,
                )
                logger.info(
                    (
                        "process_pdf_case_llm2_ok case_id=%s suggestion=%s "
                        "prompt_system=%s@%s prompt_user=%s@%s contradictions=%s"
                    ),
                    case_id,
                    llm2_result.suggested_action_json.get("suggestion"),
                    llm2_result.prompt_system_name,
                    llm2_result.prompt_system_version,
                    llm2_result.prompt_user_name,
                    llm2_result.prompt_user_version,
                    len(llm2_result.contradictions),
                )
                if self._audit_repository is not None:
                    llm2_payload = build_llm_prompt_version_audit_payload(
                        system_prompt_name=llm2_result.prompt_system_name,
                        system_prompt_version=llm2_result.prompt_system_version,
                        user_prompt_name=llm2_result.prompt_user_name,
                        user_prompt_version=llm2_result.prompt_user_version,
                    )
                    llm2_payload["suggestion"] = llm2_result.suggested_action_json.get("suggestion")
                    await self._audit_repository.append_event(
                        AuditEventCreateInput(
                            case_id=case_id,
                            actor_type="system",
                            event_type="LLM2_SUGGESTION_OK",
                            payload=llm2_payload,
                        )
                    )

                if llm2_result.contradictions and self._audit_repository is not None:
                    await self._audit_repository.append_event(
                        AuditEventCreateInput(
                            case_id=case_id,
                            actor_type="system",
                            event_type="LLM_CONTRADICTION_DETECTED",
                            payload={"contradictions": llm2_result.contradictions},
                        )
                    )

                assert self._job_queue is not None  # ensured by __init__
                await self._job_queue.enqueue(
                    JobEnqueueInput(
                        job_type="post_room2_widget",
                        case_id=case_id,
                        payload={},
                    )
                )
                logger.info(
                    "process_pdf_case_enqueued_next_job case_id=%s job_type=post_room2_widget",
                    case_id,
                )

        logger.info("process_pdf_case_completed case_id=%s", case_id)
        return record_result.cleaned_text


def build_llm_prompt_version_audit_payload(
    *,
    system_prompt_name: str,
    system_prompt_version: int,
    user_prompt_name: str,
    user_prompt_version: int,
) -> dict[str, object]:
    """Build deterministic audit payload with prompt template names and versions."""

    return {
        "prompt_system_name": system_prompt_name,
        "prompt_system_version": system_prompt_version,
        "prompt_user_name": user_prompt_name,
        "prompt_user_version": user_prompt_version,
    }

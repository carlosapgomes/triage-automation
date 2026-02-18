"""worker entrypoint."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from triage_automation.application.dto.llm1_models import Llm1Response
from triage_automation.application.dto.llm2_models import Llm2Response
from triage_automation.application.ports.job_queue_port import JobRecord
from triage_automation.application.services.execute_cleanup_service import ExecuteCleanupService
from triage_automation.application.services.job_failure_service import JobFailureService
from triage_automation.application.services.llm1_service import Llm1Service
from triage_automation.application.services.llm2_service import Llm2Service
from triage_automation.application.services.post_room1_final_service import (
    PostRoom1FinalService,
)
from triage_automation.application.services.post_room2_widget_service import (
    PostRoom2WidgetService,
)
from triage_automation.application.services.post_room3_request_service import (
    PostRoom3RequestService,
)
from triage_automation.application.services.process_pdf_case_service import ProcessPdfCaseService
from triage_automation.application.services.prompt_template_service import PromptTemplateService
from triage_automation.application.services.recovery_service import (
    RecoveryResult,
    RecoveryService,
)
from triage_automation.application.services.worker_runtime import JobHandler, WorkerRuntime
from triage_automation.config.settings import Settings, load_settings
from triage_automation.infrastructure.db.audit_repository import SqlAlchemyAuditRepository
from triage_automation.infrastructure.db.case_repository import SqlAlchemyCaseRepository
from triage_automation.infrastructure.db.job_queue_repository import SqlAlchemyJobQueueRepository
from triage_automation.infrastructure.db.message_repository import SqlAlchemyMessageRepository
from triage_automation.infrastructure.db.prior_case_queries import SqlAlchemyPriorCaseQueries
from triage_automation.infrastructure.db.prompt_template_repository import (
    SqlAlchemyPromptTemplateRepository,
)
from triage_automation.infrastructure.db.reaction_checkpoint_repository import (
    SqlAlchemyReactionCheckpointRepository,
)
from triage_automation.infrastructure.db.session import create_session_factory
from triage_automation.infrastructure.db.worker_bootstrap import reconcile_running_jobs
from triage_automation.infrastructure.llm.deterministic_client import DeterministicLlmClient
from triage_automation.infrastructure.llm.llm_client import LlmClientPort
from triage_automation.infrastructure.llm.openai_client import OpenAiChatCompletionsClient
from triage_automation.infrastructure.logging import configure_logging
from triage_automation.infrastructure.matrix.http_client import MatrixHttpClient
from triage_automation.infrastructure.matrix.mxc_downloader import MatrixMxcDownloader
from triage_automation.infrastructure.pdf.text_extractor import PdfTextExtractor

logger = logging.getLogger(__name__)


class MatrixRuntimeClientPort(Protocol):
    """Matrix operations required by worker runtime services."""

    async def send_text(
        self,
        *,
        room_id: str,
        body: str,
        formatted_body: str | None = None,
    ) -> str:
        """Post text body to Matrix and return the created event id."""

    async def send_file_from_mxc(
        self,
        *,
        room_id: str,
        filename: str,
        mxc_url: str,
        mimetype: str,
    ) -> str:
        """Post a file event to Matrix referencing an MXC URI."""

    async def reply_text(
        self,
        *,
        room_id: str,
        event_id: str,
        body: str,
        formatted_body: str | None = None,
    ) -> str:
        """Post reply text to Matrix and return the created event id."""

    async def reply_file_from_mxc(
        self,
        *,
        room_id: str,
        event_id: str,
        filename: str,
        mxc_url: str,
        mimetype: str,
    ) -> str:
        """Post a file reply event to Matrix referencing an MXC URI."""

    async def redact_event(self, *, room_id: str, event_id: str) -> None:
        """Redact a Matrix room event."""

    async def download_mxc(self, mxc_url: str) -> bytes:
        """Download raw bytes for an MXC URI."""


@dataclass(frozen=True)
class WorkerRuntimeServices:
    """Composed runtime services and shared repositories for worker handlers."""

    case_repository: SqlAlchemyCaseRepository
    audit_repository: SqlAlchemyAuditRepository
    queue_repository: SqlAlchemyJobQueueRepository
    process_pdf_case_service: ProcessPdfCaseService
    post_room2_widget_service: PostRoom2WidgetService
    post_room3_request_service: PostRoom3RequestService
    post_room1_final_service: PostRoom1FinalService
    execute_cleanup_service: ExecuteCleanupService


@dataclass(frozen=True)
class WorkerStartupResult:
    """Result summary for worker boot reconciliation and recovery scan."""

    reconciled_jobs: int
    recovery: RecoveryResult


def build_worker_handlers(
    *,
    process_pdf_case_handler: JobHandler,
    post_room2_widget_handler: JobHandler,
    post_room3_request_handler: JobHandler,
    post_room1_final_handler: JobHandler,
    execute_cleanup_handler: JobHandler,
) -> dict[str, JobHandler]:
    """Build explicit runtime handler map for all supported production job types."""

    return {
        "process_pdf_case": process_pdf_case_handler,
        "post_room2_widget": post_room2_widget_handler,
        "post_room3_request": post_room3_request_handler,
        "post_room1_final_denial_triage": post_room1_final_handler,
        "post_room1_final_appt": post_room1_final_handler,
        "post_room1_final_appt_denied": post_room1_final_handler,
        "post_room1_final_failure": post_room1_final_handler,
        "execute_cleanup": execute_cleanup_handler,
    }


def build_runtime_services(
    *,
    settings: Settings,
    session_factory: async_sessionmaker[AsyncSession],
    matrix_client: MatrixRuntimeClientPort,
    llm1_client: LlmClientPort,
    llm2_client: LlmClientPort,
) -> WorkerRuntimeServices:
    """Compose worker runtime services using SQLAlchemy repositories and adapters."""

    case_repository = SqlAlchemyCaseRepository(session_factory)
    audit_repository = SqlAlchemyAuditRepository(session_factory)
    queue_repository = SqlAlchemyJobQueueRepository(session_factory)
    message_repository = SqlAlchemyMessageRepository(session_factory)
    prior_case_queries = SqlAlchemyPriorCaseQueries(session_factory)

    prompt_templates = PromptTemplateService(
        prompt_templates=SqlAlchemyPromptTemplateRepository(session_factory)
    )
    llm1_service = Llm1Service(llm_client=llm1_client, prompt_templates=prompt_templates)
    llm2_service = Llm2Service(llm_client=llm2_client, prompt_templates=prompt_templates)

    process_pdf_case_service = ProcessPdfCaseService(
        case_repository=case_repository,
        mxc_downloader=MatrixMxcDownloader(media_client=matrix_client),
        text_extractor=PdfTextExtractor(),
        llm1_service=llm1_service,
        llm2_service=llm2_service,
        audit_repository=audit_repository,
        job_queue=queue_repository,
    )
    post_room2_widget_service = PostRoom2WidgetService(
        room2_id=settings.room2_id,
        widget_public_base_url=str(settings.widget_public_url),
        case_repository=case_repository,
        audit_repository=audit_repository,
        message_repository=message_repository,
        prior_case_queries=prior_case_queries,
        matrix_poster=matrix_client,
    )
    post_room3_request_service = PostRoom3RequestService(
        room3_id=settings.room3_id,
        case_repository=case_repository,
        audit_repository=audit_repository,
        message_repository=message_repository,
        matrix_poster=matrix_client,
    )
    post_room1_final_service = PostRoom1FinalService(
        case_repository=case_repository,
        audit_repository=audit_repository,
        message_repository=message_repository,
        matrix_poster=matrix_client,
        reaction_checkpoint_repository=SqlAlchemyReactionCheckpointRepository(session_factory),
    )
    execute_cleanup_service = ExecuteCleanupService(
        case_repository=case_repository,
        audit_repository=audit_repository,
        message_repository=message_repository,
        matrix_redactor=matrix_client,
    )

    return WorkerRuntimeServices(
        case_repository=case_repository,
        audit_repository=audit_repository,
        queue_repository=queue_repository,
        process_pdf_case_service=process_pdf_case_service,
        post_room2_widget_service=post_room2_widget_service,
        post_room3_request_service=post_room3_request_service,
        post_room1_final_service=post_room1_final_service,
        execute_cleanup_service=execute_cleanup_service,
    )


def build_runtime_job_handlers(*, services: WorkerRuntimeServices) -> dict[str, JobHandler]:
    """Build runtime job handlers bound to composed production services."""

    async def handle_process_pdf_case(job: JobRecord) -> None:
        case_id = _require_case_id(job)
        pdf_mxc_url = _require_pdf_mxc_url(job)
        await services.process_pdf_case_service.process_case(
            case_id=case_id,
            pdf_mxc_url=pdf_mxc_url,
        )

    async def handle_post_room2_widget(job: JobRecord) -> None:
        case_id = _require_case_id(job)
        await services.post_room2_widget_service.post_widget(case_id=case_id)

    async def handle_post_room3_request(job: JobRecord) -> None:
        case_id = _require_case_id(job)
        await services.post_room3_request_service.post_request(case_id=case_id)

    async def handle_post_room1_final(job: JobRecord) -> None:
        case_id = _require_case_id(job)
        await services.post_room1_final_service.post(
            case_id=case_id,
            job_type=job.job_type,
            payload=job.payload,
        )

    async def handle_execute_cleanup(job: JobRecord) -> None:
        case_id = _require_case_id(job)
        await services.execute_cleanup_service.execute(case_id=case_id)

    return build_worker_handlers(
        process_pdf_case_handler=handle_process_pdf_case,
        post_room2_widget_handler=handle_post_room2_widget,
        post_room3_request_handler=handle_post_room3_request,
        post_room1_final_handler=handle_post_room1_final,
        execute_cleanup_handler=handle_execute_cleanup,
    )


def build_worker_runtime(
    *,
    settings: Settings,
    session_factory: async_sessionmaker[AsyncSession],
    matrix_client: MatrixRuntimeClientPort | None = None,
    llm1_client: LlmClientPort | None = None,
    llm2_client: LlmClientPort | None = None,
) -> WorkerRuntime:
    """Build worker runtime with composed repositories, handlers, and failure hooks."""

    runtime_matrix_client = matrix_client or MatrixHttpClient(
        homeserver_url=str(settings.matrix_homeserver_url),
        access_token=settings.matrix_access_token,
        timeout_seconds=settings.matrix_sync_timeout_ms / 1000,
    )
    runtime_llm1_client, runtime_llm2_client = build_runtime_llm_clients(
        settings=settings,
        llm1_client=llm1_client,
        llm2_client=llm2_client,
    )

    services = build_runtime_services(
        settings=settings,
        session_factory=session_factory,
        matrix_client=runtime_matrix_client,
        llm1_client=runtime_llm1_client,
        llm2_client=runtime_llm2_client,
    )
    handlers = build_runtime_job_handlers(services=services)
    failure_service = JobFailureService(
        case_repository=services.case_repository,
        audit_repository=services.audit_repository,
        job_queue=services.queue_repository,
    )

    return WorkerRuntime(
        queue=services.queue_repository,
        handlers=handlers,
        audit_repository=services.audit_repository,
        job_failure_service=failure_service,
        poll_interval_seconds=settings.worker_poll_interval_seconds,
    )


def build_runtime_llm_clients(
    *,
    settings: Settings,
    llm1_client: LlmClientPort | None = None,
    llm2_client: LlmClientPort | None = None,
) -> tuple[LlmClientPort, LlmClientPort]:
    """Build runtime LLM clients from mode settings while preserving service contracts."""

    runtime_llm1_client = llm1_client
    runtime_llm2_client = llm2_client

    if settings.llm_runtime_mode == "provider":
        api_key = settings.openai_api_key
        if api_key is None or not api_key.strip():
            raise ValueError("OPENAI_API_KEY is required when LLM_RUNTIME_MODE=provider")
        if runtime_llm1_client is None:
            runtime_llm1_client = OpenAiChatCompletionsClient(
                api_key=api_key,
                model=settings.openai_model_llm1,
                temperature=settings.openai_temperature,
                response_schema_name="llm1_response",
                response_schema=Llm1Response.model_json_schema(),
            )
        if runtime_llm2_client is None:
            runtime_llm2_client = OpenAiChatCompletionsClient(
                api_key=api_key,
                model=settings.openai_model_llm2,
                temperature=settings.openai_temperature,
                response_schema_name="llm2_response",
                response_schema=Llm2Response.model_json_schema(),
            )
    else:
        if runtime_llm1_client is None:
            runtime_llm1_client = DeterministicLlmClient(stage="llm1")
        if runtime_llm2_client is None:
            runtime_llm2_client = DeterministicLlmClient(stage="llm2")

    return runtime_llm1_client, runtime_llm2_client


def _require_case_id(job: JobRecord) -> UUID:
    if job.case_id is None:
        raise ValueError(f"Job {job.job_id} requires case_id for job type {job.job_type}")
    return job.case_id


def _require_pdf_mxc_url(job: JobRecord) -> str:
    value = job.payload.get("pdf_mxc_url")
    if isinstance(value, str) and value.strip():
        return value
    raise ValueError("process_pdf_case job missing payload.pdf_mxc_url")


async def run_worker_startup(
    *,
    session_factory: async_sessionmaker[AsyncSession],
) -> WorkerStartupResult:
    """Run startup reconciliation and recovery scan before runtime polling."""

    reconciled_jobs = await reconcile_running_jobs(session_factory)
    queue = SqlAlchemyJobQueueRepository(session_factory)
    recovery = await RecoveryService(
        case_repository=SqlAlchemyCaseRepository(session_factory),
        audit_repository=SqlAlchemyAuditRepository(session_factory),
        job_queue=queue,
    ).recover()
    return WorkerStartupResult(reconciled_jobs=reconciled_jobs, recovery=recovery)


async def _run_worker() -> None:
    settings = load_settings()
    configure_logging(level=settings.log_level)
    logger.info(
        "worker_starting poll_interval_seconds=%s llm_mode=%s",
        settings.worker_poll_interval_seconds,
        settings.llm_runtime_mode,
    )

    session_factory = create_session_factory(settings.database_url)
    startup = await run_worker_startup(session_factory=session_factory)
    logger.info(
        (
            "worker_startup_complete reconciled_jobs=%s "
            "recovery_scanned_cases=%s recovery_enqueued_jobs=%s"
        ),
        startup.reconciled_jobs,
        startup.recovery.scanned_cases,
        startup.recovery.enqueued_jobs,
    )

    runtime = build_worker_runtime(
        settings=settings,
        session_factory=session_factory,
    )
    stop_event = asyncio.Event()

    await runtime.run_until_stopped(stop_event)


def main() -> None:
    """Run worker startup reconciliation and polling runtime."""

    asyncio.run(_run_worker())


if __name__ == "__main__":
    main()

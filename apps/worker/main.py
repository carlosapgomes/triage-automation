"""worker entrypoint."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

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
from triage_automation.infrastructure.db.session import create_session_factory
from triage_automation.infrastructure.db.worker_bootstrap import reconcile_running_jobs
from triage_automation.infrastructure.llm.llm_client import LlmClientPort
from triage_automation.infrastructure.matrix.mxc_downloader import MatrixMxcDownloader
from triage_automation.infrastructure.pdf.text_extractor import PdfTextExtractor


class MatrixRuntimeClientPort(Protocol):
    """Matrix operations required by worker runtime services."""

    async def send_text(self, *, room_id: str, body: str) -> str:
        """Post text body to Matrix and return the created event id."""

    async def reply_text(self, *, room_id: str, event_id: str, body: str) -> str:
        """Post reply text to Matrix and return the created event id."""

    async def redact_event(self, *, room_id: str, event_id: str) -> None:
        """Redact a Matrix room event."""

    async def download_mxc(self, mxc_url: str) -> bytes:
        """Download raw bytes for an MXC URI."""


class _PlaceholderMatrixRuntimeClient:
    """Fallback runtime Matrix client until live adapter wiring is implemented."""

    async def send_text(self, *, room_id: str, body: str) -> str:
        _ = room_id, body
        raise NotImplementedError("runtime Matrix send_text adapter is not configured yet")

    async def reply_text(self, *, room_id: str, event_id: str, body: str) -> str:
        _ = room_id, event_id, body
        raise NotImplementedError("runtime Matrix reply_text adapter is not configured yet")

    async def redact_event(self, *, room_id: str, event_id: str) -> None:
        _ = room_id, event_id
        raise NotImplementedError("runtime Matrix redact_event adapter is not configured yet")

    async def download_mxc(self, mxc_url: str) -> bytes:
        _ = mxc_url
        raise NotImplementedError("runtime Matrix download_mxc adapter is not configured yet")


class _PlaceholderLlmClient:
    """Fallback LLM client until runtime LLM adapter wiring is implemented."""

    def __init__(self, *, stage: str) -> None:
        self._stage = stage

    async def complete(self, *, system_prompt: str, user_prompt: str) -> str:
        _ = system_prompt, user_prompt
        raise NotImplementedError(f"runtime LLM adapter for {self._stage} is not configured yet")


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

    runtime_matrix_client = matrix_client or _PlaceholderMatrixRuntimeClient()
    runtime_llm1_client = llm1_client or _PlaceholderLlmClient(stage="llm1")
    runtime_llm2_client = llm2_client or _PlaceholderLlmClient(stage="llm2")

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

    session_factory = create_session_factory(settings.database_url)
    await run_worker_startup(session_factory=session_factory)

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

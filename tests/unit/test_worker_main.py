from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from apps.worker.main import build_runtime_llm_clients, build_worker_handlers
from triage_automation.application.ports.job_queue_port import JobRecord
from triage_automation.application.services.worker_runtime import WorkerRuntime
from triage_automation.config.settings import Settings
from triage_automation.infrastructure.llm.deterministic_client import (
    DeterministicLlmClient,
)
from triage_automation.infrastructure.llm.openai_client import OpenAiChatCompletionsClient


class _QueueForUnknownType:
    def __init__(self, job: JobRecord) -> None:
        self._job: JobRecord | None = job
        self.schedule_retry_calls: list[tuple[int, str]] = []

    async def claim_due_jobs(self, *, limit: int) -> list[JobRecord]:
        _ = limit
        if self._job is None:
            return []
        job = self._job
        self._job = None
        return [job]

    async def enqueue(self, payload: object) -> JobRecord:  # pragma: no cover - not used here
        _ = payload
        raise NotImplementedError

    async def mark_done(self, *, job_id: int) -> None:  # pragma: no cover - not used here
        _ = job_id
        raise NotImplementedError

    async def mark_failed(
        self,
        *,
        job_id: int,
        last_error: str,
    ) -> None:  # pragma: no cover - not used here
        _ = job_id, last_error
        raise NotImplementedError

    async def schedule_retry(
        self,
        *,
        job_id: int,
        run_after: datetime,
        last_error: str,
    ) -> JobRecord:
        _ = run_after
        self.schedule_retry_calls.append((job_id, last_error))
        return _make_job(job_type="queued-retry", job_id=job_id)

    async def mark_dead(
        self,
        *,
        job_id: int,
        last_error: str,
    ) -> JobRecord:  # pragma: no cover - not used here
        _ = job_id, last_error
        raise NotImplementedError

    async def has_active_job(
        self,
        *,
        case_id: object,
        job_type: str,
    ) -> bool:  # pragma: no cover - not used here
        _ = case_id, job_type
        return False


class _QueueForKnownType:
    def __init__(self, job: JobRecord) -> None:
        self._job: JobRecord | None = job
        self.mark_done_calls: list[int] = []
        self.schedule_retry_calls: list[tuple[int, str]] = []

    async def claim_due_jobs(self, *, limit: int) -> list[JobRecord]:
        _ = limit
        if self._job is None:
            return []
        job = self._job
        self._job = None
        return [job]

    async def enqueue(self, payload: object) -> JobRecord:  # pragma: no cover - not used here
        _ = payload
        raise NotImplementedError

    async def mark_done(self, *, job_id: int) -> None:
        self.mark_done_calls.append(job_id)

    async def mark_failed(
        self,
        *,
        job_id: int,
        last_error: str,
    ) -> None:  # pragma: no cover - not used here
        _ = job_id, last_error
        raise NotImplementedError

    async def schedule_retry(
        self,
        *,
        job_id: int,
        run_after: datetime,
        last_error: str,
    ) -> JobRecord:
        _ = run_after
        self.schedule_retry_calls.append((job_id, last_error))
        return _make_job(job_type="queued-retry", job_id=job_id)

    async def mark_dead(
        self,
        *,
        job_id: int,
        last_error: str,
    ) -> JobRecord:  # pragma: no cover - not used here
        _ = job_id, last_error
        raise NotImplementedError

    async def has_active_job(
        self,
        *,
        case_id: object,
        job_type: str,
    ) -> bool:  # pragma: no cover - not used here
        _ = case_id, job_type
        return False


def _make_job(
    *,
    job_type: str,
    job_id: int = 1,
    case_id: UUID | None = None,
) -> JobRecord:
    now = datetime.now(tz=UTC)
    resolved_case_id = case_id or uuid4()
    return JobRecord(
        job_id=job_id,
        case_id=resolved_case_id,
        job_type=job_type,
        status="running",
        run_after=now,
        attempts=0,
        max_attempts=3,
        last_error=None,
        payload={},
        created_at=now,
        updated_at=now,
    )


async def _noop_handler(job: JobRecord) -> None:
    _ = job


async def _failing_handler(_: JobRecord) -> None:
    raise RuntimeError("summary send failed")


def test_build_worker_handlers_contains_required_runtime_job_types() -> None:
    handlers = build_worker_handlers(
        process_pdf_case_handler=_noop_handler,
        post_room2_widget_handler=_noop_handler,
        post_room3_request_handler=_noop_handler,
        post_room4_summary_handler=_noop_handler,
        post_room1_final_handler=_noop_handler,
        execute_cleanup_handler=_noop_handler,
    )

    assert set(handlers) == {
        "process_pdf_case",
        "post_room2_widget",
        "post_room3_request",
        "post_room4_summary",
        "post_room1_final_denial_triage",
        "post_room1_final_appt",
        "post_room1_final_appt_denied",
        "post_room1_final_failure",
        "execute_cleanup",
    }


@pytest.mark.asyncio
async def test_unknown_job_type_behavior_remains_unchanged() -> None:
    queue = _QueueForUnknownType(_make_job(job_type="unknown-type", job_id=42))
    handlers = build_worker_handlers(
        process_pdf_case_handler=_noop_handler,
        post_room2_widget_handler=_noop_handler,
        post_room3_request_handler=_noop_handler,
        post_room4_summary_handler=_noop_handler,
        post_room1_final_handler=_noop_handler,
        execute_cleanup_handler=_noop_handler,
    )
    runtime = WorkerRuntime(queue=queue, handlers=handlers)

    claimed_count = await runtime.run_once()

    assert claimed_count == 1
    assert queue.schedule_retry_calls == [
        (42, "Unknown job type: unknown-type"),
    ]


@pytest.mark.asyncio
async def test_post_room4_summary_job_type_is_routable() -> None:
    queue = _QueueForKnownType(_make_job(job_type="post_room4_summary", job_id=77))
    handlers = build_worker_handlers(
        process_pdf_case_handler=_noop_handler,
        post_room2_widget_handler=_noop_handler,
        post_room3_request_handler=_noop_handler,
        post_room4_summary_handler=_noop_handler,
        post_room1_final_handler=_noop_handler,
        execute_cleanup_handler=_noop_handler,
    )
    runtime = WorkerRuntime(queue=queue, handlers=handlers)

    claimed_count = await runtime.run_once()

    assert claimed_count == 1
    assert queue.mark_done_calls == [77]
    assert queue.schedule_retry_calls == []


@pytest.mark.asyncio
async def test_post_room4_summary_handler_failure_uses_existing_retry_pipeline() -> None:
    queue = _QueueForKnownType(_make_job(job_type="post_room4_summary", job_id=78))
    handlers = build_worker_handlers(
        process_pdf_case_handler=_noop_handler,
        post_room2_widget_handler=_noop_handler,
        post_room3_request_handler=_noop_handler,
        post_room4_summary_handler=_failing_handler,
        post_room1_final_handler=_noop_handler,
        execute_cleanup_handler=_noop_handler,
    )
    runtime = WorkerRuntime(queue=queue, handlers=handlers)

    claimed_count = await runtime.run_once()

    assert claimed_count == 1
    assert queue.mark_done_calls == []
    assert queue.schedule_retry_calls == [
        (78, "Handler error for post_room4_summary: summary send failed")
    ]


def _runtime_settings(*, mode: str, openai_key: str | None) -> Settings:
    return Settings.model_construct(
        room1_id="!room1:example.org",
        room2_id="!room2:example.org",
        room3_id="!room3:example.org",
        room4_id="!room4:example.org",
        matrix_homeserver_url="https://matrix.example.org",
        matrix_bot_user_id="@bot:example.org",
        matrix_access_token="matrix-token",
        matrix_sync_timeout_ms=30_000,
        matrix_poll_interval_seconds=0.0,
        worker_poll_interval_seconds=0.0,
        supervisor_summary_timezone="America/Bahia",
        supervisor_summary_morning_hour=7,
        supervisor_summary_evening_hour=19,
        webhook_public_url="https://webhook.example.org",
        widget_public_url="https://webhook.example.org",
        database_url="sqlite+aiosqlite:///tmp.db",
        webhook_hmac_secret="secret",
        llm_runtime_mode=mode,
        openai_api_key=openai_key,
        openai_model_llm1="gpt-4o-mini",
        openai_model_llm2="gpt-4o-mini",
        log_level="INFO",
    )


def test_provider_mode_selects_openai_runtime_clients() -> None:
    settings = _runtime_settings(mode="provider", openai_key="sk-test")

    llm1_client, llm2_client = build_runtime_llm_clients(settings=settings)

    assert isinstance(llm1_client, OpenAiChatCompletionsClient)
    assert isinstance(llm2_client, OpenAiChatCompletionsClient)


def test_provider_mode_uses_configured_openai_models() -> None:
    settings = _runtime_settings(mode="provider", openai_key="sk-test").model_copy(
        update={
            "openai_model_llm1": "gpt-4.1-mini",
            "openai_model_llm2": "gpt-4.1",
        }
    )

    llm1_client, llm2_client = build_runtime_llm_clients(settings=settings)

    assert isinstance(llm1_client, OpenAiChatCompletionsClient)
    assert isinstance(llm2_client, OpenAiChatCompletionsClient)
    assert llm1_client.model_name == "gpt-4.1-mini"
    assert llm2_client.model_name == "gpt-4.1"


def test_deterministic_mode_selects_deterministic_runtime_clients() -> None:
    settings = _runtime_settings(mode="deterministic", openai_key=None)

    llm1_client, llm2_client = build_runtime_llm_clients(settings=settings)

    assert isinstance(llm1_client, DeterministicLlmClient)
    assert isinstance(llm2_client, DeterministicLlmClient)

"""bot-matrix entrypoint."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Protocol

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from triage_automation.application.services.room1_intake_service import Room1IntakeService
from triage_automation.config.settings import Settings, load_settings
from triage_automation.infrastructure.db.audit_repository import SqlAlchemyAuditRepository
from triage_automation.infrastructure.db.case_repository import SqlAlchemyCaseRepository
from triage_automation.infrastructure.db.job_queue_repository import SqlAlchemyJobQueueRepository
from triage_automation.infrastructure.db.message_repository import SqlAlchemyMessageRepository
from triage_automation.infrastructure.db.session import create_session_factory
from triage_automation.infrastructure.matrix.event_parser import parse_room1_pdf_intake_event
from triage_automation.infrastructure.matrix.http_client import MatrixHttpClient
from triage_automation.infrastructure.matrix.sync_events import (
    extract_next_batch_token,
    iter_joined_room_timeline_events,
)


class MatrixRoom1ListenerClientPort(Protocol):
    """Matrix operations required for Room-1 listener runtime."""

    async def sync(self, *, since: str | None, timeout_ms: int) -> dict[str, object]:
        """Fetch Matrix sync payload for event routing."""

    async def reply_text(self, *, room_id: str, event_id: str, body: str) -> str:
        """Post reply text to Matrix and return created event id."""


@dataclass(frozen=True)
class BotMatrixRuntime:
    """Composed bot-matrix runtime dependencies."""

    settings: Settings
    matrix_client: MatrixRoom1ListenerClientPort
    room1_intake_service: Room1IntakeService


def build_room1_intake_service(
    *,
    settings: Settings,
    matrix_client: MatrixRoom1ListenerClientPort,
    session_factory: async_sessionmaker[AsyncSession] | None = None,
) -> Room1IntakeService:
    """Build Room-1 intake service dependencies for bot-matrix runtime."""

    runtime_session_factory = session_factory or create_session_factory(settings.database_url)

    return Room1IntakeService(
        case_repository=SqlAlchemyCaseRepository(runtime_session_factory),
        audit_repository=SqlAlchemyAuditRepository(runtime_session_factory),
        message_repository=SqlAlchemyMessageRepository(runtime_session_factory),
        job_queue=SqlAlchemyJobQueueRepository(runtime_session_factory),
        matrix_poster=matrix_client,
    )


def build_bot_matrix_runtime(
    *,
    settings: Settings | None = None,
    matrix_client: MatrixRoom1ListenerClientPort | None = None,
    room1_intake_service: Room1IntakeService | None = None,
) -> BotMatrixRuntime:
    """Build runtime wiring for Room-1 intake listener execution."""

    runtime_settings = settings or load_settings()
    runtime_matrix_client = matrix_client or MatrixHttpClient(
        homeserver_url=str(runtime_settings.matrix_homeserver_url),
        access_token=runtime_settings.matrix_access_token,
        timeout_seconds=runtime_settings.matrix_sync_timeout_ms / 1000,
    )
    runtime_room1_intake_service = room1_intake_service or build_room1_intake_service(
        settings=runtime_settings,
        matrix_client=runtime_matrix_client,
    )

    return BotMatrixRuntime(
        settings=runtime_settings,
        matrix_client=runtime_matrix_client,
        room1_intake_service=runtime_room1_intake_service,
    )


async def poll_room1_intake_once(
    *,
    matrix_client: MatrixRoom1ListenerClientPort,
    intake_service: Room1IntakeService,
    room1_id: str,
    bot_user_id: str,
    since_token: str | None,
    sync_timeout_ms: int,
) -> tuple[str | None, int]:
    """Poll Matrix once and route valid Room-1 PDF events through intake service."""

    sync_payload = await matrix_client.sync(
        since=since_token,
        timeout_ms=sync_timeout_ms,
    )
    next_since = extract_next_batch_token(sync_payload, fallback=since_token)

    routed_count = 0
    for timeline_event in iter_joined_room_timeline_events(sync_payload):
        if timeline_event.room_id != room1_id:
            continue
        parsed = parse_room1_pdf_intake_event(
            room_id=timeline_event.room_id,
            event=timeline_event.event,
            bot_user_id=bot_user_id,
        )
        if parsed is None:
            continue

        await intake_service.ingest_pdf_event(parsed)
        routed_count += 1

    return next_since, routed_count


async def run_room1_intake_listener(
    *,
    matrix_client: MatrixRoom1ListenerClientPort,
    intake_service: Room1IntakeService,
    room1_id: str,
    bot_user_id: str,
    sync_timeout_ms: int,
    poll_interval_seconds: float,
    stop_event: asyncio.Event,
    initial_since_token: str | None = None,
) -> None:
    """Continuously poll Matrix and route Room-1 intake events until stopped."""

    since_token = initial_since_token
    while not stop_event.is_set():
        since_token, _ = await poll_room1_intake_once(
            matrix_client=matrix_client,
            intake_service=intake_service,
            room1_id=room1_id,
            bot_user_id=bot_user_id,
            since_token=since_token,
            sync_timeout_ms=sync_timeout_ms,
        )
        if poll_interval_seconds > 0:
            await asyncio.sleep(poll_interval_seconds)


async def _run_bot_matrix() -> None:
    runtime = build_bot_matrix_runtime()
    stop_event = asyncio.Event()

    await run_room1_intake_listener(
        matrix_client=runtime.matrix_client,
        intake_service=runtime.room1_intake_service,
        room1_id=runtime.settings.room1_id,
        bot_user_id=runtime.settings.matrix_bot_user_id,
        sync_timeout_ms=runtime.settings.matrix_sync_timeout_ms,
        poll_interval_seconds=runtime.settings.matrix_poll_interval_seconds,
        stop_event=stop_event,
    )


def main() -> None:
    """Run bot-matrix Room-1 intake listener runtime."""

    asyncio.run(_run_bot_matrix())


if __name__ == "__main__":
    main()

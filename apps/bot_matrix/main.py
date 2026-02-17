"""bot-matrix entrypoint."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Protocol, cast
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from triage_automation.application.dto.webhook_models import Decision, SupportFlag
from triage_automation.application.ports.message_repository_port import (
    CaseMessageCreateInput,
    DuplicateCaseMessageError,
)
from triage_automation.application.services.handle_doctor_decision_service import (
    HandleDoctorDecisionService,
)
from triage_automation.application.services.reaction_service import ReactionService
from triage_automation.application.services.room1_intake_service import Room1IntakeService
from triage_automation.application.services.room2_reply_service import (
    Room2MembershipAuthorizerPort,
    Room2ReplyEvent,
    Room2ReplyService,
)
from triage_automation.application.services.room3_reply_service import Room3ReplyService
from triage_automation.config.settings import Settings, load_settings
from triage_automation.infrastructure.db.audit_repository import SqlAlchemyAuditRepository
from triage_automation.infrastructure.db.case_repository import SqlAlchemyCaseRepository
from triage_automation.infrastructure.db.job_queue_repository import SqlAlchemyJobQueueRepository
from triage_automation.infrastructure.db.message_repository import SqlAlchemyMessageRepository
from triage_automation.infrastructure.db.session import create_session_factory
from triage_automation.infrastructure.logging import configure_logging
from triage_automation.infrastructure.matrix.event_parser import parse_room1_pdf_intake_event
from triage_automation.infrastructure.matrix.http_client import (
    MatrixHttpClient,
    MatrixTransportError,
)
from triage_automation.infrastructure.matrix.message_templates import (
    build_room2_decision_error_message,
)
from triage_automation.infrastructure.matrix.reaction_parser import parse_matrix_reaction_event
from triage_automation.infrastructure.matrix.room2_reply_parser import (
    parse_room2_decision_reply_event,
)
from triage_automation.infrastructure.matrix.room3_reply_parser import parse_room3_reply_event
from triage_automation.infrastructure.matrix.sync_events import (
    extract_next_batch_token,
    iter_joined_room_timeline_events,
)

_SYNC_HTTP_TIMEOUT_BUFFER_SECONDS = 10.0
_ROOM2_REPLY_ERROR_REASON_TO_CODE: dict[str, str] = {
    "unauthorized_sender": "authorization_failed",
    "authorization_check_failed": "authorization_failed",
    "wrong_state": "state_conflict",
    "duplicate_or_race": "state_conflict",
    "not_found": "state_conflict",
}
_ROOM2_REPLY_TARGET_MESSAGE_KINDS = {
    "room2_case_root",
    "room2_case_instructions",
}
_ROOM2_AUTOMATION_MESSAGE_KINDS = {
    "room2_case_root",
    "room2_case_summary",
    "room2_case_instructions",
    "room2_decision_ack",
}
logger = logging.getLogger(__name__)


class MatrixRoom1ListenerClientPort(Protocol):
    """Matrix operations required for Room-1 listener runtime."""

    async def sync(self, *, since: str | None, timeout_ms: int) -> dict[str, object]:
        """Fetch Matrix sync payload for event routing."""

    async def reply_text(self, *, room_id: str, event_id: str, body: str) -> str:
        """Post reply text to Matrix and return created event id."""

    async def send_text(self, *, room_id: str, body: str) -> str:
        """Post text to Matrix and return created event id."""


@dataclass(frozen=True)
class BotMatrixRuntime:
    """Composed bot-matrix runtime dependencies."""

    settings: Settings
    matrix_client: MatrixRoom1ListenerClientPort
    message_repository: SqlAlchemyMessageRepository
    room1_intake_service: Room1IntakeService
    reaction_service: ReactionService
    room2_reply_service: Room2ReplyService
    room3_reply_service: Room3ReplyService


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
    reaction_service: ReactionService | None = None,
    room2_reply_service: Room2ReplyService | None = None,
    room3_reply_service: Room3ReplyService | None = None,
    session_factory: async_sessionmaker[AsyncSession] | None = None,
) -> BotMatrixRuntime:
    """Build runtime wiring for Room-1 intake listener execution."""

    runtime_settings = settings or load_settings()
    runtime_session_factory = session_factory or create_session_factory(
        runtime_settings.database_url
    )
    runtime_matrix_client = matrix_client or MatrixHttpClient(
        homeserver_url=str(runtime_settings.matrix_homeserver_url),
        access_token=runtime_settings.matrix_access_token,
        timeout_seconds=(
            runtime_settings.matrix_sync_timeout_ms / 1000
            + _SYNC_HTTP_TIMEOUT_BUFFER_SECONDS
        ),
    )
    runtime_room1_intake_service = room1_intake_service or build_room1_intake_service(
        settings=runtime_settings,
        matrix_client=runtime_matrix_client,
        session_factory=runtime_session_factory,
    )
    runtime_message_repository = SqlAlchemyMessageRepository(runtime_session_factory)
    runtime_reaction_service = reaction_service or build_reaction_service(
        settings=runtime_settings,
        session_factory=runtime_session_factory,
    )
    runtime_room2_reply_service = room2_reply_service or build_room2_reply_service(
        settings=runtime_settings,
        matrix_client=runtime_matrix_client,
        session_factory=runtime_session_factory,
    )
    runtime_room3_reply_service = room3_reply_service or build_room3_reply_service(
        settings=runtime_settings,
        matrix_client=runtime_matrix_client,
        session_factory=runtime_session_factory,
    )

    return BotMatrixRuntime(
        settings=runtime_settings,
        matrix_client=runtime_matrix_client,
        message_repository=runtime_message_repository,
        room1_intake_service=runtime_room1_intake_service,
        reaction_service=runtime_reaction_service,
        room2_reply_service=runtime_room2_reply_service,
        room3_reply_service=runtime_room3_reply_service,
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

    routed_count = await _route_room1_intake_from_sync(
        sync_payload=sync_payload,
        intake_service=intake_service,
        room1_id=room1_id,
        bot_user_id=bot_user_id,
    )

    return next_since, routed_count


async def poll_reaction_events_once(
    *,
    matrix_client: MatrixRoom1ListenerClientPort,
    reaction_service: ReactionService,
    room1_id: str,
    room2_id: str,
    room3_id: str,
    bot_user_id: str,
    since_token: str | None,
    sync_timeout_ms: int,
) -> tuple[str | None, int]:
    """Poll Matrix once and route supported reactions through reaction service."""

    sync_payload = await matrix_client.sync(since=since_token, timeout_ms=sync_timeout_ms)
    next_since = extract_next_batch_token(sync_payload, fallback=since_token)
    routed_count = await _route_reactions_from_sync(
        sync_payload=sync_payload,
        reaction_service=reaction_service,
        room1_id=room1_id,
        room2_id=room2_id,
        room3_id=room3_id,
        bot_user_id=bot_user_id,
    )
    return next_since, routed_count


async def poll_room1_and_reactions_once(
    *,
    matrix_client: MatrixRoom1ListenerClientPort,
    intake_service: Room1IntakeService,
    reaction_service: ReactionService,
    room1_id: str,
    room2_id: str,
    room3_id: str,
    bot_user_id: str,
    since_token: str | None,
    sync_timeout_ms: int,
) -> tuple[str | None, int, int]:
    """Poll Matrix once and route both Room-1 intake and reaction events."""

    sync_payload = await matrix_client.sync(since=since_token, timeout_ms=sync_timeout_ms)
    next_since = extract_next_batch_token(sync_payload, fallback=since_token)
    intake_count = await _route_room1_intake_from_sync(
        sync_payload=sync_payload,
        intake_service=intake_service,
        room1_id=room1_id,
        bot_user_id=bot_user_id,
    )
    reaction_count = await _route_reactions_from_sync(
        sync_payload=sync_payload,
        reaction_service=reaction_service,
        room1_id=room1_id,
        room2_id=room2_id,
        room3_id=room3_id,
        bot_user_id=bot_user_id,
    )
    return next_since, intake_count, reaction_count


async def poll_room3_reply_events_once(
    *,
    matrix_client: MatrixRoom1ListenerClientPort,
    room3_reply_service: Room3ReplyService,
    room3_id: str,
    bot_user_id: str,
    since_token: str | None,
    sync_timeout_ms: int,
) -> tuple[str | None, int]:
    """Poll Matrix once and route supported Room-3 reply events."""

    sync_payload = await matrix_client.sync(since=since_token, timeout_ms=sync_timeout_ms)
    next_since = extract_next_batch_token(sync_payload, fallback=since_token)
    routed_count = await _route_room3_replies_from_sync(
        sync_payload=sync_payload,
        room3_reply_service=room3_reply_service,
        room3_id=room3_id,
        bot_user_id=bot_user_id,
    )
    return next_since, routed_count


async def poll_room2_reply_events_once(
    *,
    matrix_client: MatrixRoom1ListenerClientPort,
    room2_reply_service: Room2ReplyService,
    message_repository: SqlAlchemyMessageRepository,
    room2_id: str,
    bot_user_id: str,
    since_token: str | None,
    sync_timeout_ms: int,
) -> tuple[str | None, int]:
    """Poll Matrix once and route supported Room-2 decision reply events."""

    sync_payload = await matrix_client.sync(since=since_token, timeout_ms=sync_timeout_ms)
    next_since = extract_next_batch_token(sync_payload, fallback=since_token)
    routed_count = await _route_room2_replies_from_sync(
        sync_payload=sync_payload,
        matrix_client=matrix_client,
        room2_reply_service=room2_reply_service,
        message_repository=message_repository,
        room2_id=room2_id,
        bot_user_id=bot_user_id,
    )
    return next_since, routed_count


async def poll_room1_reactions_and_room3_once(
    *,
    matrix_client: MatrixRoom1ListenerClientPort,
    intake_service: Room1IntakeService,
    reaction_service: ReactionService,
    room2_reply_service: Room2ReplyService,
    message_repository: SqlAlchemyMessageRepository,
    room3_reply_service: Room3ReplyService,
    room1_id: str,
    room2_id: str,
    room3_id: str,
    bot_user_id: str,
    since_token: str | None,
    sync_timeout_ms: int,
) -> tuple[str | None, int, int, int, int]:
    """Poll Matrix once and route Room-1 intake, reactions, Room-2, and Room-3 replies."""

    sync_payload = await matrix_client.sync(since=since_token, timeout_ms=sync_timeout_ms)
    next_since = extract_next_batch_token(sync_payload, fallback=since_token)
    intake_count = await _route_room1_intake_from_sync(
        sync_payload=sync_payload,
        intake_service=intake_service,
        room1_id=room1_id,
        bot_user_id=bot_user_id,
    )
    reaction_count = await _route_reactions_from_sync(
        sync_payload=sync_payload,
        reaction_service=reaction_service,
        room1_id=room1_id,
        room2_id=room2_id,
        room3_id=room3_id,
        bot_user_id=bot_user_id,
    )
    room2_reply_count = await _route_room2_replies_from_sync(
        sync_payload=sync_payload,
        matrix_client=matrix_client,
        room2_reply_service=room2_reply_service,
        message_repository=message_repository,
        room2_id=room2_id,
        bot_user_id=bot_user_id,
    )
    room3_reply_count = await _route_room3_replies_from_sync(
        sync_payload=sync_payload,
        room3_reply_service=room3_reply_service,
        room3_id=room3_id,
        bot_user_id=bot_user_id,
    )
    return next_since, intake_count, reaction_count, room2_reply_count, room3_reply_count


async def run_room1_intake_listener(
    *,
    matrix_client: MatrixRoom1ListenerClientPort,
    message_repository: SqlAlchemyMessageRepository,
    intake_service: Room1IntakeService,
    reaction_service: ReactionService,
    room2_reply_service: Room2ReplyService,
    room3_reply_service: Room3ReplyService,
    room1_id: str,
    room2_id: str,
    room3_id: str,
    bot_user_id: str,
    sync_timeout_ms: int,
    poll_interval_seconds: float,
    stop_event: asyncio.Event,
    initial_since_token: str | None = None,
) -> None:
    """Continuously poll Matrix and route Room-1 intake events until stopped."""

    logger.info(
        (
            "bot_matrix_listener_started room1_id=%s room2_id=%s room3_id=%s "
            "sync_timeout_ms=%s poll_interval_seconds=%s"
        ),
        room1_id,
        room2_id,
        room3_id,
        sync_timeout_ms,
        poll_interval_seconds,
    )
    since_token = initial_since_token
    while not stop_event.is_set():
        try:
            since_token, intake_count, reaction_count, room2_reply_count, room3_reply_count = (
                await poll_room1_reactions_and_room3_once(
                    matrix_client=matrix_client,
                    intake_service=intake_service,
                    reaction_service=reaction_service,
                    room2_reply_service=room2_reply_service,
                    message_repository=message_repository,
                    room3_reply_service=room3_reply_service,
                    room1_id=room1_id,
                    room2_id=room2_id,
                    room3_id=room3_id,
                    bot_user_id=bot_user_id,
                    since_token=since_token,
                    sync_timeout_ms=sync_timeout_ms,
                )
            )
            if intake_count or reaction_count or room2_reply_count or room3_reply_count:
                logger.info(
                    (
                        "bot_matrix_sync_routed intake=%s reactions=%s "
                        "room2_replies=%s room3_replies=%s"
                    ),
                    intake_count,
                    reaction_count,
                    room2_reply_count,
                    room3_reply_count,
                )
            else:
                logger.debug("bot_matrix_sync_idle")
        except MatrixTransportError:
            logger.warning("Matrix sync transport failure; retrying on next poll cycle.")
        if poll_interval_seconds > 0:
            await asyncio.sleep(poll_interval_seconds)


async def _run_bot_matrix() -> None:
    settings = load_settings()
    configure_logging(level=settings.log_level)
    logger.info(
        "bot_matrix_starting poll_interval_seconds=%s sync_timeout_ms=%s",
        settings.matrix_poll_interval_seconds,
        settings.matrix_sync_timeout_ms,
    )
    runtime = build_bot_matrix_runtime(settings=settings)
    stop_event = asyncio.Event()

    await run_room1_intake_listener(
        matrix_client=runtime.matrix_client,
        message_repository=runtime.message_repository,
        intake_service=runtime.room1_intake_service,
        reaction_service=runtime.reaction_service,
        room2_reply_service=runtime.room2_reply_service,
        room3_reply_service=runtime.room3_reply_service,
        room1_id=runtime.settings.room1_id,
        room2_id=runtime.settings.room2_id,
        room3_id=runtime.settings.room3_id,
        bot_user_id=runtime.settings.matrix_bot_user_id,
        sync_timeout_ms=runtime.settings.matrix_sync_timeout_ms,
        poll_interval_seconds=runtime.settings.matrix_poll_interval_seconds,
        stop_event=stop_event,
    )


def main() -> None:
    """Run bot-matrix Room-1 intake listener runtime."""

    asyncio.run(_run_bot_matrix())


def build_reaction_service(
    *,
    settings: Settings,
    session_factory: async_sessionmaker[AsyncSession],
) -> ReactionService:
    """Build reaction routing service dependencies for runtime listener."""

    return ReactionService(
        room1_id=settings.room1_id,
        room2_id=settings.room2_id,
        room3_id=settings.room3_id,
        case_repository=SqlAlchemyCaseRepository(session_factory),
        audit_repository=SqlAlchemyAuditRepository(session_factory),
        message_repository=SqlAlchemyMessageRepository(session_factory),
        job_queue=SqlAlchemyJobQueueRepository(session_factory),
    )


def build_room2_reply_service(
    *,
    settings: Settings,
    matrix_client: MatrixRoom1ListenerClientPort,
    session_factory: async_sessionmaker[AsyncSession],
) -> Room2ReplyService:
    """Build Room-2 decision reply service for runtime listener routing."""

    decision_service = HandleDoctorDecisionService(
        case_repository=SqlAlchemyCaseRepository(session_factory),
        audit_repository=SqlAlchemyAuditRepository(session_factory),
        job_queue=SqlAlchemyJobQueueRepository(session_factory),
        message_repository=SqlAlchemyMessageRepository(session_factory),
        matrix_poster=matrix_client,
        room2_id=settings.room2_id,
    )
    membership_authorizer: Room2MembershipAuthorizerPort | None = None
    if hasattr(matrix_client, "is_user_joined"):
        membership_authorizer = cast(Room2MembershipAuthorizerPort, matrix_client)

    return Room2ReplyService(
        room2_id=settings.room2_id,
        decision_service=decision_service,
        membership_authorizer=membership_authorizer,
    )


def build_room3_reply_service(
    *,
    settings: Settings,
    matrix_client: MatrixRoom1ListenerClientPort,
    session_factory: async_sessionmaker[AsyncSession],
) -> Room3ReplyService:
    """Build Room-3 scheduler reply service dependencies for runtime listener."""

    return Room3ReplyService(
        room3_id=settings.room3_id,
        case_repository=SqlAlchemyCaseRepository(session_factory),
        audit_repository=SqlAlchemyAuditRepository(session_factory),
        message_repository=SqlAlchemyMessageRepository(session_factory),
        job_queue=SqlAlchemyJobQueueRepository(session_factory),
        matrix_poster=matrix_client,
    )


async def _route_room1_intake_from_sync(
    *,
    sync_payload: dict[str, object],
    intake_service: Room1IntakeService,
    room1_id: str,
    bot_user_id: str,
) -> int:
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

    return routed_count


async def _route_reactions_from_sync(
    *,
    sync_payload: dict[str, object],
    reaction_service: ReactionService,
    room1_id: str,
    room2_id: str,
    room3_id: str,
    bot_user_id: str,
) -> int:
    routed_count = 0
    supported_rooms = {room1_id, room2_id, room3_id}
    for timeline_event in iter_joined_room_timeline_events(sync_payload):
        if timeline_event.room_id not in supported_rooms:
            continue

        parsed = parse_matrix_reaction_event(
            room_id=timeline_event.room_id,
            event=timeline_event.event,
            bot_user_id=bot_user_id,
        )
        if parsed is None:
            continue

        await reaction_service.handle(parsed)
        routed_count += 1

    return routed_count


async def _route_room2_replies_from_sync(
    *,
    sync_payload: dict[str, object],
    matrix_client: MatrixRoom1ListenerClientPort,
    room2_reply_service: Room2ReplyService,
    message_repository: SqlAlchemyMessageRepository,
    room2_id: str,
    bot_user_id: str,
) -> int:
    routed_count = 0
    for timeline_event in iter_joined_room_timeline_events(sync_payload):
        if timeline_event.room_id != room2_id:
            continue

        reply_target_event_id = _extract_reply_target_event_id(timeline_event.event)
        if reply_target_event_id is None:
            continue

        reply_target_mapping = await message_repository.get_case_message_by_room_event(
            room_id=room2_id,
            event_id=reply_target_event_id,
        )
        if reply_target_mapping is None:
            continue
        if reply_target_mapping.kind not in _ROOM2_REPLY_TARGET_MESSAGE_KINDS:
            continue
        mapped_case_id = reply_target_mapping.case_id

        if _extract_sender_user_id(timeline_event.event) == bot_user_id:
            continue

        timeline_event_id = _extract_event_id(timeline_event.event)
        if timeline_event_id is not None:
            existing_mapping = await message_repository.get_case_message_by_room_event(
                room_id=room2_id,
                event_id=timeline_event_id,
            )
            if (
                existing_mapping is not None
                and existing_mapping.kind in _ROOM2_AUTOMATION_MESSAGE_KINDS
            ):
                continue

        parsed = parse_room2_decision_reply_event(
            room_id=timeline_event.room_id,
            event=timeline_event.event,
            bot_user_id=bot_user_id,
            active_root_event_id=reply_target_event_id,
            expected_case_id=mapped_case_id,
        )
        if parsed is None:
            await _send_room2_error_feedback(
                matrix_client=matrix_client,
                room_id=room2_id,
                reply_to_event_id=timeline_event_id,
                case_id=mapped_case_id,
                error_code="invalid_template",
            )
            continue

        result = await room2_reply_service.handle_reply(
            Room2ReplyEvent(
                room_id=parsed.room_id,
                event_id=parsed.event_id,
                sender_user_id=parsed.sender_user_id,
                reply_to_event_id=parsed.reply_to_event_id,
                case_id=parsed.case_id,
                decision=cast(Decision, parsed.decision),
                support_flag=cast(SupportFlag, parsed.support_flag),
                reason=parsed.reason,
            )
        )
        if result.processed:
            try:
                await message_repository.add_message(
                    CaseMessageCreateInput(
                        case_id=parsed.case_id,
                        room_id=room2_id,
                        event_id=parsed.event_id,
                        sender_user_id=parsed.sender_user_id,
                        kind="room2_doctor_reply",
                    )
                )
            except DuplicateCaseMessageError:
                pass
            routed_count += 1
            continue

        error_code = _ROOM2_REPLY_ERROR_REASON_TO_CODE.get(result.reason or "")
        if error_code is None:
            continue
        await _send_room2_error_feedback(
            matrix_client=matrix_client,
            room_id=room2_id,
            reply_to_event_id=parsed.event_id,
            case_id=parsed.case_id,
            error_code=error_code,
        )

    return routed_count


async def _route_room3_replies_from_sync(
    *,
    sync_payload: dict[str, object],
    room3_reply_service: Room3ReplyService,
    room3_id: str,
    bot_user_id: str,
) -> int:
    routed_count = 0
    for timeline_event in iter_joined_room_timeline_events(sync_payload):
        if timeline_event.room_id != room3_id:
            continue

        parsed = parse_room3_reply_event(
            room_id=timeline_event.room_id,
            event=timeline_event.event,
            bot_user_id=bot_user_id,
        )
        if parsed is None:
            continue

        await room3_reply_service.handle_reply(parsed)
        routed_count += 1

    return routed_count


def _extract_reply_target_event_id(event: dict[str, object]) -> str | None:
    """Extract `m.in_reply_to.event_id` from Matrix event payload when present."""

    content = event.get("content")
    if not isinstance(content, dict):
        return None
    relates = content.get("m.relates_to")
    if not isinstance(relates, dict):
        return None
    in_reply_to = relates.get("m.in_reply_to")
    if not isinstance(in_reply_to, dict):
        return None
    reply_event_id = in_reply_to.get("event_id")
    if not isinstance(reply_event_id, str) or not reply_event_id:
        return None
    return reply_event_id


def _extract_event_id(event: dict[str, object]) -> str | None:
    event_id = event.get("event_id")
    if not isinstance(event_id, str) or not event_id:
        return None
    return event_id


def _extract_sender_user_id(event: dict[str, object]) -> str | None:
    sender = event.get("sender")
    if not isinstance(sender, str) or not sender:
        return None
    return sender


async def _send_room2_error_feedback(
    *,
    matrix_client: MatrixRoom1ListenerClientPort,
    room_id: str,
    reply_to_event_id: str | None,
    case_id: UUID,
    error_code: str,
) -> None:
    if reply_to_event_id is None:
        return
    body = build_room2_decision_error_message(
        case_id=case_id,
        error_code=error_code,
    )
    try:
        await matrix_client.reply_text(
            room_id=room_id,
            event_id=reply_to_event_id,
            body=body,
        )
    except Exception as exc:  # pragma: no cover - defensive resilience path
        logger.warning(
            "room2_error_feedback_post_failed room_id=%s reply_to_event_id=%s error=%s",
            room_id,
            reply_to_event_id,
            exc,
        )


if __name__ == "__main__":
    main()

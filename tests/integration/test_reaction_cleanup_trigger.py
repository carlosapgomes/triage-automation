from __future__ import annotations

import asyncio
from pathlib import Path
from uuid import uuid4

import pytest
import sqlalchemy as sa
from alembic.config import Config

from alembic import command
from apps.bot_matrix.main import poll_reaction_events_once
from triage_automation.application.ports.case_repository_port import CaseCreateInput
from triage_automation.application.ports.message_repository_port import CaseMessageCreateInput
from triage_automation.application.services.reaction_service import (
    ReactionEvent,
    ReactionService,
)
from triage_automation.domain.case_status import CaseStatus
from triage_automation.infrastructure.db.audit_repository import SqlAlchemyAuditRepository
from triage_automation.infrastructure.db.case_repository import SqlAlchemyCaseRepository
from triage_automation.infrastructure.db.job_queue_repository import SqlAlchemyJobQueueRepository
from triage_automation.infrastructure.db.message_repository import SqlAlchemyMessageRepository
from triage_automation.infrastructure.db.reaction_checkpoint_repository import (
    SqlAlchemyReactionCheckpointRepository,
)
from triage_automation.infrastructure.db.session import create_session_factory


class _FakeSyncClient:
    def __init__(self, sync_payload: dict[str, object]) -> None:
        self._sync_payload = sync_payload
        self.calls: list[tuple[str | None, int]] = []

    async def sync(self, *, since: str | None, timeout_ms: int) -> dict[str, object]:
        self.calls.append((since, timeout_ms))
        return self._sync_payload


def _upgrade_head(tmp_path: Path, filename: str) -> tuple[str, str]:
    db_path = tmp_path / filename
    sync_url = f"sqlite+pysqlite:///{db_path}"
    async_url = f"sqlite+aiosqlite:///{db_path}"

    alembic_config = Config("alembic.ini")
    alembic_config.set_main_option("sqlalchemy.url", sync_url)
    command.upgrade(alembic_config, "head")

    return sync_url, async_url


def _reaction_event(
    *,
    event_id: str,
    sender: str,
    related_event_id: str,
    key: str = "👍",
) -> dict[str, object]:
    return {
        "type": "m.reaction",
        "event_id": event_id,
        "sender": sender,
        "content": {
            "m.relates_to": {
                "rel_type": "m.annotation",
                "event_id": related_event_id,
                "key": key,
            }
        },
    }


def _sync_payload_with_room_events(
    *,
    next_batch: str,
    by_room: dict[str, list[dict[str, object]]],
) -> dict[str, object]:
    return {
        "next_batch": next_batch,
        "rooms": {
            "join": {
                room_id: {"timeline": {"events": events}}
                for room_id, events in by_room.items()
            }
        },
    }


def _insert_reaction_checkpoint(
    connection: sa.Connection,
    *,
    case_id_hex: str,
    stage: str,
    room_id: str,
    target_event_id: str,
) -> None:
    connection.execute(
        sa.text(
            "INSERT INTO case_reaction_checkpoints ("
            "case_id, stage, room_id, target_event_id"
            ") VALUES ("
            ":case_id, :stage, :room_id, :target_event_id"
            ")"
        ),
        {
            "case_id": case_id_hex,
            "stage": stage,
            "room_id": room_id,
            "target_event_id": target_event_id,
        },
    )


@pytest.mark.asyncio
async def test_concurrent_room1_thumbs_up_triggers_cleanup_once(tmp_path: Path) -> None:
    sync_url, async_url = _upgrade_head(tmp_path, "reaction_room1_race.db")
    session_factory = create_session_factory(async_url)

    case_repo = SqlAlchemyCaseRepository(session_factory)
    audit_repo = SqlAlchemyAuditRepository(session_factory)
    message_repo = SqlAlchemyMessageRepository(session_factory)
    job_repo = SqlAlchemyJobQueueRepository(session_factory)

    case = await case_repo.create_case(
        CaseCreateInput(
            case_id=uuid4(),
            status=CaseStatus.WAIT_R1_CLEANUP_THUMBS,
            room1_origin_room_id="!room1:example.org",
            room1_origin_event_id="$origin-reaction-1",
            room1_sender_user_id="@human:example.org",
        )
    )

    engine = sa.create_engine(sync_url)
    with engine.begin() as connection:
        connection.execute(
            sa.text(
                "UPDATE cases SET room1_final_reply_event_id = :event_id "
                "WHERE case_id = :case_id"
            ),
            {"event_id": "$room1-final-1", "case_id": case.case_id.hex},
        )
        _insert_reaction_checkpoint(
            connection,
            case_id_hex=case.case_id.hex,
            stage="ROOM1_FINAL",
            room_id="!room1:example.org",
            target_event_id="$room1-final-1",
        )

    service = ReactionService(
        room1_id="!room1:example.org",
        room2_id="!room2:example.org",
        room3_id="!room3:example.org",
        case_repository=case_repo,
        audit_repository=audit_repo,
        message_repository=message_repo,
        job_queue=job_repo,
        reaction_checkpoint_repository=SqlAlchemyReactionCheckpointRepository(session_factory),
    )

    event_a = ReactionEvent(
        room_id="!room1:example.org",
        reaction_event_id="$reaction-a",
        reactor_user_id="@nurse1:example.org",
        related_event_id="$room1-final-1",
        reaction_key="👍",
    )
    event_b = ReactionEvent(
        room_id="!room1:example.org",
        reaction_event_id="$reaction-b",
        reactor_user_id="@nurse2:example.org",
        related_event_id="$room1-final-1",
        reaction_key="👍",
    )

    first, second = await asyncio.gather(service.handle(event_a), service.handle(event_b))

    assert {first.reason, second.reason} <= {None, "already_triggered"}
    assert first.processed or second.processed

    with engine.begin() as connection:
        case_row = connection.execute(
            sa.text(
                "SELECT status, cleanup_triggered_at, cleanup_triggered_by_user_id "
                "FROM cases WHERE case_id = :case_id"
            ),
            {"case_id": case.case_id.hex},
        ).mappings().one()
        cleanup_job_count = connection.execute(
            sa.text(
                "SELECT COUNT(*) FROM jobs "
                "WHERE case_id = :case_id AND job_type = 'execute_cleanup'"
            ),
            {"case_id": case.case_id.hex},
        ).scalar_one()
        room1_checkpoint = connection.execute(
            sa.text(
                "SELECT outcome, reactor_user_id FROM case_reaction_checkpoints "
                "WHERE case_id = :case_id AND stage = 'ROOM1_FINAL'"
            ),
            {"case_id": case.case_id.hex},
        ).mappings().one()

    assert case_row["status"] == "CLEANUP_RUNNING"
    assert case_row["cleanup_triggered_at"] is not None
    assert case_row["cleanup_triggered_by_user_id"] in {
        "@nurse1:example.org",
        "@nurse2:example.org",
    }
    assert int(cleanup_job_count) == 1
    assert room1_checkpoint["outcome"] == "POSITIVE_RECEIVED"
    assert room1_checkpoint["reactor_user_id"] in {
        "@nurse1:example.org",
        "@nurse2:example.org",
    }


@pytest.mark.asyncio
async def test_room2_and_room3_ack_thumbs_are_audit_only(tmp_path: Path) -> None:
    sync_url, async_url = _upgrade_head(tmp_path, "reaction_room2_room3_audit.db")
    session_factory = create_session_factory(async_url)

    case_repo = SqlAlchemyCaseRepository(session_factory)
    audit_repo = SqlAlchemyAuditRepository(session_factory)
    message_repo = SqlAlchemyMessageRepository(session_factory)
    job_repo = SqlAlchemyJobQueueRepository(session_factory)

    case = await case_repo.create_case(
        CaseCreateInput(
            case_id=uuid4(),
            status=CaseStatus.WAIT_DOCTOR,
            room1_origin_room_id="!room1:example.org",
            room1_origin_event_id="$origin-reaction-2",
            room1_sender_user_id="@human:example.org",
        )
    )

    await message_repo.add_message(
        CaseMessageCreateInput(
            case_id=case.case_id,
            room_id="!room2:example.org",
            event_id="$room2-ack-1",
            sender_user_id=None,
            kind="room2_decision_ack",
        )
    )
    await message_repo.add_message(
        CaseMessageCreateInput(
            case_id=case.case_id,
            room_id="!room3:example.org",
            event_id="$room3-ack-1",
            sender_user_id=None,
            kind="bot_ack",
        )
    )
    engine = sa.create_engine(sync_url)
    with engine.begin() as connection:
        _insert_reaction_checkpoint(
            connection,
            case_id_hex=case.case_id.hex,
            stage="ROOM2_ACK",
            room_id="!room2:example.org",
            target_event_id="$room2-ack-1",
        )
        _insert_reaction_checkpoint(
            connection,
            case_id_hex=case.case_id.hex,
            stage="ROOM3_ACK",
            room_id="!room3:example.org",
            target_event_id="$room3-ack-1",
        )

    service = ReactionService(
        room1_id="!room1:example.org",
        room2_id="!room2:example.org",
        room3_id="!room3:example.org",
        case_repository=case_repo,
        audit_repository=audit_repo,
        message_repository=message_repo,
        job_queue=job_repo,
        reaction_checkpoint_repository=SqlAlchemyReactionCheckpointRepository(session_factory),
    )

    room2_result = await service.handle(
        ReactionEvent(
            room_id="!room2:example.org",
            reaction_event_id="$reaction-room2",
            reactor_user_id="@doctor:example.org",
            related_event_id="$room2-ack-1",
            reaction_key="👍",
        )
    )
    room3_result = await service.handle(
        ReactionEvent(
            room_id="!room3:example.org",
            reaction_event_id="$reaction-room3",
            reactor_user_id="@scheduler:example.org",
            related_event_id="$room3-ack-1",
            reaction_key="👍",
        )
    )

    assert room2_result.processed is True
    assert room3_result.processed is True

    with engine.begin() as connection:
        cleanup_job_count = connection.execute(
            sa.text(
                "SELECT COUNT(*) FROM jobs WHERE case_id = :case_id "
                "AND job_type = 'execute_cleanup'"
            ),
            {"case_id": case.case_id.hex},
        ).scalar_one()
        room2_audit = connection.execute(
            sa.text(
                "SELECT COUNT(*) FROM case_events WHERE case_id = :case_id "
                "AND event_type = 'ROOM2_ACK_POSITIVE_RECEIVED'"
            ),
            {"case_id": case.case_id.hex},
        ).scalar_one()
        room3_audit = connection.execute(
            sa.text(
                "SELECT COUNT(*) FROM case_events WHERE case_id = :case_id "
                "AND event_type = 'ROOM3_ACK_THUMBS_UP_RECEIVED'"
            ),
            {"case_id": case.case_id.hex},
        ).scalar_one()
        room2_checkpoint = connection.execute(
            sa.text(
                "SELECT outcome, reactor_user_id FROM case_reaction_checkpoints "
                "WHERE case_id = :case_id AND stage = 'ROOM2_ACK'"
            ),
            {"case_id": case.case_id.hex},
        ).mappings().one()
        room3_checkpoint = connection.execute(
            sa.text(
                "SELECT outcome, reactor_user_id FROM case_reaction_checkpoints "
                "WHERE case_id = :case_id AND stage = 'ROOM3_ACK'"
            ),
            {"case_id": case.case_id.hex},
        ).mappings().one()

    assert int(cleanup_job_count) == 0
    assert int(room2_audit) == 1
    assert int(room3_audit) == 1
    assert room2_checkpoint["outcome"] == "POSITIVE_RECEIVED"
    assert room2_checkpoint["reactor_user_id"] == "@doctor:example.org"
    assert room3_checkpoint["outcome"] == "POSITIVE_RECEIVED"
    assert room3_checkpoint["reactor_user_id"] == "@scheduler:example.org"


@pytest.mark.asyncio
async def test_room1_checkmark_with_variation_triggers_cleanup_once(tmp_path: Path) -> None:
    sync_url, async_url = _upgrade_head(tmp_path, "reaction_room1_checkmark.db")
    session_factory = create_session_factory(async_url)

    case_repo = SqlAlchemyCaseRepository(session_factory)
    audit_repo = SqlAlchemyAuditRepository(session_factory)
    message_repo = SqlAlchemyMessageRepository(session_factory)
    job_repo = SqlAlchemyJobQueueRepository(session_factory)

    case = await case_repo.create_case(
        CaseCreateInput(
            case_id=uuid4(),
            status=CaseStatus.WAIT_R1_CLEANUP_THUMBS,
            room1_origin_room_id="!room1:example.org",
            room1_origin_event_id="$origin-reaction-checkmark-1",
            room1_sender_user_id="@human:example.org",
        )
    )

    engine = sa.create_engine(sync_url)
    with engine.begin() as connection:
        connection.execute(
            sa.text(
                "UPDATE cases SET room1_final_reply_event_id = :event_id "
                "WHERE case_id = :case_id"
            ),
            {"event_id": "$room1-final-checkmark-1", "case_id": case.case_id.hex},
        )
        _insert_reaction_checkpoint(
            connection,
            case_id_hex=case.case_id.hex,
            stage="ROOM1_FINAL",
            room_id="!room1:example.org",
            target_event_id="$room1-final-checkmark-1",
        )

    service = ReactionService(
        room1_id="!room1:example.org",
        room2_id="!room2:example.org",
        room3_id="!room3:example.org",
        case_repository=case_repo,
        audit_repository=audit_repo,
        message_repository=message_repo,
        job_queue=job_repo,
        reaction_checkpoint_repository=SqlAlchemyReactionCheckpointRepository(session_factory),
    )

    result = await service.handle(
        ReactionEvent(
            room_id="!room1:example.org",
            reaction_event_id="$reaction-checkmark-1",
            reactor_user_id="@nurse:example.org",
            related_event_id="$room1-final-checkmark-1",
            reaction_key="✅️",
        )
    )

    assert result.processed is True

    with engine.begin() as connection:
        case_row = connection.execute(
            sa.text(
                "SELECT status, cleanup_triggered_at FROM cases WHERE case_id = :case_id"
            ),
            {"case_id": case.case_id.hex},
        ).mappings().one()
        cleanup_job_count = connection.execute(
            sa.text(
                "SELECT COUNT(*) FROM jobs "
                "WHERE case_id = :case_id AND job_type = 'execute_cleanup'"
            ),
            {"case_id": case.case_id.hex},
        ).scalar_one()
        room1_checkpoint = connection.execute(
            sa.text(
                "SELECT outcome, reactor_user_id FROM case_reaction_checkpoints "
                "WHERE case_id = :case_id AND stage = 'ROOM1_FINAL'"
            ),
            {"case_id": case.case_id.hex},
        ).mappings().one()

    assert case_row["status"] == "CLEANUP_RUNNING"
    assert case_row["cleanup_triggered_at"] is not None
    assert int(cleanup_job_count) == 1
    assert room1_checkpoint["outcome"] == "POSITIVE_RECEIVED"
    assert room1_checkpoint["reactor_user_id"] == "@nurse:example.org"


@pytest.mark.asyncio
async def test_room2_room3_ack_accept_checkmark_and_thumbs_variants(tmp_path: Path) -> None:
    sync_url, async_url = _upgrade_head(tmp_path, "reaction_room23_variants.db")
    session_factory = create_session_factory(async_url)

    case_repo = SqlAlchemyCaseRepository(session_factory)
    audit_repo = SqlAlchemyAuditRepository(session_factory)
    message_repo = SqlAlchemyMessageRepository(session_factory)
    job_repo = SqlAlchemyJobQueueRepository(session_factory)

    case = await case_repo.create_case(
        CaseCreateInput(
            case_id=uuid4(),
            status=CaseStatus.WAIT_DOCTOR,
            room1_origin_room_id="!room1:example.org",
            room1_origin_event_id="$origin-reaction-variants-23",
            room1_sender_user_id="@human:example.org",
        )
    )

    await message_repo.add_message(
        CaseMessageCreateInput(
            case_id=case.case_id,
            room_id="!room2:example.org",
            event_id="$room2-ack-variant-1",
            sender_user_id=None,
            kind="room2_decision_ack",
        )
    )
    await message_repo.add_message(
        CaseMessageCreateInput(
            case_id=case.case_id,
            room_id="!room3:example.org",
            event_id="$room3-ack-variant-1",
            sender_user_id=None,
            kind="bot_ack",
        )
    )

    service = ReactionService(
        room1_id="!room1:example.org",
        room2_id="!room2:example.org",
        room3_id="!room3:example.org",
        case_repository=case_repo,
        audit_repository=audit_repo,
        message_repository=message_repo,
        job_queue=job_repo,
        reaction_checkpoint_repository=SqlAlchemyReactionCheckpointRepository(session_factory),
    )

    room2_result = await service.handle(
        ReactionEvent(
            room_id="!room2:example.org",
            reaction_event_id="$reaction-room2-checkmark-variant",
            reactor_user_id="@doctor:example.org",
            related_event_id="$room2-ack-variant-1",
            reaction_key="✅️",
        )
    )
    room3_result = await service.handle(
        ReactionEvent(
            room_id="!room3:example.org",
            reaction_event_id="$reaction-room3-thumbs-variant",
            reactor_user_id="@scheduler:example.org",
            related_event_id="$room3-ack-variant-1",
            reaction_key="👍️",
        )
    )

    assert room2_result.processed is True
    assert room3_result.processed is True

    engine = sa.create_engine(sync_url)
    with engine.begin() as connection:
        cleanup_job_count = connection.execute(
            sa.text(
                "SELECT COUNT(*) FROM jobs WHERE case_id = :case_id "
                "AND job_type = 'execute_cleanup'"
            ),
            {"case_id": case.case_id.hex},
        ).scalar_one()
        room2_audit = connection.execute(
            sa.text(
                "SELECT COUNT(*) FROM case_events WHERE case_id = :case_id "
                "AND event_type = 'ROOM2_ACK_POSITIVE_RECEIVED'"
            ),
            {"case_id": case.case_id.hex},
        ).scalar_one()
        room3_audit = connection.execute(
            sa.text(
                "SELECT COUNT(*) FROM case_events WHERE case_id = :case_id "
                "AND event_type = 'ROOM3_ACK_THUMBS_UP_RECEIVED'"
            ),
            {"case_id": case.case_id.hex},
        ).scalar_one()

    assert int(cleanup_job_count) == 0
    assert int(room2_audit) == 1
    assert int(room3_audit) == 1


@pytest.mark.asyncio
async def test_runtime_listener_routes_room1_thumbs_to_cleanup_trigger_path(tmp_path: Path) -> None:
    sync_url, async_url = _upgrade_head(tmp_path, "reaction_listener_room1.db")
    session_factory = create_session_factory(async_url)

    case_repo = SqlAlchemyCaseRepository(session_factory)
    audit_repo = SqlAlchemyAuditRepository(session_factory)
    message_repo = SqlAlchemyMessageRepository(session_factory)
    job_repo = SqlAlchemyJobQueueRepository(session_factory)

    case = await case_repo.create_case(
        CaseCreateInput(
            case_id=uuid4(),
            status=CaseStatus.WAIT_R1_CLEANUP_THUMBS,
            room1_origin_room_id="!room1:example.org",
            room1_origin_event_id="$origin-reaction-runtime-room1",
            room1_sender_user_id="@human:example.org",
        )
    )

    engine = sa.create_engine(sync_url)
    with engine.begin() as connection:
        connection.execute(
            sa.text(
                "UPDATE cases SET room1_final_reply_event_id = :event_id "
                "WHERE case_id = :case_id"
            ),
            {"event_id": "$room1-final-runtime-1", "case_id": case.case_id.hex},
        )

    service = ReactionService(
        room1_id="!room1:example.org",
        room2_id="!room2:example.org",
        room3_id="!room3:example.org",
        case_repository=case_repo,
        audit_repository=audit_repo,
        message_repository=message_repo,
        job_queue=job_repo,
        reaction_checkpoint_repository=SqlAlchemyReactionCheckpointRepository(session_factory),
    )
    sync_client = _FakeSyncClient(
        _sync_payload_with_room_events(
            next_batch="s-room1",
            by_room={
                "!room1:example.org": [
                    _reaction_event(
                        event_id="$reaction-runtime-room1",
                        sender="@nurse:example.org",
                        related_event_id="$room1-final-runtime-1",
                    )
                ]
            },
        )
    )

    next_since, routed_count = await poll_reaction_events_once(
        matrix_client=sync_client,
        reaction_service=service,
        room1_id="!room1:example.org",
        room2_id="!room2:example.org",
        room3_id="!room3:example.org",
        bot_user_id="@bot:example.org",
        since_token=None,
        sync_timeout_ms=5_000,
    )

    assert next_since == "s-room1"
    assert routed_count == 1

    with engine.begin() as connection:
        case_row = connection.execute(
            sa.text(
                "SELECT status, cleanup_triggered_at FROM cases WHERE case_id = :case_id"
            ),
            {"case_id": case.case_id.hex},
        ).mappings().one()
        cleanup_jobs = connection.execute(
            sa.text(
                "SELECT COUNT(*) FROM jobs WHERE case_id = :case_id "
                "AND job_type = 'execute_cleanup'"
            ),
            {"case_id": case.case_id.hex},
        ).scalar_one()

    assert case_row["status"] == "CLEANUP_RUNNING"
    assert case_row["cleanup_triggered_at"] is not None
    assert int(cleanup_jobs) == 1


@pytest.mark.asyncio
async def test_runtime_listener_routes_room2_room3_thumbs_as_audit_only(tmp_path: Path) -> None:
    sync_url, async_url = _upgrade_head(tmp_path, "reaction_listener_room2_room3.db")
    session_factory = create_session_factory(async_url)

    case_repo = SqlAlchemyCaseRepository(session_factory)
    audit_repo = SqlAlchemyAuditRepository(session_factory)
    message_repo = SqlAlchemyMessageRepository(session_factory)
    job_repo = SqlAlchemyJobQueueRepository(session_factory)

    case = await case_repo.create_case(
        CaseCreateInput(
            case_id=uuid4(),
            status=CaseStatus.WAIT_DOCTOR,
            room1_origin_room_id="!room1:example.org",
            room1_origin_event_id="$origin-reaction-runtime-room23",
            room1_sender_user_id="@human:example.org",
        )
    )

    await message_repo.add_message(
        CaseMessageCreateInput(
            case_id=case.case_id,
            room_id="!room2:example.org",
            event_id="$room2-ack-runtime",
            sender_user_id=None,
            kind="room2_decision_ack",
        )
    )
    await message_repo.add_message(
        CaseMessageCreateInput(
            case_id=case.case_id,
            room_id="!room3:example.org",
            event_id="$room3-ack-runtime",
            sender_user_id=None,
            kind="bot_ack",
        )
    )

    service = ReactionService(
        room1_id="!room1:example.org",
        room2_id="!room2:example.org",
        room3_id="!room3:example.org",
        case_repository=case_repo,
        audit_repository=audit_repo,
        message_repository=message_repo,
        job_queue=job_repo,
        reaction_checkpoint_repository=SqlAlchemyReactionCheckpointRepository(session_factory),
    )
    sync_client = _FakeSyncClient(
        _sync_payload_with_room_events(
            next_batch="s-room23",
            by_room={
                "!room2:example.org": [
                    _reaction_event(
                        event_id="$reaction-runtime-room2",
                        sender="@doctor:example.org",
                        related_event_id="$room2-ack-runtime",
                    )
                ],
                "!room3:example.org": [
                    _reaction_event(
                        event_id="$reaction-runtime-room3",
                        sender="@scheduler:example.org",
                        related_event_id="$room3-ack-runtime",
                    )
                ],
            },
        )
    )

    next_since, routed_count = await poll_reaction_events_once(
        matrix_client=sync_client,
        reaction_service=service,
        room1_id="!room1:example.org",
        room2_id="!room2:example.org",
        room3_id="!room3:example.org",
        bot_user_id="@bot:example.org",
        since_token="s-prev",
        sync_timeout_ms=5_000,
    )

    assert next_since == "s-room23"
    assert routed_count == 2

    engine = sa.create_engine(sync_url)
    with engine.begin() as connection:
        cleanup_jobs = connection.execute(
            sa.text(
                "SELECT COUNT(*) FROM jobs WHERE case_id = :case_id "
                "AND job_type = 'execute_cleanup'"
            ),
            {"case_id": case.case_id.hex},
        ).scalar_one()
        room2_audit = connection.execute(
            sa.text(
                "SELECT COUNT(*) FROM case_events WHERE case_id = :case_id "
                "AND event_type = 'ROOM2_ACK_POSITIVE_RECEIVED'"
            ),
            {"case_id": case.case_id.hex},
        ).scalar_one()
        room3_audit = connection.execute(
            sa.text(
                "SELECT COUNT(*) FROM case_events WHERE case_id = :case_id "
                "AND event_type = 'ROOM3_ACK_THUMBS_UP_RECEIVED'"
            ),
            {"case_id": case.case_id.hex},
        ).scalar_one()

    assert int(cleanup_jobs) == 0
    assert int(room2_audit) == 1
    assert int(room3_audit) == 1


@pytest.mark.asyncio
async def test_room2_non_positive_reaction_is_ignored(tmp_path: Path) -> None:
    sync_url, async_url = _upgrade_head(tmp_path, "reaction_room2_non_positive.db")
    session_factory = create_session_factory(async_url)

    case_repo = SqlAlchemyCaseRepository(session_factory)
    audit_repo = SqlAlchemyAuditRepository(session_factory)
    message_repo = SqlAlchemyMessageRepository(session_factory)
    job_repo = SqlAlchemyJobQueueRepository(session_factory)

    case = await case_repo.create_case(
        CaseCreateInput(
            case_id=uuid4(),
            status=CaseStatus.WAIT_DOCTOR,
            room1_origin_room_id="!room1:example.org",
            room1_origin_event_id="$origin-reaction-room2-neg",
            room1_sender_user_id="@human:example.org",
        )
    )

    await message_repo.add_message(
        CaseMessageCreateInput(
            case_id=case.case_id,
            room_id="!room2:example.org",
            event_id="$room2-ack-neg-1",
            sender_user_id=None,
            kind="room2_decision_ack",
        )
    )
    engine = sa.create_engine(sync_url)
    with engine.begin() as connection:
        _insert_reaction_checkpoint(
            connection,
            case_id_hex=case.case_id.hex,
            stage="ROOM2_ACK",
            room_id="!room2:example.org",
            target_event_id="$room2-ack-neg-1",
        )

    service = ReactionService(
        room1_id="!room1:example.org",
        room2_id="!room2:example.org",
        room3_id="!room3:example.org",
        case_repository=case_repo,
        audit_repository=audit_repo,
        message_repository=message_repo,
        job_queue=job_repo,
        reaction_checkpoint_repository=SqlAlchemyReactionCheckpointRepository(session_factory),
    )

    result = await service.handle(
        ReactionEvent(
            room_id="!room2:example.org",
            reaction_event_id="$reaction-room2-neg",
            reactor_user_id="@doctor:example.org",
            related_event_id="$room2-ack-neg-1",
            reaction_key="👎",
        )
    )
    assert result.processed is False
    assert result.reason == "not_thumbs_up"

    with engine.begin() as connection:
        room2_audit = connection.execute(
            sa.text(
                "SELECT COUNT(*) FROM case_events WHERE case_id = :case_id "
                "AND event_type = 'ROOM2_ACK_POSITIVE_RECEIVED'"
            ),
            {"case_id": case.case_id.hex},
        ).scalar_one()
        room2_checkpoint = connection.execute(
            sa.text(
                "SELECT outcome, reactor_user_id FROM case_reaction_checkpoints "
                "WHERE case_id = :case_id AND stage = 'ROOM2_ACK'"
            ),
            {"case_id": case.case_id.hex},
        ).mappings().one()

    assert int(room2_audit) == 0
    assert room2_checkpoint["outcome"] == "PENDING"
    assert room2_checkpoint["reactor_user_id"] is None

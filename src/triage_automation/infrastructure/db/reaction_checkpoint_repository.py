"""SQLAlchemy adapter for reaction checkpoint persistence."""

from __future__ import annotations

import logging
from typing import Any, cast

import sqlalchemy as sa
from sqlalchemy.engine import CursorResult
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from triage_automation.application.ports.reaction_checkpoint_repository_port import (
    ReactionCheckpointCreateInput,
    ReactionCheckpointPositiveInput,
    ReactionCheckpointRepositoryPort,
)
from triage_automation.infrastructure.db.metadata import case_reaction_checkpoints

logger = logging.getLogger(__name__)


def _is_duplicate_checkpoint_target_error(error: IntegrityError) -> bool:
    message = str(error.orig).lower()
    return (
        "case_reaction_checkpoints.room_id, case_reaction_checkpoints.target_event_id" in message
        or "uq_case_reaction_checkpoints_room_target_event" in message
    )


class SqlAlchemyReactionCheckpointRepository(ReactionCheckpointRepositoryPort):
    """Reaction checkpoint repository backed by SQLAlchemy async sessions."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def ensure_expected_checkpoint(self, payload: ReactionCheckpointCreateInput) -> None:
        """Insert one expected reaction checkpoint and ignore duplicate room/event targets."""

        statement = sa.insert(case_reaction_checkpoints).values(
            case_id=payload.case_id,
            stage=payload.stage,
            room_id=payload.room_id,
            target_event_id=payload.target_event_id,
        )
        async with self._session_factory() as session:
            try:
                await session.execute(statement)
                await session.commit()
            except IntegrityError as error:
                await session.rollback()
                if _is_duplicate_checkpoint_target_error(error):
                    logger.info(
                        (
                            "reaction_checkpoint_expected_duplicate_ignored "
                            "case_id=%s stage=%s room_id=%s target_event_id=%s"
                        ),
                        payload.case_id,
                        payload.stage,
                        payload.room_id,
                        payload.target_event_id,
                    )
                    return
                raise

        logger.info(
            (
                "reaction_checkpoint_expected_registered "
                "case_id=%s stage=%s room_id=%s target_event_id=%s"
            ),
            payload.case_id,
            payload.stage,
            payload.room_id,
            payload.target_event_id,
        )

    async def mark_positive_reaction(self, payload: ReactionCheckpointPositiveInput) -> bool:
        """Transition one checkpoint to POSITIVE_RECEIVED by room/event target."""

        statement = (
            sa.update(case_reaction_checkpoints)
            .where(
                case_reaction_checkpoints.c.stage == payload.stage,
                case_reaction_checkpoints.c.room_id == payload.room_id,
                case_reaction_checkpoints.c.target_event_id == payload.target_event_id,
                case_reaction_checkpoints.c.outcome == "PENDING",
            )
            .values(
                outcome="POSITIVE_RECEIVED",
                reaction_event_id=payload.reaction_event_id,
                reactor_user_id=payload.reactor_user_id,
                reaction_key=payload.reaction_key,
                reacted_at=sa.func.current_timestamp(),
            )
        )

        async with self._session_factory() as session:
            result = cast(CursorResult[Any], await session.execute(statement))
            await session.commit()

        changed = int(result.rowcount or 0) == 1
        logger.info(
            (
                "reaction_checkpoint_positive_marked=%s stage=%s room_id=%s "
                "target_event_id=%s reaction_event_id=%s reactor_user_id=%s"
            ),
            changed,
            payload.stage,
            payload.room_id,
            payload.target_event_id,
            payload.reaction_event_id,
            payload.reactor_user_id,
        )
        return changed

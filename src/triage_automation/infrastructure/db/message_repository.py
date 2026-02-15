"""SQLAlchemy adapter for case message mapping persistence."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from triage_automation.application.ports.message_repository_port import (
    CaseMessageCreateInput,
    DuplicateCaseMessageError,
    MessageRepositoryPort,
)
from triage_automation.infrastructure.db.metadata import case_messages


def _is_duplicate_room_event_error(error: IntegrityError) -> bool:
    message = str(error.orig).lower()
    return "case_messages.room_id, case_messages.event_id" in message


class SqlAlchemyMessageRepository(MessageRepositoryPort):
    """Message repository backed by SQLAlchemy async sessions."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def add_message(self, payload: CaseMessageCreateInput) -> int:
        statement = sa.insert(case_messages).values(
            case_id=payload.case_id,
            room_id=payload.room_id,
            event_id=payload.event_id,
            sender_user_id=payload.sender_user_id,
            kind=payload.kind,
        ).returning(case_messages.c.id)

        async with self._session_factory() as session:
            try:
                result = await session.execute(statement)
                await session.commit()
            except IntegrityError as error:
                await session.rollback()
                if _is_duplicate_room_event_error(error):
                    raise DuplicateCaseMessageError("Duplicate case message room/event") from error
                raise

        inserted_id = result.scalar_one()
        return int(inserted_id)

"""SQLAlchemy adapter for case message mapping persistence."""

from __future__ import annotations

from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from triage_automation.application.ports.message_repository_port import (
    CaseMessageCreateInput,
    CaseMessageLookup,
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

    async def has_message_kind(self, *, case_id: UUID, room_id: str, kind: str) -> bool:
        statement = sa.select(sa.literal(True)).where(
            case_messages.c.case_id == case_id,
            case_messages.c.room_id == room_id,
            case_messages.c.kind == kind,
        ).limit(1)

        async with self._session_factory() as session:
            result = await session.execute(statement)

        return result.scalar_one_or_none() is True

    async def find_case_id_by_room_event_kind(
        self,
        *,
        room_id: str,
        event_id: str,
        kind: str,
    ) -> UUID | None:
        statement = sa.select(case_messages.c.case_id).where(
            case_messages.c.room_id == room_id,
            case_messages.c.event_id == event_id,
            case_messages.c.kind == kind,
        ).limit(1)

        async with self._session_factory() as session:
            result = await session.execute(statement)

        case_id = result.scalar_one_or_none()
        if case_id is None:
            return None
        if isinstance(case_id, UUID):
            return case_id
        return UUID(str(case_id))

    async def get_case_message_by_room_event(
        self,
        *,
        room_id: str,
        event_id: str,
    ) -> CaseMessageLookup | None:
        statement = sa.select(
            case_messages.c.case_id,
            case_messages.c.kind,
        ).where(
            case_messages.c.room_id == room_id,
            case_messages.c.event_id == event_id,
        ).limit(1)

        async with self._session_factory() as session:
            result = await session.execute(statement)

        row = result.mappings().first()
        if row is None:
            return None

        raw_case_id = row["case_id"]
        case_id = raw_case_id if isinstance(raw_case_id, UUID) else UUID(str(raw_case_id))
        return CaseMessageLookup(
            case_id=case_id,
            kind=str(row["kind"]),
        )

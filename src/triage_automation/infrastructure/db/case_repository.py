"""SQLAlchemy adapter for case repository operations."""

from __future__ import annotations

from typing import Any, cast

import sqlalchemy as sa
from sqlalchemy.engine import RowMapping
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from triage_automation.application.ports.case_repository_port import (
    CaseCreateInput,
    CaseRecord,
    CaseRepositoryPort,
    DuplicateCaseOriginEventError,
)
from triage_automation.domain.case_status import CaseStatus
from triage_automation.infrastructure.db.metadata import cases


def _is_duplicate_origin_error(error: IntegrityError) -> bool:
    message = str(error.orig).lower()
    return "room1_origin_event_id" in message


def _to_case_record(row: RowMapping) -> CaseRecord:
    return CaseRecord(
        case_id=cast("Any", row["case_id"]),
        status=CaseStatus(cast(str, row["status"])),
        room1_origin_room_id=cast(str, row["room1_origin_room_id"]),
        room1_origin_event_id=cast(str, row["room1_origin_event_id"]),
        room1_sender_user_id=cast(str, row["room1_sender_user_id"]),
        created_at=cast("Any", row["created_at"]),
        updated_at=cast("Any", row["updated_at"]),
    )


class SqlAlchemyCaseRepository(CaseRepositoryPort):
    """Case repository backed by SQLAlchemy async sessions."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def create_case(self, payload: CaseCreateInput) -> CaseRecord:
        statement = (
            sa.insert(cases)
            .values(
                case_id=payload.case_id,
                status=payload.status.value,
                room1_origin_room_id=payload.room1_origin_room_id,
                room1_origin_event_id=payload.room1_origin_event_id,
                room1_sender_user_id=payload.room1_sender_user_id,
            )
            .returning(
                cases.c.case_id,
                cases.c.status,
                cases.c.room1_origin_room_id,
                cases.c.room1_origin_event_id,
                cases.c.room1_sender_user_id,
                cases.c.created_at,
                cases.c.updated_at,
            )
        )

        async with self._session_factory() as session:
            try:
                result = await session.execute(statement)
                await session.commit()
            except IntegrityError as error:
                await session.rollback()
                if _is_duplicate_origin_error(error):
                    raise DuplicateCaseOriginEventError(
                        "Duplicate room1_origin_event_id"
                    ) from error
                raise

        row = result.mappings().one()
        return _to_case_record(row)

    async def get_case_by_origin_event_id(self, origin_event_id: str) -> CaseRecord | None:
        statement = sa.select(
            cases.c.case_id,
            cases.c.status,
            cases.c.room1_origin_room_id,
            cases.c.room1_origin_event_id,
            cases.c.room1_sender_user_id,
            cases.c.created_at,
            cases.c.updated_at,
        ).where(cases.c.room1_origin_event_id == origin_event_id)

        async with self._session_factory() as session:
            result = await session.execute(statement)

        row = result.mappings().first()
        if row is None:
            return None
        return _to_case_record(row)

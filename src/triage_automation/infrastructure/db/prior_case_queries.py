"""Prior-case lookup helpers used by Room-2 widget enrichment."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import cast
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from triage_automation.application.ports.prior_case_query_port import (
    PriorCaseContext,
    PriorCaseDecision,
    PriorCaseQueryPort,
    PriorCaseSummary,
)
from triage_automation.infrastructure.db.metadata import cases


@dataclass(frozen=True)
class PriorCaseCandidate:
    """Case row subset used to compute prior decision context."""

    case_id: UUID
    created_at: datetime
    status: str
    doctor_decision: str | None
    doctor_decided_at: datetime | None
    doctor_reason: str | None
    appointment_status: str | None
    appointment_decided_at: datetime | None
    appointment_reason: str | None


class SqlAlchemyPriorCaseQueries(PriorCaseQueryPort):
    """DB query adapter for prior case lookup by agency record number."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def lookup_recent_context(
        self,
        *,
        case_id: UUID,
        agency_record_number: str,
        now: datetime | None = None,
    ) -> PriorCaseContext:
        """Return seven-day prior-case context for Room-2 widget enrichment."""

        reference_now = now or datetime.now(tz=UTC)
        window_start = reference_now - timedelta(days=7)

        statement = sa.select(
            cases.c.case_id,
            cases.c.created_at,
            cases.c.status,
            cases.c.doctor_decision,
            cases.c.doctor_decided_at,
            cases.c.doctor_reason,
            cases.c.appointment_status,
            cases.c.appointment_decided_at,
            cases.c.appointment_reason,
        ).where(
            cases.c.agency_record_number == agency_record_number,
            cases.c.created_at >= window_start,
            cases.c.created_at <= reference_now,
            cases.c.case_id != case_id,
        )

        async with self._session_factory() as session:
            result = await session.execute(statement)

        candidates: list[PriorCaseCandidate] = []
        for row in result.mappings().all():
            candidates.append(
                PriorCaseCandidate(
                    case_id=cast(UUID, row["case_id"]),
                    created_at=_ensure_utc(cast(datetime, row["created_at"])),
                    status=cast(str, row["status"]),
                    doctor_decision=cast(str | None, row["doctor_decision"]),
                    doctor_decided_at=_ensure_utc_or_none(
                        cast(datetime | None, row["doctor_decided_at"])
                    ),
                    doctor_reason=cast(str | None, row["doctor_reason"]),
                    appointment_status=cast(str | None, row["appointment_status"]),
                    appointment_decided_at=_ensure_utc_or_none(
                        cast(datetime | None, row["appointment_decided_at"])
                    ),
                    appointment_reason=cast(str | None, row["appointment_reason"]),
                )
            )

        return build_prior_case_context(
            candidates=candidates,
            current_case_id=case_id,
            now=reference_now,
        )


def build_prior_case_context(
    *,
    candidates: list[PriorCaseCandidate],
    current_case_id: UUID,
    now: datetime,
) -> PriorCaseContext:
    """Compute most-recent prior case and denial count within 7 days."""

    window_start = now - timedelta(days=7)

    scoped = [
        candidate
        for candidate in candidates
        if candidate.case_id != current_case_id and candidate.created_at >= window_start
    ]
    if not scoped:
        return PriorCaseContext(prior_case=None, prior_denial_count_7d=None)

    scoped.sort(key=lambda item: item.created_at, reverse=True)
    denial_count = sum(1 for item in scoped if _is_denial(item))

    top = scoped[0]
    return PriorCaseContext(
        prior_case=PriorCaseSummary(
            prior_case_id=top.case_id,
            decided_at=_select_decided_at(top),
            decision=_map_decision(top),
            reason=_select_reason(top),
        ),
        prior_denial_count_7d=denial_count,
    )


def _is_denial(candidate: PriorCaseCandidate) -> bool:
    return candidate.doctor_decision == "deny" or candidate.appointment_status == "denied"


def _map_decision(candidate: PriorCaseCandidate) -> PriorCaseDecision:
    if candidate.doctor_decision == "deny":
        return "deny_triage"
    if candidate.appointment_status == "denied":
        return "deny_appointment"
    if candidate.status == "FAILED":
        return "failed"
    return "accepted"


def _select_decided_at(candidate: PriorCaseCandidate) -> datetime:
    if candidate.doctor_decided_at is not None:
        return candidate.doctor_decided_at
    if candidate.appointment_decided_at is not None:
        return candidate.appointment_decided_at
    return candidate.created_at


def _select_reason(candidate: PriorCaseCandidate) -> str | None:
    if candidate.doctor_reason:
        return candidate.doctor_reason
    if candidate.appointment_reason:
        return candidate.appointment_reason
    return None


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


def _ensure_utc_or_none(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return _ensure_utc(value)

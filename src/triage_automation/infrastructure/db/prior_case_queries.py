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

        denial_window_filter = sa.or_(
            sa.and_(
                cases.c.doctor_decision == "deny",
                cases.c.doctor_decided_at.is_not(None),
                cases.c.doctor_decided_at >= window_start,
                cases.c.doctor_decided_at <= reference_now,
            ),
            sa.and_(
                cases.c.appointment_status == "denied",
                cases.c.appointment_decided_at.is_not(None),
                cases.c.appointment_decided_at >= window_start,
                cases.c.appointment_decided_at <= reference_now,
            ),
        )

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
            cases.c.case_id != case_id,
            denial_window_filter,
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
    """Compute most-recent prior denial and denial count within the 7-day window."""

    window_start = now - timedelta(days=7)

    denial_events_in_window: list[tuple[UUID, datetime, PriorCaseDecision, str | None]] = []
    for candidate in candidates:
        if candidate.case_id == current_case_id:
            continue

        for decided_at, decision, reason in _collect_denial_events(candidate):
            if decided_at < window_start or decided_at > now:
                continue
            denial_events_in_window.append((candidate.case_id, decided_at, decision, reason))

    if not denial_events_in_window:
        return PriorCaseContext(prior_case=None, prior_denial_count_7d=None)

    denial_events_in_window.sort(key=lambda item: item[1], reverse=True)
    top_case_id, top_decided_at, top_decision, top_reason = denial_events_in_window[0]

    return PriorCaseContext(
        prior_case=PriorCaseSummary(
            prior_case_id=top_case_id,
            decided_at=top_decided_at,
            decision=top_decision,
            reason=_normalize_denial_reason(top_reason),
        ),
        prior_denial_count_7d=len(denial_events_in_window),
    )


def _collect_denial_events(
    candidate: PriorCaseCandidate,
) -> list[tuple[datetime, PriorCaseDecision, str | None]]:
    """Return all denial events available in a candidate case row."""

    denial_events: list[tuple[datetime, PriorCaseDecision, str | None]] = []

    if candidate.doctor_decision == "deny" and candidate.doctor_decided_at is not None:
        denial_events.append(
            (candidate.doctor_decided_at, "deny_triage", candidate.doctor_reason)
        )

    if candidate.appointment_status == "denied" and candidate.appointment_decided_at is not None:
        denial_events.append(
            (
                candidate.appointment_decided_at,
                "deny_appointment",
                candidate.appointment_reason,
            )
        )

    return denial_events


def _normalize_denial_reason(reason: str | None) -> str:
    """Return deterministic reason text for selected recent denial context."""

    if reason is None:
        return "não informado"

    normalized = reason.strip()
    if not normalized:
        return "não informado"
    return normalized


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


def _ensure_utc_or_none(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return _ensure_utc(value)

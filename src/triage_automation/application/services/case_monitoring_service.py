"""Application service for monitoring dashboard case-list queries."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

from triage_automation.application.ports.case_repository_port import (
    CaseMonitoringListFilter,
    CaseMonitoringListPage,
    CaseRepositoryPort,
)
from triage_automation.domain.case_status import CaseStatus


class InvalidMonitoringPeriodError(ValueError):
    """Raised when monitoring period filters are semantically invalid."""


@dataclass(frozen=True)
class CaseMonitoringListQuery:
    """Query object for paginated monitoring list retrieval."""

    page: int
    page_size: int
    status: CaseStatus | None = None
    from_date: date | None = None
    to_date: date | None = None


class CaseMonitoringService:
    """List cases for operational monitoring with period/status filters."""

    def __init__(self, *, case_repository: CaseRepositoryPort) -> None:
        self._case_repository = case_repository

    async def list_cases(self, query: CaseMonitoringListQuery) -> CaseMonitoringListPage:
        """Return paginated cases ordered by latest activity timestamp."""

        if query.from_date and query.to_date and query.to_date < query.from_date:
            raise InvalidMonitoringPeriodError("to_date must be greater than or equal to from_date")

        activity_from = _day_start(query.from_date) if query.from_date is not None else None
        activity_to = _next_day_start(query.to_date) if query.to_date is not None else None
        return await self._case_repository.list_cases_for_monitoring(
            filters=CaseMonitoringListFilter(
                status=query.status,
                activity_from=activity_from,
                activity_to=activity_to,
                page=query.page,
                page_size=query.page_size,
            )
        )


def _day_start(value: date) -> datetime:
    """Return UTC start-of-day datetime for the provided date."""

    return datetime(value.year, value.month, value.day, tzinfo=UTC)


def _next_day_start(value: date) -> datetime:
    """Return UTC start-of-next-day datetime for inclusive date-end filtering."""

    return _day_start(value) + timedelta(days=1)

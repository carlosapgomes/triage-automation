"""Query port for Room-4 supervisor summary aggregate metrics."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True)
class SupervisorSummaryMetrics:
    """Aggregate counters rendered in one Room-4 supervisor summary message."""

    patients_received: int
    reports_processed: int
    cases_evaluated: int
    accepted: int
    refused: int


class SupervisorSummaryMetricsQueryPort(Protocol):
    """Async contract for aggregate metrics over a reporting window."""

    async def aggregate_metrics(
        self,
        *,
        window_start: datetime,
        window_end: datetime,
    ) -> SupervisorSummaryMetrics:
        """Return aggregate summary metrics in `[window_start, window_end)` window."""

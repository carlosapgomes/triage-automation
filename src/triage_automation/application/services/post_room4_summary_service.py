"""Application service for posting supervisor summary messages to Room-4."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from zoneinfo import ZoneInfo

from triage_automation.application.ports.supervisor_summary_metrics_query_port import (
    SupervisorSummaryMetrics,
    SupervisorSummaryMetricsQueryPort,
)


class Room4SummaryMatrixPosterPort(Protocol):
    """Matrix posting operations required by Room-4 summary service."""

    async def send_text(
        self,
        *,
        room_id: str,
        body: str,
        formatted_body: str | None = None,
    ) -> str:
        """Post text body to Matrix and return the created event id."""


@dataclass(frozen=True)
class SupervisorSummaryRendered:
    """Rendered Room-4 summary content and source aggregate metrics."""

    body: str
    metrics: SupervisorSummaryMetrics


class PostRoom4SummaryService:
    """Compute and post one Room-4 supervisor summary message."""

    def __init__(
        self,
        *,
        room4_id: str,
        timezone_name: str,
        metrics_queries: SupervisorSummaryMetricsQueryPort,
        matrix_poster: Room4SummaryMatrixPosterPort,
    ) -> None:
        self._room4_id = room4_id
        self._timezone_name = timezone_name
        self._metrics_queries = metrics_queries
        self._matrix_poster = matrix_poster

    async def post_summary(
        self,
        *,
        window_start: datetime,
        window_end: datetime,
        room_id: str | None = None,
        timezone_name: str | None = None,
    ) -> str:
        """Aggregate and publish one Room-4 summary for the requested window."""

        metrics = await self._metrics_queries.aggregate_metrics(
            window_start=window_start,
            window_end=window_end,
        )
        rendered = render_room4_summary_message(
            window_start=window_start,
            window_end=window_end,
            timezone_name=timezone_name or self._timezone_name,
            metrics=metrics,
        )
        target_room_id = room_id or self._room4_id
        return await self._matrix_poster.send_text(
            room_id=target_room_id,
            body=rendered.body,
        )


def render_room4_summary_message(
    *,
    window_start: datetime,
    window_end: datetime,
    timezone_name: str,
    metrics: SupervisorSummaryMetrics,
) -> SupervisorSummaryRendered:
    """Render deterministic Portuguese summary message for Room-4 supervisors."""

    timezone = ZoneInfo(timezone_name)
    start_local = window_start.astimezone(timezone)
    end_local = window_end.astimezone(timezone)
    body = "\n".join(
        [
            "📊 Resumo de Supervisão",
            f"Janela ({timezone_name}): {start_local:%d/%m/%Y %H:%M} → {end_local:%d/%m/%Y %H:%M}",
            "",
            f"- Pacientes recebidos: {metrics.patients_received}",
            f"- Relatórios processados: {metrics.reports_processed}",
            f"- Casos avaliados: {metrics.cases_evaluated}",
            f"- Aceitos: {metrics.accepted}",
            f"- Recusados: {metrics.refused}",
        ]
    )
    return SupervisorSummaryRendered(body=body, metrics=metrics)

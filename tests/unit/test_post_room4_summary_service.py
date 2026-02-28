from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

import pytest

from triage_automation.application.ports.supervisor_summary_metrics_query_port import (
    SupervisorSummaryMetrics,
)
from triage_automation.application.services.post_room4_summary_service import (
    PostRoom4SummaryService,
)


@dataclass
class _MetricsSpy:
    metrics: SupervisorSummaryMetrics

    async def aggregate_metrics(
        self,
        *,
        window_start: datetime,
        window_end: datetime,
    ) -> SupervisorSummaryMetrics:
        _ = window_start, window_end
        return self.metrics


class _MatrixSpy:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    async def send_text(
        self,
        *,
        room_id: str,
        body: str,
        formatted_body: str | None = None,
    ) -> str:
        _ = formatted_body
        self.calls.append((room_id, body))
        return "$room4-summary"


@pytest.mark.asyncio
async def test_post_room4_summary_service_renders_metrics_and_posts_to_room4() -> None:
    matrix = _MatrixSpy()
    service = PostRoom4SummaryService(
        room4_id="!room4:example.org",
        timezone_name="America/Bahia",
        metrics_queries=_MetricsSpy(
            metrics=SupervisorSummaryMetrics(
                patients_received=12,
                reports_processed=10,
                cases_evaluated=9,
                accepted=6,
                refused=3,
            )
        ),
        matrix_poster=matrix,
    )

    event_id = await service.post_summary(
        window_start=datetime(2026, 2, 16, 10, 0, tzinfo=UTC),
        window_end=datetime(2026, 2, 16, 22, 0, tzinfo=UTC),
    )

    assert event_id == "$room4-summary"
    assert matrix.calls[0][0] == "!room4:example.org"
    body = matrix.calls[0][1]
    assert "Resumo de Supervisão" in body
    assert "Pacientes recebidos: 12" in body
    assert "Relatórios processados: 10" in body
    assert "Casos avaliados: 9" in body
    assert "Aceitos: 6" in body
    assert "Recusados: 3" in body

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

import pytest

from triage_automation.application.ports.supervisor_summary_dispatch_repository_port import (
    SupervisorSummaryDispatchRecord,
    SupervisorSummaryDispatchSentInput,
    SupervisorSummaryWindowKey,
)
from triage_automation.application.ports.supervisor_summary_metrics_query_port import (
    SupervisorSummaryMetrics,
)
from triage_automation.application.services.post_room4_summary_service import (
    PostRoom4SummaryService,
)


@dataclass
class _MetricsSpy:
    metrics: SupervisorSummaryMetrics

    def __post_init__(self) -> None:
        self.calls: list[tuple[datetime, datetime]] = []

    async def aggregate_metrics(
        self,
        *,
        window_start: datetime,
        window_end: datetime,
    ) -> SupervisorSummaryMetrics:
        self.calls.append((window_start, window_end))
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


class _DispatchSpy:
    def __init__(
        self,
        *,
        existing: SupervisorSummaryDispatchRecord | None,
        claim_result: bool = True,
        mark_sent_result: bool,
    ) -> None:
        self._existing = existing
        self._claim_result = claim_result
        self._mark_sent_result = mark_sent_result
        self.claim_calls: list[tuple[str, datetime, datetime]] = []
        self.mark_sent_calls: list[tuple[str, datetime, datetime, str]] = []

    async def claim_window(self, payload: SupervisorSummaryWindowKey) -> bool:
        self.claim_calls.append((payload.room_id, payload.window_start, payload.window_end))
        return self._claim_result

    async def mark_sent(self, payload: SupervisorSummaryDispatchSentInput) -> bool:
        self.mark_sent_calls.append(
            (
                payload.room_id,
                payload.window_start,
                payload.window_end,
                payload.matrix_event_id,
            )
        )
        return self._mark_sent_result

    async def get_by_window(
        self,
        *,
        room_id: str,
        window_start: datetime,
        window_end: datetime,
    ) -> SupervisorSummaryDispatchRecord | None:
        _ = room_id, window_start, window_end
        return self._existing


@pytest.mark.asyncio
async def test_post_room4_summary_service_renders_metrics_and_posts_to_room4() -> None:
    matrix = _MatrixSpy()
    dispatch = _DispatchSpy(existing=None, mark_sent_result=True)
    metrics = _MetricsSpy(
        metrics=SupervisorSummaryMetrics(
            patients_received=12,
            reports_processed=10,
            cases_evaluated=9,
            accepted=6,
            refused=3,
        )
    )
    service = PostRoom4SummaryService(
        room4_id="!room4:example.org",
        timezone_name="America/Bahia",
        metrics_queries=metrics,
        dispatch_repository=dispatch,
        matrix_poster=matrix,
    )

    window_start = datetime(2026, 2, 16, 10, 0, tzinfo=UTC)
    window_end = datetime(2026, 2, 16, 22, 0, tzinfo=UTC)
    event_id = await service.post_summary(
        window_start=window_start,
        window_end=window_end,
    )

    assert event_id == "$room4-summary"
    assert metrics.calls == [(window_start, window_end)]
    assert matrix.calls[0][0] == "!room4:example.org"
    body = matrix.calls[0][1]
    assert "Resumo de Supervisão" in body
    assert "Pacientes recebidos: 12" in body
    assert "Relatórios processados: 10" in body
    assert "Casos avaliados: 9" in body
    assert "Aceitos: 6" in body
    assert "Recusados: 3" in body


@pytest.mark.asyncio
async def test_post_room4_summary_service_skips_publish_when_window_already_sent() -> None:
    matrix = _MatrixSpy()
    dispatch = _DispatchSpy(
        existing=SupervisorSummaryDispatchRecord(
            dispatch_id=11,
            room_id="!room4:example.org",
            window_start=datetime(2026, 2, 16, 10, 0, tzinfo=UTC),
            window_end=datetime(2026, 2, 16, 22, 0, tzinfo=UTC),
            status="sent",
            sent_at=datetime(2026, 2, 16, 22, 5, tzinfo=UTC),
            matrix_event_id="$summary-old",
            last_error=None,
            created_at=datetime(2026, 2, 16, 22, 1, tzinfo=UTC),
            updated_at=datetime(2026, 2, 16, 22, 5, tzinfo=UTC),
        ),
        mark_sent_result=False,
    )
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
        dispatch_repository=dispatch,
        matrix_poster=matrix,
    )

    event_id = await service.post_summary_if_not_sent(
        window_start=datetime(2026, 2, 16, 10, 0, tzinfo=UTC),
        window_end=datetime(2026, 2, 16, 22, 0, tzinfo=UTC),
    )

    assert event_id is None
    assert matrix.calls == []
    assert dispatch.mark_sent_calls == []

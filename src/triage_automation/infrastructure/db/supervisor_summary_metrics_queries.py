"""SQLAlchemy query adapter for Room-4 supervisor summary aggregate metrics."""

from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from triage_automation.application.ports.supervisor_summary_metrics_query_port import (
    SupervisorSummaryMetrics,
    SupervisorSummaryMetricsQueryPort,
)
from triage_automation.infrastructure.db.metadata import cases

case_report_transcripts = sa.table(
    "case_report_transcripts",
    sa.column("id", sa.Integer()),
    sa.column("captured_at", sa.DateTime(timezone=True)),
)


class SqlAlchemySupervisorSummaryMetricsQueries(SupervisorSummaryMetricsQueryPort):
    """Aggregate Room-4 summary counters from persisted case/report timestamps."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def aggregate_metrics(
        self,
        *,
        window_start: datetime,
        window_end: datetime,
    ) -> SupervisorSummaryMetrics:
        """Return aggregate counts in `[window_start, window_end)` using case/report fields."""

        patients_statement = sa.select(sa.func.count()).select_from(cases).where(
            cases.c.created_at >= window_start,
            cases.c.created_at < window_end,
        )
        reports_statement = sa.select(sa.func.count()).select_from(case_report_transcripts).where(
            case_report_transcripts.c.captured_at >= window_start,
            case_report_transcripts.c.captured_at < window_end,
        )
        evaluated_statement = sa.select(sa.func.count()).select_from(cases).where(
            cases.c.doctor_decided_at.is_not(None),
            cases.c.doctor_decided_at >= window_start,
            cases.c.doctor_decided_at < window_end,
        )
        accepted_statement = sa.select(sa.func.count()).select_from(cases).where(
            cases.c.appointment_status == "confirmed",
            cases.c.appointment_decided_at.is_not(None),
            cases.c.appointment_decided_at >= window_start,
            cases.c.appointment_decided_at < window_end,
        )

        doctor_denied_statement = sa.select(sa.func.count()).select_from(cases).where(
            cases.c.doctor_decision == "deny",
            cases.c.doctor_decided_at.is_not(None),
            cases.c.doctor_decided_at >= window_start,
            cases.c.doctor_decided_at < window_end,
        )
        scheduler_denied_statement = sa.select(sa.func.count()).select_from(cases).where(
            cases.c.appointment_status == "denied",
            cases.c.appointment_decided_at.is_not(None),
            cases.c.appointment_decided_at >= window_start,
            cases.c.appointment_decided_at < window_end,
        )

        async with self._session_factory() as session:
            patients_received = int((await session.execute(patients_statement)).scalar_one())
            reports_processed = int((await session.execute(reports_statement)).scalar_one())
            cases_evaluated = int((await session.execute(evaluated_statement)).scalar_one())
            accepted = int((await session.execute(accepted_statement)).scalar_one())
            doctor_denied = int((await session.execute(doctor_denied_statement)).scalar_one())
            scheduler_denied = int(
                (await session.execute(scheduler_denied_statement)).scalar_one()
            )

        return SupervisorSummaryMetrics(
            patients_received=patients_received,
            reports_processed=reports_processed,
            cases_evaluated=cases_evaluated,
            accepted=accepted,
            refused=doctor_denied + scheduler_denied,
        )

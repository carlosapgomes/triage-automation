from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from triage_automation.infrastructure.db.prior_case_queries import (
    PriorCaseCandidate,
    build_prior_case_context,
)


def test_lookup_excludes_current_case_and_uses_7_day_window() -> None:
    now = datetime(2026, 2, 15, 12, 0, tzinfo=UTC)
    current_case_id = uuid4()
    recent_denied_case_id = uuid4()

    candidates = [
        PriorCaseCandidate(
            case_id=current_case_id,
            created_at=now - timedelta(days=1),
            status="LLM_SUGGEST",
            doctor_decision=None,
            doctor_decided_at=None,
            doctor_reason=None,
            appointment_status=None,
            appointment_decided_at=None,
            appointment_reason=None,
        ),
        PriorCaseCandidate(
            case_id=recent_denied_case_id,
            created_at=now - timedelta(days=2),
            status="DOCTOR_DENIED",
            doctor_decision="deny",
            doctor_decided_at=now - timedelta(days=2, hours=1),
            doctor_reason="criterio clinico",
            appointment_status=None,
            appointment_decided_at=None,
            appointment_reason=None,
        ),
        PriorCaseCandidate(
            case_id=uuid4(),
            created_at=now - timedelta(days=8),
            status="DOCTOR_DENIED",
            doctor_decision="deny",
            doctor_decided_at=now - timedelta(days=8),
            doctor_reason="fora da janela",
            appointment_status=None,
            appointment_decided_at=None,
            appointment_reason=None,
        ),
    ]

    context = build_prior_case_context(
        candidates=candidates,
        current_case_id=current_case_id,
        now=now,
    )

    assert context.prior_case is not None
    assert context.prior_case.prior_case_id == recent_denied_case_id
    assert context.prior_case.decision == "deny_triage"
    assert context.prior_denial_count_7d == 1


def test_lookup_window_uses_doctor_decided_at_not_created_at() -> None:
    now = datetime(2026, 2, 15, 12, 0, tzinfo=UTC)
    current_case_id = uuid4()
    recent_denial_old_created_case_id = uuid4()

    candidates = [
        PriorCaseCandidate(
            case_id=recent_denial_old_created_case_id,
            created_at=now - timedelta(days=30),
            status="DOCTOR_DENIED",
            doctor_decision="deny",
            doctor_decided_at=now - timedelta(days=1),
            doctor_reason="negativa recente com caso antigo",
            appointment_status=None,
            appointment_decided_at=None,
            appointment_reason=None,
        ),
        PriorCaseCandidate(
            case_id=uuid4(),
            created_at=now - timedelta(days=1),
            status="DOCTOR_DENIED",
            doctor_decision="deny",
            doctor_decided_at=now - timedelta(days=10),
            doctor_reason="negativa antiga com caso recente",
            appointment_status=None,
            appointment_decided_at=None,
            appointment_reason=None,
        ),
    ]

    context = build_prior_case_context(
        candidates=candidates,
        current_case_id=current_case_id,
        now=now,
    )

    assert context.prior_case is not None
    assert context.prior_case.prior_case_id == recent_denial_old_created_case_id
    assert context.prior_case.decision == "deny_triage"
    assert context.prior_denial_count_7d == 1


def test_lookup_window_uses_appointment_decided_at_not_created_at() -> None:
    now = datetime(2026, 2, 15, 12, 0, tzinfo=UTC)
    current_case_id = uuid4()
    recent_appointment_denial_old_created_case_id = uuid4()

    candidates = [
        PriorCaseCandidate(
            case_id=recent_appointment_denial_old_created_case_id,
            created_at=now - timedelta(days=20),
            status="R3_DENIED",
            doctor_decision=None,
            doctor_decided_at=None,
            doctor_reason=None,
            appointment_status="denied",
            appointment_decided_at=now - timedelta(days=2),
            appointment_reason="agenda indisponivel",
        ),
        PriorCaseCandidate(
            case_id=uuid4(),
            created_at=now - timedelta(days=1),
            status="R3_DENIED",
            doctor_decision=None,
            doctor_decided_at=None,
            doctor_reason=None,
            appointment_status="denied",
            appointment_decided_at=now - timedelta(days=9),
            appointment_reason="fora da janela",
        ),
    ]

    context = build_prior_case_context(
        candidates=candidates,
        current_case_id=current_case_id,
        now=now,
    )

    assert context.prior_case is not None
    assert context.prior_case.prior_case_id == recent_appointment_denial_old_created_case_id
    assert context.prior_case.decision == "deny_appointment"
    assert context.prior_denial_count_7d == 1


def test_lookup_selects_latest_denial_event_by_denial_timestamp() -> None:
    now = datetime(2026, 2, 15, 12, 0, tzinfo=UTC)
    current_case_id = uuid4()
    latest_denial_case_id = uuid4()

    candidates = [
        PriorCaseCandidate(
            case_id=uuid4(),
            created_at=now - timedelta(days=1),
            status="DOCTOR_DENIED",
            doctor_decision="deny",
            doctor_decided_at=now - timedelta(hours=6),
            doctor_reason="negativa mais antiga",
            appointment_status=None,
            appointment_decided_at=None,
            appointment_reason=None,
        ),
        PriorCaseCandidate(
            case_id=latest_denial_case_id,
            created_at=now - timedelta(days=10),
            status="R3_DENIED",
            doctor_decision=None,
            doctor_decided_at=None,
            doctor_reason=None,
            appointment_status="denied",
            appointment_decided_at=now - timedelta(hours=2),
            appointment_reason="negativa mais recente",
        ),
    ]

    context = build_prior_case_context(
        candidates=candidates,
        current_case_id=current_case_id,
        now=now,
    )

    assert context.prior_case is not None
    assert context.prior_case.prior_case_id == latest_denial_case_id
    assert context.prior_case.decision == "deny_appointment"
    assert context.prior_case.decided_at == now - timedelta(hours=2)


def test_lookup_uses_nao_informado_fallback_for_missing_denial_reason() -> None:
    now = datetime(2026, 2, 15, 12, 0, tzinfo=UTC)
    current_case_id = uuid4()

    candidates = [
        PriorCaseCandidate(
            case_id=uuid4(),
            created_at=now - timedelta(days=1),
            status="DOCTOR_DENIED",
            doctor_decision="deny",
            doctor_decided_at=now - timedelta(hours=3),
            doctor_reason="   ",
            appointment_status=None,
            appointment_decided_at=None,
            appointment_reason=None,
        )
    ]

    context = build_prior_case_context(
        candidates=candidates,
        current_case_id=current_case_id,
        now=now,
    )

    assert context.prior_case is not None
    assert context.prior_case.reason == "não informado"

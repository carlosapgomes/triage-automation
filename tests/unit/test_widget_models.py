from __future__ import annotations

from uuid import uuid4

import pytest
from pydantic import ValidationError

from triage_automation.application.dto.webhook_models import TriageDecisionWebhookPayload
from triage_automation.application.dto.widget_models import (
    WidgetDecisionBootstrapRequest,
    WidgetDecisionBootstrapResponse,
    WidgetDecisionSubmitRequest,
    WidgetDecisionSubmitResponse,
)


def _submit_payload(*, decision: str, support_flag: str) -> dict[str, str]:
    return {
        "case_id": str(uuid4()),
        "doctor_user_id": "@doctor:example.org",
        "decision": decision,
        "support_flag": support_flag,
    }


def _is_valid_widget_submit(payload: dict[str, str]) -> bool:
    try:
        WidgetDecisionSubmitRequest.model_validate(payload)
    except ValidationError:
        return False
    return True


def _is_valid_webhook_submit(payload: dict[str, str]) -> bool:
    try:
        TriageDecisionWebhookPayload.model_validate(payload)
    except ValidationError:
        return False
    return True


@pytest.mark.parametrize(
    ("decision", "support_flag"),
    [
        ("accept", "none"),
        ("accept", "anesthesist"),
        ("accept", "anesthesist_icu"),
        ("deny", "none"),
        ("deny", "anesthesist"),
        ("accept", "invalid"),
    ],
)
def test_widget_submit_validation_matches_webhook_contract(
    decision: str,
    support_flag: str,
) -> None:
    payload = _submit_payload(decision=decision, support_flag=support_flag)

    assert _is_valid_widget_submit(payload) is _is_valid_webhook_submit(payload)


def test_widget_submit_rejects_unknown_fields() -> None:
    payload = _submit_payload(decision="accept", support_flag="none")
    payload["unexpected"] = "value"

    with pytest.raises(ValidationError):
        WidgetDecisionSubmitRequest.model_validate(payload)


def test_widget_bootstrap_request_requires_case_id_and_rejects_extra_fields() -> None:
    with pytest.raises(ValidationError):
        WidgetDecisionBootstrapRequest.model_validate({"unexpected": "value"})



def test_widget_bootstrap_response_validates_required_shape() -> None:
    case_id = uuid4()

    response = WidgetDecisionBootstrapResponse.model_validate(
        {
            "case_id": str(case_id),
            "status": "WAIT_DOCTOR",
            "doctor_decision": None,
            "doctor_reason": None,
        }
    )

    assert response.case_id == case_id
    assert response.status == "WAIT_DOCTOR"



def test_widget_submit_response_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        WidgetDecisionSubmitResponse.model_validate({"ok": True, "unexpected": "value"})

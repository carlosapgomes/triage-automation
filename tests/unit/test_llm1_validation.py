from __future__ import annotations

import json
from uuid import uuid4

import pytest

from triage_automation.application.services.llm1_service import (
    Llm1RetriableError,
    Llm1Service,
)


class FakeLlmClient:
    def __init__(self, response_text: str) -> None:
        self.response_text = response_text
        self.calls: list[tuple[str, str]] = []

    async def complete(self, *, system_prompt: str, user_prompt: str) -> str:
        self.calls.append((system_prompt, user_prompt))
        return self.response_text


def _valid_llm1_payload(agency_record_number: str) -> dict[str, object]:
    return {
        "schema_version": "1.1",
        "language": "pt-BR",
        "agency_record_number": agency_record_number,
        "patient": {
            "name": "Paciente",
            "age": 45,
            "sex": "F",
            "document_id": None,
        },
        "eda": {
            "indication_category": "dyspepsia",
            "exclusion_type": "none",
            "is_pediatric": False,
            "foreign_body_suspected": False,
            "requested_procedure": {
                "name": "EDA",
                "urgency": "eletivo",
            },
            "labs": {
                "hb_g_dl": 10.2,
                "platelets_per_mm3": 140000,
                "inr": 1.1,
                "source_text_hint": None,
            },
            "ecg": {
                "report_present": "yes",
                "abnormal_flag": "no",
                "source_text_hint": None,
            },
            "asa": {
                "class": "II",
                "confidence": "media",
                "rationale": None,
            },
            "cardiovascular_risk": {
                "level": "low",
                "confidence": "media",
                "rationale": None,
            },
        },
        "policy_precheck": {
            "excluded_from_eda_flow": False,
            "exclusion_reason": None,
            "labs_required": True,
            "labs_pass": "yes",
            "labs_failed_items": [],
            "ecg_required": True,
            "ecg_present": "yes",
            "pediatric_flag": False,
            "notes": None,
        },
        "summary": {
            "one_liner": "Resumo clinico",
            "bullet_points": ["ponto 1", "ponto 2", "ponto 3"],
        },
        "extraction_quality": {
            "confidence": "media",
            "missing_fields": [],
            "notes": None,
        },
    }


@pytest.mark.asyncio
async def test_valid_llm1_response_parses_and_returns_artifacts() -> None:
    agency_record = "12345"
    client = FakeLlmClient(json.dumps(_valid_llm1_payload(agency_record)))
    service = Llm1Service(llm_client=client)

    result = await service.run(
        case_id=uuid4(),
        agency_record_number=agency_record,
        clean_text="texto limpo",
    )

    assert result.summary_text == "Resumo clinico"
    assert result.structured_data_json["agency_record_number"] == agency_record


@pytest.mark.asyncio
async def test_invalid_schema_is_retriable_llm1_error() -> None:
    client = FakeLlmClient(json.dumps({"schema_version": "1.1"}))
    service = Llm1Service(llm_client=client)

    with pytest.raises(Llm1RetriableError) as exc_info:
        await service.run(case_id=uuid4(), agency_record_number="12345", clean_text="texto")

    assert exc_info.value.cause == "llm1"


@pytest.mark.asyncio
async def test_non_json_response_is_rejected() -> None:
    client = FakeLlmClient("not-json")
    service = Llm1Service(llm_client=client)

    with pytest.raises(Llm1RetriableError) as exc_info:
        await service.run(case_id=uuid4(), agency_record_number="12345", clean_text="texto")

    assert exc_info.value.cause == "llm1"


@pytest.mark.asyncio
async def test_agency_record_number_is_injected_exactly_into_prompt() -> None:
    agency_record = "54321"
    client = FakeLlmClient(json.dumps(_valid_llm1_payload(agency_record)))
    service = Llm1Service(llm_client=client)

    await service.run(
        case_id=uuid4(),
        agency_record_number=agency_record,
        clean_text="texto limpo",
    )

    assert len(client.calls) == 1
    _, user_prompt = client.calls[0]
    assert f"agency_record_number: {agency_record}" in user_prompt

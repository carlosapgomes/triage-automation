from __future__ import annotations

from triage_automation.application.services.process_pdf_case_service import (
    build_llm_prompt_version_audit_payload,
)


def test_prompt_version_audit_payload_contains_prompt_names_and_versions() -> None:
    payload = build_llm_prompt_version_audit_payload(
        system_prompt_name="llm1_system",
        system_prompt_version=3,
        user_prompt_name="llm1_user",
        user_prompt_version=4,
    )

    assert payload == {
        "prompt_system_name": "llm1_system",
        "prompt_system_version": 3,
        "prompt_user_name": "llm1_user",
        "prompt_user_version": 4,
    }

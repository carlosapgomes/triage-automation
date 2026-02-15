"""LLM2 orchestration service for policy-aware suggestion generation."""

from __future__ import annotations

import json
from dataclasses import dataclass
from uuid import UUID

from pydantic import ValidationError

from triage_automation.application.dto.llm1_models import Llm1Response
from triage_automation.application.dto.llm2_models import Llm2Response
from triage_automation.application.services.prompt_template_service import (
    PROMPT_NAME_LLM2_SYSTEM,
    PROMPT_NAME_LLM2_USER,
    MissingActivePromptTemplateError,
    PromptTemplateService,
)
from triage_automation.domain.policy.eda_policy import (
    EdaPolicyPrecheckInput,
    Llm2PolicyAlignmentInput,
    Llm2SuggestionInput,
    reconcile_eda_policy,
)
from triage_automation.infrastructure.llm.llm_client import LlmClientPort


@dataclass(frozen=True)
class Llm2ServiceResult:
    """Validated and policy-reconciled LLM2 artifact for persistence."""

    suggested_action_json: dict[str, object]
    contradictions: list[dict[str, object]]
    prompt_system_name: str
    prompt_system_version: int
    prompt_user_name: str
    prompt_user_version: int


@dataclass(frozen=True)
class Llm2RetriableError(RuntimeError):
    """Retriable LLM2 failure with explicit cause label."""

    cause: str
    details: str

    def __str__(self) -> str:
        return f"{self.cause}: {self.details}"


class Llm2Service:
    """Execute LLM2 call, enforce schema, and apply deterministic policy rules."""

    def __init__(
        self,
        *,
        llm_client: LlmClientPort,
        prompt_templates: PromptTemplateService | None = None,
        system_prompt_name: str = PROMPT_NAME_LLM2_SYSTEM,
        user_prompt_name: str = PROMPT_NAME_LLM2_USER,
    ) -> None:
        self._llm_client = llm_client
        self._prompt_templates = prompt_templates
        self._system_prompt_name = system_prompt_name
        self._user_prompt_name = user_prompt_name

    async def run(
        self,
        *,
        case_id: UUID,
        agency_record_number: str,
        llm1_structured_data: dict[str, object],
        prior_case_json: dict[str, object] | None = None,
    ) -> Llm2ServiceResult:
        try:
            llm1_payload = Llm1Response.model_validate(llm1_structured_data)
        except ValidationError as error:
            raise Llm2RetriableError(
                cause="llm2",
                details=f"LLM1 payload invalid for LLM2 input: {error}",
            ) from error

        (
            system_prompt,
            user_prompt_template,
            system_prompt_name,
            system_prompt_version,
            user_prompt_name,
            user_prompt_version,
        ) = await self._load_prompts()
        user_prompt = _render_user_prompt(
            template=user_prompt_template,
            case_id=case_id,
            agency_record_number=agency_record_number,
            llm1_structured_data=llm1_structured_data,
            prior_case_json=prior_case_json,
        )

        raw_response = await self._llm_client.complete(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )

        try:
            decoded = json.loads(raw_response)
        except json.JSONDecodeError as error:
            raise Llm2RetriableError(
                cause="llm2",
                details="LLM2 returned non-JSON payload",
            ) from error

        try:
            validated = Llm2Response.model_validate(decoded)
        except ValidationError as error:
            raise Llm2RetriableError(
                cause="llm2",
                details=f"LLM2 schema validation failed: {error}",
            ) from error

        if validated.case_id != str(case_id):
            raise Llm2RetriableError(
                cause="llm2",
                details="LLM2 case_id mismatch",
            )

        if validated.agency_record_number != agency_record_number:
            raise Llm2RetriableError(
                cause="llm2",
                details="LLM2 agency_record_number mismatch",
            )

        policy_result = reconcile_eda_policy(
            precheck=EdaPolicyPrecheckInput(
                excluded_from_eda_flow=llm1_payload.policy_precheck.excluded_from_eda_flow,
                indication_category=llm1_payload.eda.indication_category,
                labs_required=llm1_payload.policy_precheck.labs_required,
                labs_pass=llm1_payload.policy_precheck.labs_pass,
                ecg_required=llm1_payload.policy_precheck.ecg_required,
                ecg_present=llm1_payload.policy_precheck.ecg_present,
                pediatric_flag=llm1_payload.policy_precheck.pediatric_flag,
            ),
            llm2=Llm2SuggestionInput(
                suggestion=validated.suggestion,
                policy_alignment=Llm2PolicyAlignmentInput(
                    excluded_request=validated.policy_alignment.excluded_request,
                    labs_ok=validated.policy_alignment.labs_ok,
                    ecg_ok=validated.policy_alignment.ecg_ok,
                    pediatric_flag=validated.policy_alignment.pediatric_flag,
                    notes=validated.policy_alignment.notes,
                ),
            ),
        )

        normalized = validated.model_dump(mode="json", by_alias=True)
        normalized["suggestion"] = policy_result.suggestion
        normalized["policy_alignment"] = {
            "excluded_request": policy_result.policy_alignment.excluded_request,
            "labs_ok": policy_result.policy_alignment.labs_ok,
            "ecg_ok": policy_result.policy_alignment.ecg_ok,
            "pediatric_flag": policy_result.policy_alignment.pediatric_flag,
            "notes": policy_result.policy_alignment.notes,
        }

        contradictions: list[dict[str, object]] = [
            {
                "rule": item.rule,
                "field": item.field,
                "previous_value": item.previous_value,
                "reconciled_value": item.reconciled_value,
            }
            for item in policy_result.contradictions
        ]

        return Llm2ServiceResult(
            suggested_action_json=normalized,
            contradictions=contradictions,
            prompt_system_name=system_prompt_name,
            prompt_system_version=system_prompt_version,
            prompt_user_name=user_prompt_name,
            prompt_user_version=user_prompt_version,
        )

    async def _load_prompts(self) -> tuple[str, str, str, int, str, int]:
        if self._prompt_templates is None:
            return (
                _default_system_prompt(),
                _default_user_prompt_template(),
                self._system_prompt_name,
                0,
                self._user_prompt_name,
                0,
            )

        try:
            pair = await self._prompt_templates.get_required_active_prompt_pair(
                system_prompt_name=self._system_prompt_name,
                user_prompt_name=self._user_prompt_name,
            )
        except MissingActivePromptTemplateError as error:
            raise Llm2RetriableError(cause="llm2", details=str(error)) from error

        return (
            pair.system.content,
            pair.user.content,
            pair.system.name,
            pair.system.version,
            pair.user.name,
            pair.user.version,
        )


def _default_system_prompt() -> str:
    return (
        "Voce e um assistente de apoio a triagem de Endoscopia Digestiva Alta (EDA). "
        "Responda apenas com JSON valido no schema v1.1, em pt-BR. "
        "Sugira accept ou deny e suporte (none, anesthesist, anesthesist_icu, unknown)."
    )


def _default_user_prompt_template() -> str:
    return "Tarefa: sugerir accept/deny e recomendacao de suporte para triagem de EDA."


def _render_user_prompt(
    *,
    template: str,
    case_id: UUID,
    agency_record_number: str,
    llm1_structured_data: dict[str, object],
    prior_case_json: dict[str, object] | None,
) -> str:
    prior_case = json.dumps(
        prior_case_json if prior_case_json is not None else None,
        ensure_ascii=False,
    )
    llm1_json = json.dumps(llm1_structured_data, ensure_ascii=False)
    return (
        f"{template}\n\n"
        f"case_id: {case_id}\n"
        f"agency_record_number: {agency_record_number}\n\n"
        f"Dados extraidos (JSON do LLM1):\n{llm1_json}\n\n"
        f"Prior decision (se existir):\n{prior_case}\n\n"
        "Retorne JSON schema_version 1.1 com policy_alignment e confidence."
    )

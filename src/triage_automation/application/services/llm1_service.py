"""LLM1 orchestration service for structured extraction and summary generation."""

from __future__ import annotations

import json
from dataclasses import dataclass
from uuid import UUID

from pydantic import ValidationError

from triage_automation.application.dto.llm1_models import Llm1Response
from triage_automation.application.services.prompt_template_service import (
    PROMPT_NAME_LLM1_SYSTEM,
    PROMPT_NAME_LLM1_USER,
    MissingActivePromptTemplateError,
    PromptTemplateService,
)
from triage_automation.infrastructure.llm.llm_client import LlmClientPort


@dataclass(frozen=True)
class Llm1ServiceResult:
    """Validated and normalized LLM1 artifacts for persistence."""

    structured_data_json: dict[str, object]
    summary_text: str
    prompt_system_name: str
    prompt_system_version: int
    prompt_user_name: str
    prompt_user_version: int


@dataclass(frozen=True)
class Llm1RetriableError(RuntimeError):
    """Retriable LLM1 failure with explicit cause label."""

    cause: str
    details: str

    def __str__(self) -> str:
        return f"{self.cause}: {self.details}"


class Llm1Service:
    """Execute LLM1 call, enforce schema, and normalize output."""

    def __init__(
        self,
        *,
        llm_client: LlmClientPort,
        prompt_templates: PromptTemplateService | None = None,
        system_prompt_name: str = PROMPT_NAME_LLM1_SYSTEM,
        user_prompt_name: str = PROMPT_NAME_LLM1_USER,
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
        clean_text: str,
    ) -> Llm1ServiceResult:
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
            clean_text=clean_text,
        )

        raw_response = await self._llm_client.complete(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )

        try:
            decoded = json.loads(raw_response)
        except json.JSONDecodeError as error:
            raise Llm1RetriableError(
                cause="llm1",
                details="LLM1 returned non-JSON payload",
            ) from error

        try:
            validated = Llm1Response.model_validate(decoded)
        except ValidationError as error:
            raise Llm1RetriableError(
                cause="llm1",
                details=f"LLM1 schema validation failed: {error}",
            ) from error

        if validated.agency_record_number != agency_record_number:
            raise Llm1RetriableError(
                cause="llm1",
                details="LLM1 agency_record_number mismatch",
            )

        structured = validated.model_dump(mode="json", by_alias=True)
        return Llm1ServiceResult(
            structured_data_json=structured,
            summary_text=validated.summary.one_liner,
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
            raise Llm1RetriableError(cause="llm1", details=str(error)) from error

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
        "Voce e um assistente clinico para triagem de Endoscopia Digestiva Alta (EDA). "
        "Responda apenas com JSON valido no schema v1.1, em pt-BR. "
        "Nao invente fatos; use null/unknown quando faltar informacao."
    )


def _default_user_prompt_template() -> str:
    return (
        "Tarefa: extrair dados estruturados e resumo de um relatorio clinico "
        "para triagem de EDA."
    )


def _render_user_prompt(
    *,
    template: str,
    case_id: UUID,
    agency_record_number: str,
    clean_text: str,
) -> str:
    return (
        f"{template}\n\n"
        f"case_id: {case_id}\n"
        f"agency_record_number: {agency_record_number}\n\n"
        "Retorne JSON schema_version 1.1 e preserve agency_record_number exatamente.\n\n"
        f"Texto do relatorio:\n{clean_text}"
    )

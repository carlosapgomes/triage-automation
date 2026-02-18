"""LLM1 orchestration service for structured extraction and summary generation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from pydantic import ValidationError

from triage_automation.application.dto.llm1_models import Llm1Response
from triage_automation.application.ports.case_repository_port import (
    CaseLlmInteractionCreateInput,
    CaseRepositoryPort,
)
from triage_automation.application.services.llm_json_parser import (
    LlmJsonParseError,
    decode_llm_json_object,
)
from triage_automation.application.services.prompt_template_service import (
    PROMPT_NAME_LLM1_SYSTEM,
    PROMPT_NAME_LLM1_USER,
    MissingActivePromptTemplateError,
    PromptTemplateService,
)
from triage_automation.application.services.ptbr_language_guard import (
    collect_forbidden_terms,
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

    _LANGUAGE_RETRY_INSTRUCTION = (
        "Regra obrigatoria adicional: todo texto narrativo deve estar em portugues "
        "brasileiro (pt-BR), sem palavras em ingles."
    )

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
        interaction_repository: CaseRepositoryPort | None = None,
    ) -> Llm1ServiceResult:
        """Execute LLM1 and return validated structured extraction artifacts."""

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

        raw_response = await self._complete_and_capture(
            case_id=case_id,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            prompt_system_name=system_prompt_name,
            prompt_system_version=system_prompt_version,
            prompt_user_name=user_prompt_name,
            prompt_user_version=user_prompt_version,
            interaction_repository=interaction_repository,
        )
        validated = _decode_and_validate_llm1_response(
            raw_response=raw_response,
            agency_record_number=agency_record_number,
        )

        forbidden_terms = _collect_llm1_forbidden_terms(validated=validated)
        if forbidden_terms:
            retry_user_prompt = (
                f"{user_prompt}\n\n"
                f"{self._LANGUAGE_RETRY_INSTRUCTION}"
            )
            retry_response = await self._complete_and_capture(
                case_id=case_id,
                system_prompt=system_prompt,
                user_prompt=retry_user_prompt,
                prompt_system_name=system_prompt_name,
                prompt_system_version=system_prompt_version,
                prompt_user_name=user_prompt_name,
                prompt_user_version=user_prompt_version,
                interaction_repository=interaction_repository,
            )
            validated = _decode_and_validate_llm1_response(
                raw_response=retry_response,
                agency_record_number=agency_record_number,
            )
            forbidden_terms = _collect_llm1_forbidden_terms(validated=validated)
            if forbidden_terms:
                joined_terms = ", ".join(forbidden_terms)
                raise Llm1RetriableError(
                    cause="llm1",
                    details=(
                        "LLM1 output contains non-ptbr narrative terms after retry: "
                        f"{joined_terms}"
                    ),
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

    async def _complete_and_capture(
        self,
        *,
        case_id: UUID,
        system_prompt: str,
        user_prompt: str,
        prompt_system_name: str,
        prompt_system_version: int,
        prompt_user_name: str,
        prompt_user_version: int,
        interaction_repository: CaseRepositoryPort | None,
    ) -> str:
        raw_response = await self._llm_client.complete(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )
        if interaction_repository is not None:
            await interaction_repository.append_case_llm_interaction(
                CaseLlmInteractionCreateInput(
                    case_id=case_id,
                    stage="LLM1",
                    input_payload=_build_llm_input_payload(
                        system_prompt=system_prompt,
                        user_prompt=user_prompt,
                    ),
                    output_payload={"raw_response": raw_response},
                    prompt_system_name=prompt_system_name,
                    prompt_system_version=prompt_system_version,
                    prompt_user_name=prompt_user_name,
                    prompt_user_version=prompt_user_version,
                    model_name=_resolve_model_name(self._llm_client),
                )
            )
        return raw_response

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
        "Retorne APENAS JSON valido que siga estritamente o schema_version 1.1. "
        "Escreva todos os campos narrativos em portugues brasileiro (pt-BR). "
        "Nao use palavras em ingles nos campos narrativos. "
        "Nao inclua markdown, blocos de codigo ou chaves extras. "
        "Nao invente fatos; use null/unknown quando faltar informacao."
    )


def _default_user_prompt_template() -> str:
    return (
        "Tarefa: extrair dados estruturados e gerar resumo conciso de triagem "
        "a partir de um relatorio clinico para triagem EDA."
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
        "Retorne JSON schema_version 1.1 e preserve agency_record_number exatamente.\n"
        "Todos os campos narrativos devem estar em portugues brasileiro (pt-BR).\n"
        "Nao use palavras em ingles nos campos narrativos.\n\n"
        f"Texto clinico do relatorio:\n{clean_text}"
    )


def _decode_and_validate_llm1_response(
    *,
    raw_response: str,
    agency_record_number: str,
) -> Llm1Response:
    try:
        decoded = decode_llm_json_object(raw_response)
    except LlmJsonParseError as error:
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

    return validated


def _collect_llm1_forbidden_terms(*, validated: Llm1Response) -> list[str]:
    texts: list[str] = [
        validated.summary.one_liner,
        *validated.summary.bullet_points,
    ]
    optional_texts = [
        validated.policy_precheck.notes,
        validated.extraction_quality.notes,
        validated.eda.asa.rationale,
        validated.eda.cardiovascular_risk.rationale,
    ]
    texts.extend(text for text in optional_texts if text is not None)
    return collect_forbidden_terms(texts=texts)


def _build_llm_input_payload(*, system_prompt: str, user_prompt: str) -> dict[str, Any]:
    return {
        "system_prompt": system_prompt,
        "user_prompt": user_prompt,
    }


def _resolve_model_name(client: LlmClientPort) -> str | None:
    model_name = getattr(client, "model_name", None)
    if isinstance(model_name, str) and model_name.strip():
        return model_name
    return None

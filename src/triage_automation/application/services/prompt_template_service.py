"""Service helpers for loading required active prompt template versions."""

from __future__ import annotations

from triage_automation.application.ports.prompt_template_repository_port import (
    PromptTemplateRecord,
    PromptTemplateRepositoryPort,
)

PROMPT_NAME_LLM1_SYSTEM = "llm1_system"
PROMPT_NAME_LLM1_USER = "llm1_user"
PROMPT_NAME_LLM2_SYSTEM = "llm2_system"
PROMPT_NAME_LLM2_USER = "llm2_user"


class MissingActivePromptTemplateError(LookupError):
    """Raised when a required prompt has no active template row."""

    def __init__(self, *, name: str) -> None:
        self.name = name
        super().__init__(f"Missing active prompt template for name '{name}'")


class PromptTemplateService:
    """Load active prompt content/version for worker orchestration use."""

    def __init__(self, *, prompt_templates: PromptTemplateRepositoryPort) -> None:
        self._prompt_templates = prompt_templates

    async def get_required_active_prompt(self, *, name: str) -> PromptTemplateRecord:
        """Return active prompt template or raise explicit missing-template error."""

        prompt = await self._prompt_templates.get_active_by_name(name=name)
        if prompt is None:
            raise MissingActivePromptTemplateError(name=name)
        return prompt

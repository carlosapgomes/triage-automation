from __future__ import annotations

import pytest

from triage_automation.application.ports.prompt_template_repository_port import PromptTemplateRecord
from triage_automation.application.services.prompt_template_service import (
    MissingActivePromptTemplateError,
    PromptTemplateService,
)


class FakePromptTemplateRepository:
    def __init__(self, record: PromptTemplateRecord | None) -> None:
        self._record = record
        self.names: list[str] = []

    async def get_active_by_name(self, *, name: str) -> PromptTemplateRecord | None:
        self.names.append(name)
        return self._record


@pytest.mark.asyncio
async def test_service_returns_active_prompt_content_and_version() -> None:
    repo = FakePromptTemplateRepository(
        PromptTemplateRecord(
            name="llm1_system",
            version=7,
            content="prompt content",
        )
    )
    service = PromptTemplateService(prompt_templates=repo)

    resolved = await service.get_required_active_prompt(name="llm1_system")

    assert resolved.name == "llm1_system"
    assert resolved.version == 7
    assert resolved.content == "prompt content"
    assert repo.names == ["llm1_system"]


@pytest.mark.asyncio
async def test_service_raises_explicit_error_when_active_prompt_missing() -> None:
    repo = FakePromptTemplateRepository(None)
    service = PromptTemplateService(prompt_templates=repo)

    with pytest.raises(MissingActivePromptTemplateError) as error_info:
        await service.get_required_active_prompt(name="llm2_user")

    assert "llm2_user" in str(error_info.value)

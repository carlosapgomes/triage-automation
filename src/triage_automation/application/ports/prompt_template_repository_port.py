"""Port for retrieving active prompt template versions by name."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class PromptTemplateRecord:
    """Active prompt template model used by application services."""

    name: str
    version: int
    content: str


class PromptTemplateRepositoryPort(Protocol):
    """Prompt template persistence contract."""

    async def get_active_by_name(self, *, name: str) -> PromptTemplateRecord | None:
        """Return active prompt template for name, or None when absent."""

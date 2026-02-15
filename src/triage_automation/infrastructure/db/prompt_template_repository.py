"""SQLAlchemy adapter for prompt template retrieval queries."""

from __future__ import annotations

from typing import cast

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from triage_automation.application.ports.prompt_template_repository_port import (
    PromptTemplateRecord,
    PromptTemplateRepositoryPort,
)
from triage_automation.infrastructure.db.metadata import prompt_templates


class SqlAlchemyPromptTemplateRepository(PromptTemplateRepositoryPort):
    """Prompt template repository backed by SQLAlchemy async sessions."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def get_active_by_name(self, *, name: str) -> PromptTemplateRecord | None:
        """Return latest active template version for the provided prompt name."""

        statement = (
            sa.select(
                prompt_templates.c.name,
                prompt_templates.c.version,
                prompt_templates.c.content,
            )
            .where(
                prompt_templates.c.name == name,
                prompt_templates.c.is_active.is_(True),
            )
            .order_by(prompt_templates.c.version.desc())
            .limit(1)
        )

        async with self._session_factory() as session:
            result = await session.execute(statement)

        row = result.mappings().first()
        if row is None:
            return None

        return PromptTemplateRecord(
            name=cast(str, row["name"]),
            version=int(row["version"]),
            content=cast(str, row["content"]),
        )

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
import sqlalchemy as sa
from alembic.config import Config

from alembic import command
from triage_automation.infrastructure.db.prompt_template_repository import (
    SqlAlchemyPromptTemplateRepository,
)
from triage_automation.infrastructure.db.session import create_session_factory


def _upgrade_head(tmp_path: Path, filename: str) -> tuple[str, str]:
    db_path = tmp_path / filename
    sync_url = f"sqlite+pysqlite:///{db_path}"
    async_url = f"sqlite+aiosqlite:///{db_path}"

    alembic_config = Config("alembic.ini")
    alembic_config.set_main_option("sqlalchemy.url", sync_url)
    command.upgrade(alembic_config, "head")

    return sync_url, async_url


@pytest.mark.asyncio
async def test_repository_returns_seeded_active_prompt(tmp_path: Path) -> None:
    _, async_url = _upgrade_head(tmp_path, "prompt_repo_seeded.db")
    session_factory = create_session_factory(async_url)
    repo = SqlAlchemyPromptTemplateRepository(session_factory)

    prompt = await repo.get_active_by_name(name="llm1_system")

    assert prompt is not None
    assert prompt.name == "llm1_system"
    assert prompt.version == 1
    assert prompt.content.strip() != ""


@pytest.mark.asyncio
async def test_repository_returns_none_when_no_active_prompt_exists(tmp_path: Path) -> None:
    _, async_url = _upgrade_head(tmp_path, "prompt_repo_missing.db")
    session_factory = create_session_factory(async_url)
    repo = SqlAlchemyPromptTemplateRepository(session_factory)

    prompt = await repo.get_active_by_name(name="missing_prompt_name")

    assert prompt is None


@pytest.mark.asyncio
async def test_repository_resolves_only_active_version_for_same_name(tmp_path: Path) -> None:
    sync_url, async_url = _upgrade_head(tmp_path, "prompt_repo_versions.db")
    session_factory = create_session_factory(async_url)
    repo = SqlAlchemyPromptTemplateRepository(session_factory)

    engine = sa.create_engine(sync_url)
    with engine.begin() as connection:
        connection.execute(
            sa.text(
                "INSERT INTO prompt_templates (id, name, version, content, is_active) "
                "VALUES (:id, :name, :version, :content, :is_active)"
            ),
            {
                "id": uuid4().hex,
                "name": "llm1_system",
                "version": 2,
                "content": "inactive version",
                "is_active": False,
            },
        )
        connection.execute(
            sa.text(
                "UPDATE prompt_templates SET is_active = 0 "
                "WHERE name = :name AND version = 1"
            ),
            {"name": "llm1_system"},
        )
        connection.execute(
            sa.text(
                "INSERT INTO prompt_templates (id, name, version, content, is_active) "
                "VALUES (:id, :name, :version, :content, :is_active)"
            ),
            {
                "id": uuid4().hex,
                "name": "llm1_system",
                "version": 3,
                "content": "active version 3",
                "is_active": True,
            },
        )

    prompt = await repo.get_active_by_name(name="llm1_system")

    assert prompt is not None
    assert prompt.version == 3
    assert prompt.content == "active version 3"

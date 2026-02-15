from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
import sqlalchemy as sa
from alembic.config import Config

from alembic import command


def _upgrade_head(tmp_path: Path) -> str:
    db_path = tmp_path / "slice19_prompt_templates.db"
    database_url = f"sqlite+pysqlite:///{db_path}"

    alembic_config = Config("alembic.ini")
    alembic_config.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(alembic_config, "head")

    return database_url


def test_prompt_templates_table_exists_with_required_columns_and_seed_rows(
    tmp_path: Path,
) -> None:
    database_url = _upgrade_head(tmp_path)
    engine = sa.create_engine(database_url)
    inspector = sa.inspect(engine)

    assert "prompt_templates" in set(inspector.get_table_names())

    columns = {column["name"]: column for column in inspector.get_columns("prompt_templates")}
    assert set(columns.keys()) == {
        "id",
        "name",
        "version",
        "content",
        "is_active",
        "created_at",
        "updated_at",
        "updated_by_user_id",
    }
    assert columns["updated_by_user_id"]["nullable"] is True

    with engine.begin() as connection:
        rows = connection.execute(
            sa.text(
                "SELECT name, version, is_active, content "
                "FROM prompt_templates "
                "ORDER BY name"
            )
        ).mappings().all()

    assert len(rows) == 4
    expected_names = {"llm1_system", "llm1_user", "llm2_system", "llm2_user"}
    assert {str(row["name"]) for row in rows} == expected_names
    assert all(int(row["version"]) == 1 for row in rows)
    assert all(bool(row["is_active"]) for row in rows)
    assert all(str(row["content"]).strip() != "" for row in rows)


def test_prompt_templates_indexes_and_constraints_are_enforced(tmp_path: Path) -> None:
    database_url = _upgrade_head(tmp_path)
    engine = sa.create_engine(database_url)
    inspector = sa.inspect(engine)

    uniques = {
        tuple(sorted(constraint["column_names"]))
        for constraint in inspector.get_unique_constraints("prompt_templates")
    }
    assert ("name", "version") in uniques

    indexes = {index["name"] for index in inspector.get_indexes("prompt_templates")}
    assert "ix_prompt_templates_name" in indexes
    assert "ux_prompt_templates_name_active_true" in indexes

    with engine.begin() as connection:
        partial_index_sql = connection.execute(
            sa.text(
                "SELECT sql FROM sqlite_master "
                "WHERE type = 'index' AND name = 'ux_prompt_templates_name_active_true'"
            )
        ).scalar_one()

    assert partial_index_sql is not None
    assert "WHERE is_active = 1" in str(partial_index_sql)

    with engine.begin() as connection:
        connection.execute(
            sa.text(
                "INSERT INTO prompt_templates (id, name, version, content, is_active) "
                "VALUES (:id, :name, :version, :content, :is_active)"
            ),
            {
                "id": uuid4().hex,
                "name": "triage_custom_prompt",
                "version": 1,
                "content": "v1",
                "is_active": False,
            },
        )

        with pytest.raises(sa.exc.IntegrityError):
            connection.execute(
                sa.text(
                    "INSERT INTO prompt_templates (id, name, version, content, is_active) "
                    "VALUES (:id, :name, :version, :content, :is_active)"
                ),
                {
                    "id": uuid4().hex,
                    "name": "triage_custom_prompt",
                    "version": 1,
                    "content": "duplicate",
                    "is_active": False,
                },
            )

        with pytest.raises(sa.exc.IntegrityError):
            connection.execute(
                sa.text(
                    "INSERT INTO prompt_templates (id, name, version, content, is_active) "
                    "VALUES (:id, :name, :version, :content, :is_active)"
                ),
                {
                    "id": uuid4().hex,
                    "name": "invalid_version_prompt",
                    "version": 0,
                    "content": "invalid",
                    "is_active": False,
                },
            )

        connection.execute(
            sa.text(
                "INSERT INTO prompt_templates (id, name, version, content, is_active) "
                "VALUES (:id, :name, :version, :content, :is_active)"
            ),
            {
                "id": uuid4().hex,
                "name": "one_active_prompt",
                "version": 1,
                "content": "active-v1",
                "is_active": True,
            },
        )
        with pytest.raises(sa.exc.IntegrityError):
            connection.execute(
                sa.text(
                    "INSERT INTO prompt_templates (id, name, version, content, is_active) "
                    "VALUES (:id, :name, :version, :content, :is_active)"
                ),
                {
                    "id": uuid4().hex,
                    "name": "one_active_prompt",
                    "version": 2,
                    "content": "active-v2",
                    "is_active": True,
                },
            )


def test_prompt_templates_updated_by_user_id_has_no_foreign_key_yet(tmp_path: Path) -> None:
    database_url = _upgrade_head(tmp_path)
    engine = sa.create_engine(database_url)
    inspector = sa.inspect(engine)

    assert inspector.get_foreign_keys("prompt_templates") == []

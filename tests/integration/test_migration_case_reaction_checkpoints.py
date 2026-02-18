from __future__ import annotations

from pathlib import Path

import sqlalchemy as sa
from alembic.config import Config

from alembic import command


def _upgrade_head(tmp_path: Path) -> str:
    db_path = tmp_path / "slice_reaction_checkpoints.db"
    database_url = f"sqlite+pysqlite:///{db_path}"

    alembic_config = Config("alembic.ini")
    alembic_config.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(alembic_config, "head")
    return database_url


def test_case_reaction_checkpoints_table_exists_with_required_columns(tmp_path: Path) -> None:
    database_url = _upgrade_head(tmp_path)
    engine = sa.create_engine(database_url)
    inspector = sa.inspect(engine)

    assert "case_reaction_checkpoints" in set(inspector.get_table_names())

    columns = {column["name"] for column in inspector.get_columns("case_reaction_checkpoints")}
    assert columns == {
        "id",
        "case_id",
        "stage",
        "room_id",
        "target_event_id",
        "expected_at",
        "outcome",
        "reaction_event_id",
        "reactor_user_id",
        "reaction_key",
        "reacted_at",
    }


def test_case_reaction_checkpoints_has_case_fk(tmp_path: Path) -> None:
    database_url = _upgrade_head(tmp_path)
    engine = sa.create_engine(database_url)
    inspector = sa.inspect(engine)

    foreign_keys = inspector.get_foreign_keys("case_reaction_checkpoints")
    assert any(
        foreign_key["referred_table"] == "cases"
        and foreign_key["constrained_columns"] == ["case_id"]
        for foreign_key in foreign_keys
    )

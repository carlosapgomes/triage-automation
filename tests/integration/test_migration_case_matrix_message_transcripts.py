from __future__ import annotations

from pathlib import Path

import sqlalchemy as sa
from alembic.config import Config

from alembic import command


def _upgrade_head(tmp_path: Path) -> str:
    db_path = tmp_path / "slice_dashboard_matrix_message_transcripts.db"
    database_url = f"sqlite+pysqlite:///{db_path}"

    alembic_config = Config("alembic.ini")
    alembic_config.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(alembic_config, "head")
    return database_url


def test_case_matrix_message_transcripts_table_has_required_columns(tmp_path: Path) -> None:
    database_url = _upgrade_head(tmp_path)
    engine = sa.create_engine(database_url)
    inspector = sa.inspect(engine)

    assert "case_matrix_message_transcripts" in set(inspector.get_table_names())

    columns = {
        column["name"] for column in inspector.get_columns("case_matrix_message_transcripts")
    }
    assert columns == {
        "id",
        "case_id",
        "room_id",
        "event_id",
        "sender",
        "message_type",
        "message_text",
        "reply_to_event_id",
        "captured_at",
    }


def test_case_matrix_message_transcripts_has_case_foreign_key(tmp_path: Path) -> None:
    database_url = _upgrade_head(tmp_path)
    engine = sa.create_engine(database_url)
    inspector = sa.inspect(engine)

    foreign_keys = inspector.get_foreign_keys("case_matrix_message_transcripts")
    assert any(
        foreign_key["referred_table"] == "cases"
        and foreign_key["constrained_columns"] == ["case_id"]
        for foreign_key in foreign_keys
    )

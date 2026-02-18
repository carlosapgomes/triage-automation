from __future__ import annotations

from pathlib import Path

import sqlalchemy as sa
from alembic.config import Config

from alembic import command


def _upgrade_head(tmp_path: Path) -> str:
    db_path = tmp_path / "slice_dashboard_transcript_indexes.db"
    database_url = f"sqlite+pysqlite:///{db_path}"

    alembic_config = Config("alembic.ini")
    alembic_config.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(alembic_config, "head")
    return database_url


def test_transcript_tables_have_case_id_captured_at_indexes(tmp_path: Path) -> None:
    database_url = _upgrade_head(tmp_path)
    engine = sa.create_engine(database_url)
    inspector = sa.inspect(engine)

    report_indexes = {index["name"] for index in inspector.get_indexes("case_report_transcripts")}
    assert "ix_case_report_transcripts_case_id_captured_at" in report_indexes

    llm_indexes = {index["name"] for index in inspector.get_indexes("case_llm_interactions")}
    assert "ix_case_llm_interactions_case_id_captured_at" in llm_indexes

    matrix_indexes = {
        index["name"] for index in inspector.get_indexes("case_matrix_message_transcripts")
    }
    assert "ix_case_matrix_message_transcripts_case_id_captured_at" in matrix_indexes

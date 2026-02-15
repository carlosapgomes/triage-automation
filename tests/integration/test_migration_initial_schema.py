from __future__ import annotations

from pathlib import Path

import sqlalchemy as sa
from alembic.config import Config

from alembic import command


def _upgrade_head(tmp_path: Path) -> str:
    db_path = tmp_path / "slice3_migration.db"
    database_url = f"sqlite+pysqlite:///{db_path}"

    alembic_config = Config("alembic.ini")
    alembic_config.set_main_option("sqlalchemy.url", database_url)

    command.upgrade(alembic_config, "head")
    return database_url


def test_migration_creates_required_tables(tmp_path: Path) -> None:
    database_url = _upgrade_head(tmp_path)
    engine = sa.create_engine(database_url)

    inspector = sa.inspect(engine)
    table_names = set(inspector.get_table_names())

    assert "cases" in table_names
    assert "case_events" in table_names
    assert "case_messages" in table_names
    assert "jobs" in table_names


def test_migration_creates_required_uniques_and_indexes(tmp_path: Path) -> None:
    database_url = _upgrade_head(tmp_path)
    engine = sa.create_engine(database_url)
    inspector = sa.inspect(engine)

    cases_uniques = {
        tuple(sorted(constraint["column_names"]))
        for constraint in inspector.get_unique_constraints("cases")
    }
    assert ("room1_origin_event_id",) in cases_uniques

    case_messages_uniques = {
        tuple(sorted(constraint["column_names"]))
        for constraint in inspector.get_unique_constraints("case_messages")
    }
    assert ("event_id", "room_id") in case_messages_uniques

    cases_indexes = {index["name"] for index in inspector.get_indexes("cases")}
    assert "ix_cases_agency_record_number_created_at" in cases_indexes
    assert "ix_cases_status" in cases_indexes
    assert "ix_cases_room1_final_reply_event_id" in cases_indexes

    case_events_indexes = {index["name"] for index in inspector.get_indexes("case_events")}
    assert "ix_case_events_case_id_ts" in case_events_indexes
    assert "ix_case_events_event_type_ts" in case_events_indexes

    case_messages_indexes = {index["name"] for index in inspector.get_indexes("case_messages")}
    assert "ix_case_messages_case_id" in case_messages_indexes
    assert "ix_case_messages_kind" in case_messages_indexes

    jobs_indexes = {index["name"] for index in inspector.get_indexes("jobs")}
    assert "ix_jobs_status_run_after" in jobs_indexes
    assert "ix_jobs_case_id" in jobs_indexes


def test_jobs_status_default_is_queued(tmp_path: Path) -> None:
    database_url = _upgrade_head(tmp_path)
    engine = sa.create_engine(database_url)

    with engine.begin() as connection:
        connection.execute(sa.text("INSERT INTO jobs (job_type) VALUES ('process_pdf_case')"))
        status = connection.execute(sa.text("SELECT status FROM jobs LIMIT 1")).scalar_one()

    assert status == "queued"

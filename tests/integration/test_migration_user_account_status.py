from __future__ import annotations

import re
from pathlib import Path

import sqlalchemy as sa
from alembic.config import Config

from alembic import command


def _configure_alembic(database_url: str) -> Config:
    alembic_config = Config("alembic.ini")
    alembic_config.set_main_option("sqlalchemy.url", database_url)
    return alembic_config


def test_users_schema_includes_account_status_column_and_constraint(tmp_path: Path) -> None:
    db_path = tmp_path / "slice_user_account_status_schema.db"
    database_url = f"sqlite+pysqlite:///{db_path}"

    command.upgrade(_configure_alembic(database_url), "head")

    engine = sa.create_engine(database_url)
    inspector = sa.inspect(engine)
    columns = {column["name"]: column for column in inspector.get_columns("users")}
    assert "account_status" in columns
    assert bool(columns["account_status"]["nullable"]) is False

    status_checks = [
        check
        for check in inspector.get_check_constraints("users")
        if check["name"] == "ck_users_account_status"
    ]
    assert len(status_checks) == 1
    sqltext = str(status_checks[0].get("sqltext", ""))
    values = set(re.findall(r"'([^']+)'", sqltext))
    assert values == {"active", "blocked", "removed"}


def test_upgrade_from_0012_maps_legacy_users_to_account_status(tmp_path: Path) -> None:
    db_path = tmp_path / "slice_user_account_status_data.db"
    database_url = f"sqlite+pysqlite:///{db_path}"
    alembic_config = _configure_alembic(database_url)

    command.upgrade(alembic_config, "0012_actor_display_names")

    engine = sa.create_engine(database_url)
    with engine.begin() as connection:
        connection.execute(
            sa.text(
                "INSERT INTO users (id, email, password_hash, role, is_active) "
                "VALUES "
                "('00000000-0000-0000-0000-000000000101', 'active@example.org', 'h1', 'admin', 1), "
                "('00000000-0000-0000-0000-000000000102', 'blocked@example.org', 'h2', 'reader', 0)"
            )
        )

    command.upgrade(alembic_config, "head")

    with engine.connect() as connection:
        rows = (
            connection.execute(
                sa.text(
                    "SELECT email, is_active, account_status "
                    "FROM users "
                    "ORDER BY email"
                )
            )
            .mappings()
            .all()
        )

    by_email = {str(row["email"]): row for row in rows}
    assert by_email["active@example.org"]["account_status"] == "active"
    assert bool(by_email["active@example.org"]["is_active"]) is True
    assert by_email["blocked@example.org"]["account_status"] == "blocked"
    assert bool(by_email["blocked@example.org"]["is_active"]) is False

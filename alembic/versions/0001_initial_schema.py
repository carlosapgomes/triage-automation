"""Initial schema for cases, case events, case messages, and jobs."""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None

sqlite_bigint = sa.BigInteger().with_variant(sa.Integer(), "sqlite")


def upgrade() -> None:
    op.create_table(
        "cases",
        sa.Column("case_id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("room1_origin_room_id", sa.Text(), nullable=False),
        sa.Column("room1_origin_event_id", sa.Text(), nullable=False),
        sa.Column("room1_sender_user_id", sa.Text(), nullable=False),
        sa.Column("agency_record_number", sa.Text(), nullable=True),
        sa.Column("agency_record_extracted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("doctor_user_id", sa.Text(), nullable=True),
        sa.Column("doctor_decision", sa.Text(), nullable=True),
        sa.Column("doctor_support_flag", sa.Text(), nullable=True),
        sa.Column("doctor_reason", sa.Text(), nullable=True),
        sa.Column("doctor_decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("scheduler_user_id", sa.Text(), nullable=True),
        sa.Column("appointment_status", sa.Text(), nullable=True),
        sa.Column("appointment_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("appointment_location", sa.Text(), nullable=True),
        sa.Column("appointment_instructions", sa.Text(), nullable=True),
        sa.Column("appointment_reason", sa.Text(), nullable=True),
        sa.Column("appointment_decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("room1_final_reply_event_id", sa.Text(), nullable=True),
        sa.Column("room1_final_reply_posted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cleanup_triggered_by_user_id", sa.Text(), nullable=True),
        sa.Column("cleanup_triggered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cleanup_completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "artifact_storage_mode",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'full_pdf'"),
        ),
        sa.Column("pdf_mxc_url", sa.Text(), nullable=True),
        sa.Column("pdf_sha256", sa.Text(), nullable=True),
        sa.Column("extracted_text", sa.Text(), nullable=True),
        sa.Column("structured_data_json", sa.JSON(), nullable=True),
        sa.Column("summary_text", sa.Text(), nullable=True),
        sa.Column("suggested_action_json", sa.JSON(), nullable=True),
        sa.UniqueConstraint("room1_origin_event_id", name="uq_cases_room1_origin_event_id"),
    )

    op.create_index(
        "ix_cases_agency_record_number_created_at",
        "cases",
        ["agency_record_number", "created_at"],
        unique=False,
    )
    op.create_index("ix_cases_status", "cases", ["status"], unique=False)
    op.create_index(
        "ix_cases_room1_final_reply_event_id",
        "cases",
        ["room1_final_reply_event_id"],
        unique=False,
    )

    op.create_table(
        "case_events",
        sa.Column("id", sqlite_bigint, primary_key=True, autoincrement=True),
        sa.Column("case_id", sa.Uuid(), sa.ForeignKey("cases.case_id"), nullable=False),
        sa.Column(
            "ts",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("actor_type", sa.Text(), nullable=False),
        sa.Column("actor_user_id", sa.Text(), nullable=True),
        sa.Column("room_id", sa.Text(), nullable=True),
        sa.Column("matrix_event_id", sa.Text(), nullable=True),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
    )

    op.create_index("ix_case_events_case_id_ts", "case_events", ["case_id", "ts"], unique=False)
    op.create_index(
        "ix_case_events_event_type_ts",
        "case_events",
        ["event_type", "ts"],
        unique=False,
    )

    op.create_table(
        "case_messages",
        sa.Column("id", sqlite_bigint, primary_key=True, autoincrement=True),
        sa.Column("case_id", sa.Uuid(), sa.ForeignKey("cases.case_id"), nullable=False),
        sa.Column("room_id", sa.Text(), nullable=False),
        sa.Column("event_id", sa.Text(), nullable=False),
        sa.Column("sender_user_id", sa.Text(), nullable=True),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.UniqueConstraint("room_id", "event_id", name="uq_case_messages_room_event"),
    )

    op.create_index("ix_case_messages_case_id", "case_messages", ["case_id"], unique=False)
    op.create_index("ix_case_messages_kind", "case_messages", ["kind"], unique=False)

    op.create_table(
        "jobs",
        sa.Column("job_id", sqlite_bigint, primary_key=True, autoincrement=True),
        sa.Column("case_id", sa.Uuid(), sa.ForeignKey("cases.case_id"), nullable=True),
        sa.Column("job_type", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'queued'")),
        sa.Column(
            "run_after",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default=sa.text("5")),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )

    op.create_index("ix_jobs_status_run_after", "jobs", ["status", "run_after"], unique=False)
    op.create_index("ix_jobs_case_id", "jobs", ["case_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_jobs_case_id", table_name="jobs")
    op.drop_index("ix_jobs_status_run_after", table_name="jobs")
    op.drop_table("jobs")

    op.drop_index("ix_case_messages_kind", table_name="case_messages")
    op.drop_index("ix_case_messages_case_id", table_name="case_messages")
    op.drop_table("case_messages")

    op.drop_index("ix_case_events_event_type_ts", table_name="case_events")
    op.drop_index("ix_case_events_case_id_ts", table_name="case_events")
    op.drop_table("case_events")

    op.drop_index("ix_cases_room1_final_reply_event_id", table_name="cases")
    op.drop_index("ix_cases_status", table_name="cases")
    op.drop_index("ix_cases_agency_record_number_created_at", table_name="cases")
    op.drop_table("cases")

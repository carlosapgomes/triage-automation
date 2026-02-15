"""SQLAlchemy metadata definitions for triage automation tables."""

from __future__ import annotations

import sqlalchemy as sa

metadata = sa.MetaData()
sqlite_bigint = sa.BigInteger().with_variant(sa.Integer(), "sqlite")

cases = sa.Table(
    "cases",
    metadata,
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

sa.Index(
    "ix_cases_agency_record_number_created_at",
    cases.c.agency_record_number,
    cases.c.created_at,
)
sa.Index("ix_cases_status", cases.c.status)
sa.Index("ix_cases_room1_final_reply_event_id", cases.c.room1_final_reply_event_id)

case_events = sa.Table(
    "case_events",
    metadata,
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

sa.Index("ix_case_events_case_id_ts", case_events.c.case_id, case_events.c.ts)
sa.Index("ix_case_events_event_type_ts", case_events.c.event_type, case_events.c.ts)

case_messages = sa.Table(
    "case_messages",
    metadata,
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

sa.Index("ix_case_messages_case_id", case_messages.c.case_id)
sa.Index("ix_case_messages_kind", case_messages.c.kind)

jobs = sa.Table(
    "jobs",
    metadata,
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

sa.Index("ix_jobs_status_run_after", jobs.c.status, jobs.c.run_after)
sa.Index("ix_jobs_case_id", jobs.c.case_id)

prompt_templates = sa.Table(
    "prompt_templates",
    metadata,
    sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
    sa.Column("name", sa.Text(), nullable=False),
    sa.Column("version", sa.Integer(), nullable=False),
    sa.Column("content", sa.Text(), nullable=False),
    sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
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
    sa.Column("updated_by_user_id", sa.Uuid(), nullable=True),
    sa.UniqueConstraint("name", "version", name="uq_prompt_templates_name_version"),
    sa.CheckConstraint("version > 0", name="ck_prompt_templates_version_positive"),
)

sa.Index("ix_prompt_templates_name", prompt_templates.c.name)
sa.Index(
    "ux_prompt_templates_name_active_true",
    prompt_templates.c.name,
    unique=True,
    sqlite_where=sa.text("is_active = 1"),
    postgresql_where=sa.text("is_active = true"),
)

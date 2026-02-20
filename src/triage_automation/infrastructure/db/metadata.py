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

case_reaction_checkpoints = sa.Table(
    "case_reaction_checkpoints",
    metadata,
    sa.Column("id", sqlite_bigint, primary_key=True, autoincrement=True),
    sa.Column("case_id", sa.Uuid(), sa.ForeignKey("cases.case_id"), nullable=False),
    sa.Column("stage", sa.Text(), nullable=False),
    sa.Column("room_id", sa.Text(), nullable=False),
    sa.Column("target_event_id", sa.Text(), nullable=False),
    sa.Column(
        "expected_at",
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.text("CURRENT_TIMESTAMP"),
    ),
    sa.Column("outcome", sa.Text(), nullable=False, server_default=sa.text("'PENDING'")),
    sa.Column("reaction_event_id", sa.Text(), nullable=True),
    sa.Column("reactor_user_id", sa.Text(), nullable=True),
    sa.Column("reactor_display_name", sa.Text(), nullable=True),
    sa.Column("reaction_key", sa.Text(), nullable=True),
    sa.Column("reacted_at", sa.DateTime(timezone=True), nullable=True),
    sa.CheckConstraint(
        "stage IN ('ROOM2_ACK', 'ROOM3_ACK', 'ROOM1_FINAL')",
        name="ck_case_reaction_checkpoints_stage",
    ),
    sa.CheckConstraint(
        "outcome IN ('PENDING', 'POSITIVE_RECEIVED')",
        name="ck_case_reaction_checkpoints_outcome",
    ),
    sa.UniqueConstraint(
        "room_id",
        "target_event_id",
        name="uq_case_reaction_checkpoints_room_target_event",
    ),
)
sa.Index(
    "ix_case_reaction_checkpoints_case_id_expected_at",
    case_reaction_checkpoints.c.case_id,
    case_reaction_checkpoints.c.expected_at,
)
sa.Index(
    "ix_case_reaction_checkpoints_stage_outcome",
    case_reaction_checkpoints.c.stage,
    case_reaction_checkpoints.c.outcome,
)

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

users = sa.Table(
    "users",
    metadata,
    sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
    sa.Column("email", sa.Text(), nullable=False),
    sa.Column("password_hash", sa.Text(), nullable=False),
    sa.Column("role", sa.Text(), nullable=False),
    sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
    sa.Column(
        "account_status",
        sa.Text(),
        nullable=False,
        server_default=sa.text("'active'"),
    ),
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
    sa.UniqueConstraint("email", name="uq_users_email"),
    sa.CheckConstraint("role IN ('admin', 'reader')", name="ck_users_role"),
    sa.CheckConstraint(
        "account_status IN ('active', 'blocked', 'removed')",
        name="ck_users_account_status",
    ),
)
sa.Index("ix_users_email", users.c.email)

auth_events = sa.Table(
    "auth_events",
    metadata,
    sa.Column("id", sqlite_bigint, primary_key=True, autoincrement=True),
    sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=True),
    sa.Column("event_type", sa.Text(), nullable=False),
    sa.Column("ip_address", sa.Text(), nullable=True),
    sa.Column("user_agent", sa.Text(), nullable=True),
    sa.Column("payload", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
    sa.Column(
        "occurred_at",
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.text("CURRENT_TIMESTAMP"),
    ),
)
sa.Index("ix_auth_events_user_id_occurred_at", auth_events.c.user_id, auth_events.c.occurred_at)
sa.Index(
    "ix_auth_events_event_type_occurred_at",
    auth_events.c.event_type,
    auth_events.c.occurred_at,
)

auth_tokens = sa.Table(
    "auth_tokens",
    metadata,
    sa.Column("id", sqlite_bigint, primary_key=True, autoincrement=True),
    sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
    sa.Column("token_hash", sa.Text(), nullable=False),
    sa.Column(
        "issued_at",
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.text("CURRENT_TIMESTAMP"),
    ),
    sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
    sa.UniqueConstraint("token_hash", name="uq_auth_tokens_token_hash"),
)
sa.Index("ix_auth_tokens_user_id", auth_tokens.c.user_id)
sa.Index("ix_auth_tokens_expires_at", auth_tokens.c.expires_at)

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
    sa.Column("updated_by_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=True),
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

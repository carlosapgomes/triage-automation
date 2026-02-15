"""Add prompt_templates with versioning and single-active constraints."""

from __future__ import annotations

from uuid import UUID

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "0002_prompt_templates"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "prompt_templates",
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

    op.create_index("ix_prompt_templates_name", "prompt_templates", ["name"], unique=False)
    op.create_index(
        "ux_prompt_templates_name_active_true",
        "prompt_templates",
        ["name"],
        unique=True,
        sqlite_where=sa.text("is_active = 1"),
        postgresql_where=sa.text("is_active = true"),
    )

    prompt_templates = sa.table(
        "prompt_templates",
        sa.column("id", sa.Uuid()),
        sa.column("name", sa.Text()),
        sa.column("version", sa.Integer()),
        sa.column("content", sa.Text()),
        sa.column("is_active", sa.Boolean()),
    )
    op.bulk_insert(
        prompt_templates,
        [
            {
                "id": UUID("11111111-1111-1111-1111-111111111111"),
                "name": "llm1_system",
                "version": 1,
                "content": "DEFAULT LLM1 SYSTEM PROMPT v1",
                "is_active": True,
            },
            {
                "id": UUID("11111111-1111-1111-1111-111111111112"),
                "name": "llm1_user",
                "version": 1,
                "content": "DEFAULT LLM1 USER PROMPT v1",
                "is_active": True,
            },
            {
                "id": UUID("11111111-1111-1111-1111-111111111113"),
                "name": "llm2_system",
                "version": 1,
                "content": "DEFAULT LLM2 SYSTEM PROMPT v1",
                "is_active": True,
            },
            {
                "id": UUID("11111111-1111-1111-1111-111111111114"),
                "name": "llm2_user",
                "version": 1,
                "content": "DEFAULT LLM2 USER PROMPT v1",
                "is_active": True,
            },
        ],
    )


def downgrade() -> None:
    op.drop_index("ux_prompt_templates_name_active_true", table_name="prompt_templates")
    op.drop_index("ix_prompt_templates_name", table_name="prompt_templates")
    op.drop_table("prompt_templates")

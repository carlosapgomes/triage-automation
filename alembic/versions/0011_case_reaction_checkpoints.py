"""Add stateful reaction checkpoints per case and room target event."""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "0011_case_reaction_checkpoints"
down_revision = "0010_transcript_tables_append_only"
branch_labels = None
depends_on = None

sqlite_bigint = sa.BigInteger().with_variant(sa.Integer(), "sqlite")


def upgrade() -> None:
    """Create reaction checkpoint table used by dashboard reaction timeline."""

    op.create_table(
        "case_reaction_checkpoints",
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
    op.create_index(
        "ix_case_reaction_checkpoints_case_id_expected_at",
        "case_reaction_checkpoints",
        ["case_id", "expected_at"],
        unique=False,
    )
    op.create_index(
        "ix_case_reaction_checkpoints_stage_outcome",
        "case_reaction_checkpoints",
        ["stage", "outcome"],
        unique=False,
    )


def downgrade() -> None:
    """Drop reaction checkpoint table and indexes."""

    op.drop_index(
        "ix_case_reaction_checkpoints_stage_outcome",
        table_name="case_reaction_checkpoints",
    )
    op.drop_index(
        "ix_case_reaction_checkpoints_case_id_expected_at",
        table_name="case_reaction_checkpoints",
    )
    op.drop_table("case_reaction_checkpoints")

"""Add case and chronological indexes for transcript tables."""

from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision = "0009_transcript_case_chronological_indexes"
down_revision = "0008_case_matrix_message_transcripts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_case_report_transcripts_case_id_captured_at",
        "case_report_transcripts",
        ["case_id", "captured_at"],
        unique=False,
    )
    op.create_index(
        "ix_case_llm_interactions_case_id_captured_at",
        "case_llm_interactions",
        ["case_id", "captured_at"],
        unique=False,
    )
    op.create_index(
        "ix_case_matrix_message_transcripts_case_id_captured_at",
        "case_matrix_message_transcripts",
        ["case_id", "captured_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_case_matrix_message_transcripts_case_id_captured_at",
        table_name="case_matrix_message_transcripts",
    )
    op.drop_index(
        "ix_case_llm_interactions_case_id_captured_at",
        table_name="case_llm_interactions",
    )
    op.drop_index(
        "ix_case_report_transcripts_case_id_captured_at",
        table_name="case_report_transcripts",
    )

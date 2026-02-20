"""Add explicit user account status lifecycle with is_active compatibility."""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0013_user_account_status"
down_revision = "0012_actor_display_names"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add account_status and map legacy user rows from is_active."""

    op.add_column(
        "users",
        sa.Column(
            "account_status",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'active'"),
        ),
    )
    op.execute(
        sa.text(
            "UPDATE users "
            "SET account_status = 'blocked' "
            "WHERE is_active IS FALSE"
        )
    )
    with op.batch_alter_table("users") as batch_op:
        batch_op.create_check_constraint(
            "ck_users_account_status",
            "account_status IN ('active', 'blocked', 'removed')",
        )


def downgrade() -> None:
    """Remove account_status lifecycle column and related constraint."""

    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_constraint("ck_users_account_status", type_="check")
        batch_op.drop_column("account_status")

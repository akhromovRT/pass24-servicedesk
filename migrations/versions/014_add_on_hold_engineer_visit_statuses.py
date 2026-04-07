"""Add on_hold and engineer_visit statuses to ticketstatus enum,
add comment_id column to attachments table.

Revision ID: 014
Revises: 013
Create Date: 2026-04-07

NOTE: PostgreSQL ALTER TYPE ... ADD VALUE cannot run inside a transaction.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "014"
down_revision: Union[str, None] = "013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # PostgreSQL enum extension — must run outside transaction
    op.execute("ALTER TYPE ticketstatus ADD VALUE IF NOT EXISTS 'on_hold'")
    op.execute("ALTER TYPE ticketstatus ADD VALUE IF NOT EXISTS 'engineer_visit'")

    # Inline attachments: link attachment to specific comment
    op.add_column(
        "attachments",
        sa.Column("comment_id", sa.String(), nullable=True),
    )
    op.create_index("ix_attachments_comment_id", "attachments", ["comment_id"])


def downgrade() -> None:
    op.drop_index("ix_attachments_comment_id", table_name="attachments")
    op.drop_column("attachments", "comment_id")
    # PostgreSQL enum values cannot be removed — manual intervention needed

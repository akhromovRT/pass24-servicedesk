"""Add has_unread_reply flag for staff notifications.

Revision ID: 004
Revises: 003
Create Date: 2026-04-05

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "tickets",
        sa.Column("has_unread_reply", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.create_index("ix_tickets_has_unread_reply", "tickets", ["has_unread_reply"])


def downgrade() -> None:
    op.drop_index("ix_tickets_has_unread_reply", table_name="tickets")
    op.drop_column("tickets", "has_unread_reply")

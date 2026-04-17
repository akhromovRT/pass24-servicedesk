"""Add sla_paused_by_status / sla_paused_by_reply flags.

Revision ID: 021
Revises: 020
Create Date: 2026-04-17
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "021"
down_revision: Union[str, None] = "020"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "tickets",
        sa.Column("sla_paused_by_status", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.add_column(
        "tickets",
        sa.Column("sla_paused_by_reply", sa.Boolean(), nullable=False, server_default="false"),
    )
    # Backfill: статус-флаг derive-им из текущего статуса. Reply-флаг оставляем
    # false — не ретроактивно применяем новую паузу к исторической переписке.
    op.execute(
        "UPDATE tickets "
        "SET sla_paused_by_status = TRUE "
        "WHERE status IN ('waiting_for_user', 'on_hold')"
    )


def downgrade() -> None:
    op.drop_column("tickets", "sla_paused_by_reply")
    op.drop_column("tickets", "sla_paused_by_status")

"""Telegram bot v2 — FSM storage, link tokens, user telegram fields.

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
    # --- telegram_fsm_state: aiogram FSM persistence ---
    op.create_table(
        "telegram_fsm_state",
        sa.Column("key", sa.String(), primary_key=True),
        sa.Column("state", sa.String(), nullable=True),
        sa.Column(
            "data",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'{}'::json"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_telegram_fsm_state_updated_at",
        "telegram_fsm_state",
        ["updated_at"],
    )

    # --- telegram_link_tokens: one-time tokens for account linking ---
    op.create_table(
        "telegram_link_tokens",
        sa.Column("token", sa.String(length=64), primary_key=True),
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("used_at", sa.DateTime(), nullable=True),
    )
    op.create_index(
        "ix_telegram_link_tokens_user_id",
        "telegram_link_tokens",
        ["user_id"],
    )

    # --- users: telegram linking metadata ---
    op.add_column(
        "users",
        sa.Column("telegram_linked_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column(
            "telegram_preferences",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'{}'::json"),
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "telegram_preferences")
    op.drop_column("users", "telegram_linked_at")
    op.drop_index("ix_telegram_link_tokens_user_id", table_name="telegram_link_tokens")
    op.drop_table("telegram_link_tokens")
    op.drop_index("ix_telegram_fsm_state_updated_at", table_name="telegram_fsm_state")
    op.drop_table("telegram_fsm_state")

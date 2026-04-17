"""Add ticket_comments.email_message_id + partial unique index.

Идемпотентность inbound-обработки: Message-ID письма сохраняется рядом с
комментарием, уникальный индекс по ненулевым значениям не даёт создать
второй комментарий из того же письма после рестарта воркера, очистки
in-memory кеша или повторного прохода IMAP SINCE-окна.

Revision ID: 022
Revises: 021
Create Date: 2026-04-17
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "022"
down_revision: Union[str, None] = "021"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "ticket_comments",
        sa.Column("email_message_id", sa.String(length=998), nullable=True),
    )
    op.create_index(
        "uq_ticket_comments_email_message_id",
        "ticket_comments",
        ["email_message_id"],
        unique=True,
        postgresql_where=sa.text("email_message_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_ticket_comments_email_message_id", table_name="ticket_comments")
    op.drop_column("ticket_comments", "email_message_id")

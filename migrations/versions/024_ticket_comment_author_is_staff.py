"""Denormalize author role onto ticket_comments for last-reply indicator.

Revision ID: 024
Revises: 023
Create Date: 2026-04-20

Добавляет bool-колонку `author_is_staff` в ticket_comments, чтобы UI-индикатор
«кто ответил последним» работал без JOIN к users. Backfill проставляет TRUE
для комментариев, авторы которых в users имеют роль support_agent или admin.
Комментарии из email/telegram остаются FALSE (клиентские).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "024"
down_revision: Union[str, None] = "023"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "ticket_comments",
        sa.Column("author_is_staff", sa.Boolean(), nullable=False, server_default="false"),
    )
    # Backfill: authors, которые есть в users с ролью support_agent/admin.
    # - author_id в ticket_comments — строка, users.id — UUID → ::text cast.
    # - users.role — Postgres enum userrole → ::text cast, иначе asyncpg кидает
    #   InvalidTextRepresentationError на bare string literal.
    op.execute(
        """
        UPDATE ticket_comments tc
        SET author_is_staff = TRUE
        FROM users u
        WHERE u.id::text = tc.author_id
          AND u.role::text IN ('support_agent', 'admin')
        """
    )


def downgrade() -> None:
    op.drop_column("ticket_comments", "author_is_staff")

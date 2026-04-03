"""Add FTS to articles and stats view for analytics.

Revision ID: 002
Revises: 001
Create Date: 2026-04-03

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- FTS для articles ---
    op.add_column("articles", sa.Column("search_vector", sa.Text(), nullable=True))

    # Заполняем search_vector для существующих записей
    op.execute("""
        UPDATE articles
        SET search_vector = title || ' ' || content
    """)

    # GIN-индекс для полнотекстового поиска
    op.execute("""
        CREATE INDEX ix_articles_fts
        ON articles
        USING GIN (to_tsvector('russian', coalesce(title, '') || ' ' || coalesce(content, '')))
    """)

    # --- Индексы для фильтрации тикетов ---
    op.create_index("ix_tickets_object_id", "tickets", ["object_id"])
    op.create_index("ix_tickets_status", "tickets", ["status"])
    op.create_index("ix_tickets_category", "tickets", ["category"])


def downgrade() -> None:
    op.drop_index("ix_tickets_category", table_name="tickets")
    op.drop_index("ix_tickets_status", table_name="tickets")
    op.drop_index("ix_tickets_object_id", table_name="tickets")
    op.execute("DROP INDEX IF EXISTS ix_articles_fts")
    op.drop_column("articles", "search_vector")

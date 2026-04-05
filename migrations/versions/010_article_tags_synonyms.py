"""Add tags, synonyms, slug_aliases to articles + enhanced tsvector.

Revision ID: 010
Revises: 009
Create Date: 2026-04-06

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "010"
down_revision: Union[str, None] = "009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Теги: ["sms", "registration", "password"] — для фильтров и FTS boost
    op.add_column(
        "articles",
        sa.Column(
            "tags",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    # Синонимы: альтернативные формулировки от лица клиента
    # ["смс не приходит", "нет кода", "код не пришёл"]
    op.add_column(
        "articles",
        sa.Column(
            "synonyms",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    # slug_aliases: старые slug для 301 redirect после декомпозиции статей
    op.add_column(
        "articles",
        sa.Column(
            "slug_aliases",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )

    # GIN индекс по tags для быстрого фильтра ?tag=sms
    op.create_index(
        "ix_articles_tags_gin",
        "articles",
        ["tags"],
        postgresql_using="gin",
    )
    # GIN индекс по slug_aliases для redirect lookup
    op.create_index(
        "ix_articles_slug_aliases_gin",
        "articles",
        ["slug_aliases"],
        postgresql_using="gin",
    )


def downgrade() -> None:
    op.drop_index("ix_articles_slug_aliases_gin", table_name="articles")
    op.drop_index("ix_articles_tags_gin", table_name="articles")
    op.drop_column("articles", "slug_aliases")
    op.drop_column("articles", "synonyms")
    op.drop_column("articles", "tags")

"""Add article_feedback table + helpful counters on articles.

Revision ID: 009
Revises: 008
Create Date: 2026-04-06

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel

revision: str = "009"
down_revision: Union[str, None] = "008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Feedback по статьям БЗ: помогла/не помогла + опциональный комментарий
    op.create_table(
        "article_feedback",
        sa.Column("id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("article_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("session_id", sqlmodel.sql.sqltypes.AutoString(length=64), nullable=False),
        sa.Column("user_id", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("helpful", sa.Boolean(), nullable=False),
        sa.Column("comment", sqlmodel.sql.sqltypes.AutoString(length=500), nullable=True),
        sa.Column("source", sqlmodel.sql.sqltypes.AutoString(length=16), nullable=False, server_default="web"),
        # web / email / telegram
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_article_feedback_article_id", "article_feedback", ["article_id"])
    op.create_index("ix_article_feedback_created_at", "article_feedback", ["created_at"])
    # Один session не может оставить несколько feedback на одну статью
    op.create_index(
        "ix_article_feedback_session_article",
        "article_feedback",
        ["session_id", "article_id"],
        unique=True,
    )

    # Денормализованные счётчики на articles (для быстрого отображения)
    op.add_column(
        "articles",
        sa.Column("helpful_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "articles",
        sa.Column("not_helpful_count", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("articles", "not_helpful_count")
    op.drop_column("articles", "helpful_count")
    op.drop_index("ix_article_feedback_session_article", table_name="article_feedback")
    op.drop_index("ix_article_feedback_created_at", table_name="article_feedback")
    op.drop_index("ix_article_feedback_article_id", table_name="article_feedback")
    op.drop_table("article_feedback")

"""Add saved_views, ticket_article_links, parent_ticket_id.

Revision ID: 007
Revises: 006
Create Date: 2026-04-05

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "007"
down_revision: Union[str, None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Saved views — персональные фильтры
    op.create_table(
        "saved_views",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("icon", sa.String(length=64), nullable=True),
        sa.Column("filters", sa.String(), nullable=False),
        sa.Column("owner_id", sa.String(), nullable=False),
        sa.Column("is_shared", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("usage_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_saved_views_owner_id", "saved_views", ["owner_id"])

    # M2M: тикет → статья БЗ
    op.create_table(
        "ticket_article_links",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("ticket_id", sa.String(), nullable=False),
        sa.Column("article_id", sa.String(), nullable=False),
        sa.Column("relation_type", sa.String(length=32), nullable=False, server_default="helped"),
        sa.Column("linked_by", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["ticket_id"], ["tickets.id"]),
    )
    op.create_index("ix_ticket_article_links_ticket_id", "ticket_article_links", ["ticket_id"])
    op.create_index("ix_ticket_article_links_article_id", "ticket_article_links", ["article_id"])

    # Parent ticket для Incident → Problem
    op.add_column("tickets", sa.Column("parent_ticket_id", sa.String(), nullable=True))
    op.create_index("ix_tickets_parent_ticket_id", "tickets", ["parent_ticket_id"])


def downgrade() -> None:
    op.drop_index("ix_tickets_parent_ticket_id", table_name="tickets")
    op.drop_column("tickets", "parent_ticket_id")
    op.drop_index("ix_ticket_article_links_article_id", table_name="ticket_article_links")
    op.drop_index("ix_ticket_article_links_ticket_id", table_name="ticket_article_links")
    op.drop_table("ticket_article_links")
    op.drop_index("ix_saved_views_owner_id", table_name="saved_views")
    op.drop_table("saved_views")

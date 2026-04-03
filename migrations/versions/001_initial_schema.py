"""Initial schema — baseline migration.

Описывает существующую схему БД, созданную через SQLModel.metadata.create_all.
На продакшен-БД применяется через `alembic stamp head` (без выполнения DDL).

Revision ID: 001
Revises: None
Create Date: 2026-04-03

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- users ---
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("email", sqlmodel.sql.sqltypes.AutoString(length=320), nullable=False),
        sa.Column("hashed_password", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("full_name", sqlmodel.sql.sqltypes.AutoString(length=256), nullable=False),
        sa.Column("role", sa.VARCHAR(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)

    # --- tickets ---
    op.create_table(
        "tickets",
        sa.Column("id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("creator_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("title", sqlmodel.sql.sqltypes.AutoString(length=200), nullable=False),
        sa.Column("description", sqlmodel.sql.sqltypes.AutoString(length=4000), nullable=False),
        sa.Column("category", sqlmodel.sql.sqltypes.AutoString(length=64), nullable=False),
        sa.Column("status", sa.VARCHAR(), nullable=False),
        sa.Column("priority", sa.VARCHAR(), nullable=False),
        sa.Column("object_id", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("access_point_id", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("user_role", sqlmodel.sql.sqltypes.AutoString(length=64), nullable=True),
        sa.Column("occurred_at", sqlmodel.sql.sqltypes.AutoString(length=128), nullable=True),
        sa.Column("contact", sqlmodel.sql.sqltypes.AutoString(length=128), nullable=True),
        sa.Column("urgent", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_tickets_creator_id"), "tickets", ["creator_id"])

    # --- ticket_events ---
    op.create_table(
        "ticket_events",
        sa.Column("id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("ticket_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("actor_id", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("description", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["ticket_id"], ["tickets.id"]),
    )
    op.create_index(op.f("ix_ticket_events_ticket_id"), "ticket_events", ["ticket_id"])

    # --- ticket_comments ---
    op.create_table(
        "ticket_comments",
        sa.Column("id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("ticket_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("author_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("author_name", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("text", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["ticket_id"], ["tickets.id"]),
    )
    op.create_index(op.f("ix_ticket_comments_ticket_id"), "ticket_comments", ["ticket_id"])

    # --- articles ---
    op.create_table(
        "articles",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("title", sqlmodel.sql.sqltypes.AutoString(length=512), nullable=False),
        sa.Column("slug", sqlmodel.sql.sqltypes.AutoString(length=512), nullable=False),
        sa.Column("category", sa.String(), nullable=True),
        sa.Column("content", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("is_published", sa.Boolean(), nullable=False),
        sa.Column("views_count", sa.Integer(), nullable=False),
        sa.Column("author_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["author_id"], ["users.id"]),
    )
    op.create_index(op.f("ix_articles_title"), "articles", ["title"])
    op.create_index(op.f("ix_articles_slug"), "articles", ["slug"], unique=True)
    op.create_index(op.f("ix_articles_is_published"), "articles", ["is_published"])
    op.create_index("ix_articles_category_published", "articles", ["category", "is_published"])


def downgrade() -> None:
    op.drop_table("articles")
    op.drop_table("ticket_comments")
    op.drop_table("ticket_events")
    op.drop_table("tickets")
    op.drop_table("users")

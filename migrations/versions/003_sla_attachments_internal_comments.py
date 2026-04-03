"""Add SLA fields, attachments table, internal comments flag.

Revision ID: 003
Revises: 002
Create Date: 2026-04-03

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- SLA-поля в tickets ---
    op.add_column("tickets", sa.Column("first_response_at", sa.DateTime(), nullable=True))
    op.add_column("tickets", sa.Column("resolved_at", sa.DateTime(), nullable=True))
    op.add_column("tickets", sa.Column("sla_response_hours", sa.Integer(), nullable=True, server_default="4"))
    op.add_column("tickets", sa.Column("sla_resolve_hours", sa.Integer(), nullable=True, server_default="24"))

    # --- Внутренние комментарии ---
    op.add_column("ticket_comments", sa.Column("is_internal", sa.Boolean(), nullable=False, server_default="false"))

    # --- Таблица вложений ---
    op.create_table(
        "attachments",
        sa.Column("id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("ticket_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("uploader_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("filename", sqlmodel.sql.sqltypes.AutoString(length=512), nullable=False),
        sa.Column("content_type", sqlmodel.sql.sqltypes.AutoString(length=128), nullable=False),
        sa.Column("size", sa.Integer(), nullable=False),
        sa.Column("storage_path", sqlmodel.sql.sqltypes.AutoString(length=1024), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["ticket_id"], ["tickets.id"]),
    )
    op.create_index("ix_attachments_ticket_id", "attachments", ["ticket_id"])


def downgrade() -> None:
    op.drop_table("attachments")
    op.drop_column("ticket_comments", "is_internal")
    op.drop_column("tickets", "sla_resolve_hours")
    op.drop_column("tickets", "sla_response_hours")
    op.drop_column("tickets", "resolved_at")
    op.drop_column("tickets", "first_response_at")

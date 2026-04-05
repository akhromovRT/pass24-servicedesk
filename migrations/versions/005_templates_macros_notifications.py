"""Add response_templates, macros, sla_notifications tables.

Revision ID: 005
Revises: 004
Create Date: 2026-04-05

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel

revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # response_templates: шаблоны ответов агентов
    op.create_table(
        "response_templates",
        sa.Column("id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("name", sqlmodel.sql.sqltypes.AutoString(length=256), nullable=False),
        sa.Column("body", sqlmodel.sql.sqltypes.AutoString(length=4000), nullable=False),
        sa.Column("category", sqlmodel.sql.sqltypes.AutoString(length=64), nullable=True),
        sa.Column("author_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("is_shared", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("usage_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_response_templates_author_id", "response_templates", ["author_id"])

    # macros: предустановленные комбинации действий
    op.create_table(
        "macros",
        sa.Column("id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("name", sqlmodel.sql.sqltypes.AutoString(length=256), nullable=False),
        sa.Column("icon", sqlmodel.sql.sqltypes.AutoString(length=64), nullable=True),
        # JSON-описание действий: { "status": "in_progress", "comment": "...", "assign_self": true, ... }
        sa.Column("actions", sa.Text(), nullable=False),
        sa.Column("author_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("is_shared", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # sla_breach_notified: чтобы не слать уведомление о SLA повторно
    op.add_column(
        "tickets",
        sa.Column("sla_breach_warned", sa.Boolean(), nullable=False, server_default="false"),
    )

    # merged_into: для дубликатов
    op.add_column(
        "tickets",
        sa.Column("merged_into_ticket_id", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    )
    op.create_index("ix_tickets_merged_into", "tickets", ["merged_into_ticket_id"])


def downgrade() -> None:
    op.drop_index("ix_tickets_merged_into", table_name="tickets")
    op.drop_column("tickets", "merged_into_ticket_id")
    op.drop_column("tickets", "sla_breach_warned")
    op.drop_table("macros")
    op.drop_index("ix_response_templates_author_id", table_name="response_templates")
    op.drop_table("response_templates")

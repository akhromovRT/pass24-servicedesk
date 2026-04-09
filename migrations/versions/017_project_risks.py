"""Add project_risks table for risk management.

Revision ID: 017
Revises: 016
Create Date: 2026-04-09
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "017"
down_revision: Union[str, None] = "016"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "project_risks",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("project_id", sa.String(), sa.ForeignKey("implementation_projects.id"), nullable=False, index=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.String(4000), nullable=True),
        sa.Column("severity", sa.String(), nullable=False, server_default="medium", index=True),
        sa.Column("probability", sa.String(), nullable=False, server_default="medium"),
        sa.Column("impact", sa.String(), nullable=False, server_default="medium"),
        sa.Column("mitigation_plan", sa.String(4000), nullable=True),
        sa.Column("owner_id", sa.String(), nullable=True, index=True),
        sa.Column("status", sa.String(), nullable=False, server_default="open", index=True),
        sa.Column("created_by", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("project_risks")

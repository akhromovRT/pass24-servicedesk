"""Add kb_improvement_suggestions table.

Revision ID: 008
Revises: 007
Create Date: 2026-04-05

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel

revision: str = "008"
down_revision: Union[str, None] = "007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "kb_improvement_suggestions",
        sa.Column("id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("article_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("ticket_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("suggestion", sqlmodel.sql.sqltypes.AutoString(length=4000), nullable=False),
        sa.Column("suggested_by", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("status", sqlmodel.sql.sqltypes.AutoString(length=32), nullable=False, server_default="pending"),
        # pending / applied / rejected
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_kb_improvement_suggestions_article_id", "kb_improvement_suggestions", ["article_id"])
    op.create_index("ix_kb_improvement_suggestions_status", "kb_improvement_suggestions", ["status"])


def downgrade() -> None:
    op.drop_index("ix_kb_improvement_suggestions_status", table_name="kb_improvement_suggestions")
    op.drop_index("ix_kb_improvement_suggestions_article_id", table_name="kb_improvement_suggestions")
    op.drop_table("kb_improvement_suggestions")

"""Add customers table (Bitrix24 companies sync by INN).

Revision ID: 012
Revises: 011
Create Date: 2026-04-06

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel

revision: str = "012"
down_revision: Union[str, None] = "011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "customers",
        sa.Column("id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("inn", sqlmodel.sql.sqltypes.AutoString(length=20), nullable=False),
        sa.Column("name", sqlmodel.sql.sqltypes.AutoString(length=512), nullable=False),
        sa.Column("bitrix24_company_id", sa.Integer(), nullable=True),
        sa.Column("address", sqlmodel.sql.sqltypes.AutoString(length=1024), nullable=True),
        sa.Column("phone", sqlmodel.sql.sqltypes.AutoString(length=64), nullable=True),
        sa.Column("email", sqlmodel.sql.sqltypes.AutoString(length=320), nullable=True),
        sa.Column("industry", sqlmodel.sql.sqltypes.AutoString(length=128), nullable=True),
        sa.Column("comment", sqlmodel.sql.sqltypes.AutoString(length=2000), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("synced_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_customers_inn", "customers", ["inn"], unique=True)
    op.create_index("ix_customers_bitrix24_company_id", "customers", ["bitrix24_company_id"])

    # Добавляем customer_id в users (контакт привязан к компании)
    op.add_column("users", sa.Column("customer_id", sqlmodel.sql.sqltypes.AutoString(), nullable=True))
    op.create_index("ix_users_customer_id", "users", ["customer_id"])

    # Добавляем customer_id в tickets (тикет привязан к компании)
    op.add_column("tickets", sa.Column("customer_id", sqlmodel.sql.sqltypes.AutoString(), nullable=True))
    op.create_index("ix_tickets_customer_id", "tickets", ["customer_id"])


def downgrade() -> None:
    op.drop_index("ix_tickets_customer_id", table_name="tickets")
    op.drop_column("tickets", "customer_id")
    op.drop_index("ix_users_customer_id", table_name="users")
    op.drop_column("users", "customer_id")
    op.drop_index("ix_customers_bitrix24_company_id", table_name="customers")
    op.drop_index("ix_customers_inn", table_name="customers")
    op.drop_table("customers")

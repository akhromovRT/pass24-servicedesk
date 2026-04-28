"""Add customers.subdomain + partial unique index.

Поддомен сайта клиента в зоне pass24online.ru для авто-связывания
guest-тикетов из embed AI-виджета с компанией. Embed-виджет шлёт
window.location.hostname в payload /tickets/guest, бэкенд извлекает первый
label (bristol.pass24online.ru → "bristol") и матчит против
customers.subdomain. Найден → ticket.customer_id / company / object_name
заполняются автоматически.

Уникальность через частичный unique-индекс (паттерн как у миграции 026
для tickets.email_message_id): NULL'ы не блокируются, а одинаковый
непустой subdomain у двух разных клиентов запрещён.

Revision ID: 027
Revises: 026
Create Date: 2026-04-28
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "027"
down_revision: Union[str, None] = "026"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "customers",
        sa.Column("subdomain", sa.String(length=64), nullable=True),
    )
    op.create_index(
        "uq_customers_subdomain",
        "customers",
        ["subdomain"],
        unique=True,
        postgresql_where=sa.text("subdomain IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_customers_subdomain", table_name="customers")
    op.drop_column("customers", "subdomain")

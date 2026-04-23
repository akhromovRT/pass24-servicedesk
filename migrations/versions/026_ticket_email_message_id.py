"""Add tickets.email_message_id + partial unique index.

Идемпотентность inbound-email-обработки для новых тикетов: до этой миграции
защита от дублей для _handle_new_ticket держалась на pre-insert SELECT по
(title, contact_email, source='email') в отдельной сессии — классический
TOCTOU, который ломался по двум причинам:

1. Рассогласование нормализации title: SELECT сравнивал c subject[:200]
   без strip, а сохранялось title = subject.strip() (или fallback на body),
   поэтому лишние пробелы/пустой subject обходили проверку.
2. Отсутствие ограничения на уровне БД: две параллельные транзакции
   (например, старый и новый контейнер во время `docker compose up -d`)
   могли одновременно пройти SELECT и обе вставить дубль.

Паттерн копирует миграцию 022 (ticket_comments.email_message_id):
Message-ID → колонка + уникальный частичный индекс по ненулевым значениям.
После накатывания INSERT новых тикетов из email обёрнут в try/IntegrityError
и откатывает транзакцию на повторном письме.

Revision ID: 026
Revises: 025
Create Date: 2026-04-22
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "026"
down_revision: Union[str, None] = "025"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "tickets",
        sa.Column("email_message_id", sa.String(length=998), nullable=True),
    )
    op.create_index(
        "uq_tickets_email_message_id",
        "tickets",
        ["email_message_id"],
        unique=True,
        postgresql_where=sa.text("email_message_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_tickets_email_message_id", table_name="tickets")
    op.drop_column("tickets", "email_message_id")

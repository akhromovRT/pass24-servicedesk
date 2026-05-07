"""Add tickets.number — короткий последовательный ID для UI и email.

UUID `id` остаётся первичным ключом и стабильным внутренним идентификатором
(используется в URL фронта, FK с комментариями, событиями, вложениями).
`number` — пользовательский номер (1, 2, 3, ...) для отображения в UI и
email-тегах `[PASS24-{number}]`.

Бэкфилл: существующим тикетам присваиваются номера в порядке `created_at, id`.

Revision ID: 029
Revises: 028
Create Date: 2026-05-07
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "029"
down_revision: Union[str, None] = "028"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Добавляем колонку nullable, чтобы заполнить существующие строки.
    op.add_column(
        "tickets",
        sa.Column("number", sa.BigInteger(), nullable=True),
    )

    # 2. Бэкфилл: нумеруем существующие тикеты в порядке created_at.
    #    ROW_NUMBER() OVER гарантирует детерминированный порядок и уникальность.
    op.execute(
        """
        WITH ordered AS (
            SELECT id,
                   ROW_NUMBER() OVER (ORDER BY created_at, id) AS rn
            FROM tickets
        )
        UPDATE tickets t
        SET number = ordered.rn
        FROM ordered
        WHERE t.id = ordered.id
        """
    )

    # 3. NOT NULL + UNIQUE.
    op.alter_column("tickets", "number", nullable=False)
    op.create_unique_constraint("uq_tickets_number", "tickets", ["number"])

    # 4. Sequence для авто-генерации новых номеров (старт = max(number)+1).
    #    Используем PostgreSQL SEQUENCE как DEFAULT, чтобы новые INSERT
    #    через SQLModel/SQLAlchemy без явного указания number получали
    #    следующее значение. Это надёжнее, чем `func.max+1` race-condition.
    op.execute(
        """
        DO $$
        DECLARE
            next_val bigint;
        BEGIN
            SELECT COALESCE(MAX(number), 0) + 1 INTO next_val FROM tickets;
            EXECUTE format(
                'CREATE SEQUENCE IF NOT EXISTS tickets_number_seq START WITH %s',
                next_val
            );
        END $$;
        """
    )
    op.execute(
        "ALTER TABLE tickets ALTER COLUMN number SET DEFAULT nextval('tickets_number_seq')"
    )
    op.execute(
        "ALTER SEQUENCE tickets_number_seq OWNED BY tickets.number"
    )

    # 5. Индекс для быстрого поиска по номеру (UNIQUE constraint уже создаёт
    #    индекс, но дополнительный явный для читаемости — не нужен).


def downgrade() -> None:
    op.execute("ALTER TABLE tickets ALTER COLUMN number DROP DEFAULT")
    op.execute("DROP SEQUENCE IF EXISTS tickets_number_seq")
    op.drop_constraint("uq_tickets_number", "tickets", type_="unique")
    op.drop_column("tickets", "number")

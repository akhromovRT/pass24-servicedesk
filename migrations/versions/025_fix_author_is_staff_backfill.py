"""Fix author_is_staff backfill: match Postgres enum uppercase names.

Revision ID: 025
Revises: 024
Create Date: 2026-04-20

Миграция 024 сделала backfill, сравнивая `u.role::text` с `'support_agent'`
и `'admin'`. Но Postgres-enum `userrole` хранит значения как имена Python
Enum-членов в верхнем регистре: `SUPPORT_AGENT`, `ADMIN`, `RESIDENT`,
`PROPERTY_MANAGER`. В итоге UPDATE отработал вхолостую — 0 строк
пометилось как staff, все 144 существующих комментария остались `false`,
индикатор «кто ответил последним» для исторических данных всегда
показывал «клиент».

Эта миграция повторяет тот же backfill с правильным регистром.
downgrade() — no-op: колонку не трогаем, предыдущий state (все false) всё
равно был неправильным и не является целевым состоянием для rollback'а.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "025"
down_revision: Union[str, None] = "024"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE ticket_comments tc
        SET author_is_staff = TRUE
        FROM users u
        WHERE u.id::text = tc.author_id
          AND u.role::text IN ('SUPPORT_AGENT', 'ADMIN')
        """
    )


def downgrade() -> None:
    # Сбросить обратно в all-false — это значит «вернуться к сломанному
    # состоянию после 024». Downgrade не имеет смысла, оставляем no-op.
    pass

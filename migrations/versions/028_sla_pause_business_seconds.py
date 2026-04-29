"""Reset sla_total_pause_seconds for active tickets.

Семантика поля изменена с линейных секунд на бизнес-секунды
(только рабочее время). Накопленные ранее линейные значения
после смены кода стали бы интерпретироваться как «слишком большая»
бизнес-пауза и неоправданно сдвигали бы дедлайны вперёд.

Чистим только активные тикеты (без активной паузы), чтобы:
- не трогать данные resolved/closed (исторические, не пересчитываются);
- не сломать тикеты с активной паузой (sla_paused_at IS NOT NULL —
  при следующем recompute_sla_pause накопитель корректно обновится).

Revision ID: 028
Revises: 027
Create Date: 2026-04-29
"""
from typing import Sequence, Union

from alembic import op


revision: str = "028"
down_revision: Union[str, None] = "027"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "UPDATE tickets "
        "SET sla_total_pause_seconds = 0 "
        "WHERE sla_paused_at IS NULL "
        "  AND status NOT IN ('resolved', 'closed')"
    )


def downgrade() -> None:
    # Обратной операции нет: исходные значения не сохранялись.
    # Старая (линейная) семантика всё равно несовместима с новой кодовой базой.
    pass

"""
Массовое закрытие всех открытых тикетов БЕЗ уведомлений клиента.

Цель — очистить очередь, чтобы начать работать по списку с чистого листа.
Не использует ticket.transition() и не дёргает notify_*, поэтому email,
Telegram и WebSocket-уведомления НЕ срабатывают.

Что делает:
  1. Находит все тикеты со статусом != closed
  2. Для каждого:
     - status = 'closed'
     - updated_at = now()
     - resolved_at = now() (если было NULL)
     - satisfaction_requested_at = now() (помечаем, что CSAT не будет отправлен)
     - создаёт TicketEvent(description="Массовое закрытие — очистка очереди",
                            old_status=<прежний>, new_status='closed')
  3. Пишет итог: сколько закрыто по каждому статусу.

Запуск:
  # dry-run (по умолчанию) — только показать что будет изменено
  docker exec site-pass24-servicedesk python -m backend.scripts.bulk_close_tickets

  # реальное закрытие
  docker exec site-pass24-servicedesk python -m backend.scripts.bulk_close_tickets --apply

  # закрытие с указанием актора (user_id или email админа — пишется в TicketEvent.actor_id)
  docker exec site-pass24-servicedesk python -m backend.scripts.bulk_close_tickets \\
      --apply --actor-email admin@pass24online.ru

Безопасность:
  - Без --apply изменений в БД не происходит
  - При --apply без --actor-email актор по умолчанию = "system"
  - Closed тикеты не трогаются (идемпотентно)
  - Работает в одной транзакции; при ошибке — полный откат
"""
from __future__ import annotations

import argparse
import asyncio
import logging
from collections import Counter
from datetime import datetime

from sqlmodel import select

from backend.database import async_session_factory

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
logger = logging.getLogger("bulk_close")


async def _resolve_actor_id(actor_email: str | None) -> str:
    """Возвращает user.id по email либо 'system'."""
    if not actor_email:
        return "system"

    from backend.auth.models import User

    async with async_session_factory() as session:
        r = await session.execute(select(User).where(User.email == actor_email))
        user = r.scalar_one_or_none()
        if not user:
            logger.warning(
                "Актор с email %s не найден, использую 'system'", actor_email
            )
            return "system"
        return str(user.id)


async def bulk_close(apply: bool, actor_email: str | None) -> None:
    from backend.tickets.models import Ticket, TicketEvent, TicketStatus

    mode = "APPLY" if apply else "DRY-RUN"
    logger.info("=== Bulk close tickets (%s) ===", mode)

    actor_id = await _resolve_actor_id(actor_email)
    logger.info("Актор для аудит-события: %s", actor_id)

    closed_str = TicketStatus.CLOSED.value

    async with async_session_factory() as session:
        r = await session.execute(
            select(Ticket).where(Ticket.status != closed_str)
        )
        tickets = list(r.scalars().all())

        if not tickets:
            logger.info("Открытых тикетов не найдено — нечего закрывать.")
            return

        by_status: Counter[str] = Counter()
        for t in tickets:
            old_status = (
                t.status.value if hasattr(t.status, "value") else str(t.status)
            )
            by_status[old_status] += 1

        logger.info("Найдено открытых тикетов: %d", len(tickets))
        for status_val, count in sorted(by_status.items()):
            logger.info("  %s: %d", status_val, count)

        if not apply:
            logger.info("DRY-RUN: изменения НЕ сохраняются. Для запуска: --apply")
            return

        now = datetime.utcnow()
        for t in tickets:
            old_status = (
                t.status.value if hasattr(t.status, "value") else str(t.status)
            )

            t.status = TicketStatus.CLOSED
            t.updated_at = now
            if t.resolved_at is None:
                t.resolved_at = now
            # Помечаем, что CSAT уже был «запрошен» — это отключит будущие
            # попытки email-отправки запроса оценки при будущих операциях.
            if hasattr(t, "satisfaction_requested_at") and t.satisfaction_requested_at is None:
                t.satisfaction_requested_at = now

            # has_unread_reply = False чтоб не светилось в notifications у staff
            if hasattr(t, "has_unread_reply"):
                t.has_unread_reply = False

            session.add(t)

            event = TicketEvent(
                ticket_id=t.id,
                actor_id=actor_id,
                description=(
                    f"Массовое закрытие — очистка очереди "
                    f"({old_status} → {closed_str})"
                ),
            )
            session.add(event)

        await session.commit()
        logger.info("Закрыто %d тикетов, события аудита созданы.", len(tickets))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Массовое закрытие тикетов без уведомлений клиенту"
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Сохранить изменения в БД (иначе dry-run)",
    )
    parser.add_argument(
        "--actor-email",
        type=str,
        default=None,
        help="Email пользователя-актора для TicketEvent.actor_id (иначе 'system')",
    )
    args = parser.parse_args()
    asyncio.run(bulk_close(apply=args.apply, actor_email=args.actor_email))


if __name__ == "__main__":
    main()

"""
Бэкофилл: очистка HTML из description существующих тикетов и текстов комментариев.

Применяет _html_to_text (из notifications/inbound) к тем тикетам/комментариям,
где description/text содержит HTML-разметку (теги или entities).

Запуск:
  # dry-run (по умолчанию) — только показать что будет изменено
  docker exec site-pass24-servicedesk python -m backend.scripts.cleanup_html_bodies

  # реальное обновление
  docker exec site-pass24-servicedesk python -m backend.scripts.cleanup_html_bodies --apply
"""
from __future__ import annotations

import argparse
import asyncio
import logging

from sqlmodel import select

from backend.database import async_session_factory
from backend.notifications.inbound import _html_to_text, _looks_like_html
from backend.tickets.models import Ticket, TicketComment

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
logger = logging.getLogger(__name__)


async def cleanup(apply: bool) -> None:
    mode = "APPLY" if apply else "DRY-RUN"
    logger.info("=== HTML cleanup backfill (%s) ===", mode)

    ticket_updates = 0
    ticket_skipped = 0
    comment_updates = 0
    comment_skipped = 0

    async with async_session_factory() as session:
        # === Тикеты ===
        result = await session.execute(select(Ticket))
        tickets = result.scalars().all()
        logger.info("Найдено тикетов: %d", len(tickets))

        for ticket in tickets:
            desc = ticket.description or ""
            if not desc or not _looks_like_html(desc):
                ticket_skipped += 1
                continue

            cleaned = _html_to_text(desc)[:4000]
            if cleaned == desc:
                ticket_skipped += 1
                continue

            logger.info(
                "TICKET %s: '%s...' → '%s...'",
                ticket.id[:8],
                desc[:60].replace("\n", " "),
                cleaned[:60].replace("\n", " "),
            )
            ticket_updates += 1

            if apply:
                ticket.description = cleaned
                session.add(ticket)

        # === Комментарии ===
        result = await session.execute(select(TicketComment))
        comments = result.scalars().all()
        logger.info("Найдено комментариев: %d", len(comments))

        for comment in comments:
            text = comment.text or ""
            if not text or not _looks_like_html(text):
                comment_skipped += 1
                continue

            cleaned = _html_to_text(text)
            if cleaned == text:
                comment_skipped += 1
                continue

            logger.info(
                "COMMENT %s (ticket=%s): '%s...' → '%s...'",
                comment.id[:8],
                comment.ticket_id[:8],
                text[:60].replace("\n", " "),
                cleaned[:60].replace("\n", " "),
            )
            comment_updates += 1

            if apply:
                comment.text = cleaned
                session.add(comment)

        if apply:
            await session.commit()
            logger.info("Изменения сохранены в БД")
        else:
            logger.info("DRY-RUN: изменения НЕ сохранены (используйте --apply)")

    logger.info(
        "Итог: тикеты %d/%d, комментарии %d/%d",
        ticket_updates, ticket_updates + ticket_skipped,
        comment_updates, comment_updates + comment_skipped,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Очистка HTML в description/text")
    parser.add_argument("--apply", action="store_true", help="Сохранить изменения в БД (иначе dry-run)")
    args = parser.parse_args()
    asyncio.run(cleanup(apply=args.apply))


if __name__ == "__main__":
    main()

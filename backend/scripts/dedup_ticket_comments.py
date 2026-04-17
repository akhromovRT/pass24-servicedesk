"""Чистка дублирующихся клиентских комментариев, накопленных до миграции 022.

Для каждого тикета группирует комментарии по (author_id, text.strip()) и
оставляет самый ранний по created_at. Остальные комментарии группы вместе с
привязанными к ним вложениями (только БД-записи; файлы на диске трогать не
будем — это ответственность отдельного gc-скрипта) удаляются.

Запуск:
  docker exec site-pass24-servicedesk python -m backend.scripts.dedup_ticket_comments --dry-run
  docker exec site-pass24-servicedesk python -m backend.scripts.dedup_ticket_comments --ticket d6393659
  docker exec site-pass24-servicedesk python -m backend.scripts.dedup_ticket_comments --all
"""
from __future__ import annotations

import argparse
import asyncio
import logging
from collections import defaultdict

from sqlmodel import select

from backend.database import async_session_factory
from backend.tickets.models import Attachment, TicketComment

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
logger = logging.getLogger("dedup_comments")


def _group_key(c: TicketComment) -> tuple[str, str]:
    # Внутренние заметки агентов не трогаем — дубли приходят только из email.
    return (c.author_id, (c.text or "").strip())


async def _dedup_ticket(ticket_id: str, dry_run: bool) -> tuple[int, int]:
    """Возвращает (kept, removed) для одного тикета."""
    async with async_session_factory() as session:
        r = await session.execute(
            select(TicketComment)
            .where(TicketComment.ticket_id == ticket_id)
            .order_by(TicketComment.created_at.asc())
        )
        comments = list(r.scalars())

        groups: dict[tuple[str, str], list[TicketComment]] = defaultdict(list)
        for c in comments:
            if c.is_internal:
                continue
            if not (c.text or "").strip():
                continue
            groups[_group_key(c)].append(c)

        to_remove: list[TicketComment] = []
        for group in groups.values():
            if len(group) < 2:
                continue
            # Оставляем самый ранний, остальные — на удаление.
            group.sort(key=lambda c: c.created_at)
            to_remove.extend(group[1:])

        if not to_remove:
            return (len(comments), 0)

        for dup in to_remove:
            # Отвязываем/удаляем вложения, привязанные к дублю.
            a = await session.execute(
                select(Attachment).where(Attachment.comment_id == dup.id)
            )
            for att in a.scalars():
                logger.info(
                    "  attachment %s (%s) %s",
                    att.id[:8], att.filename, "[dry-run]" if dry_run else "→ delete",
                )
                if not dry_run:
                    await session.delete(att)

            logger.info(
                "  comment %s created=%s %s",
                dup.id[:8], dup.created_at.isoformat(timespec="seconds"),
                "[dry-run]" if dry_run else "→ delete",
            )
            if not dry_run:
                await session.delete(dup)

        if not dry_run:
            await session.commit()

        return (len(comments) - len(to_remove), len(to_remove))


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ticket", help="Префикс UUID тикета (напр. d6393659) или полный id")
    parser.add_argument("--all", action="store_true", help="Обработать все тикеты")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if not args.ticket and not args.all:
        parser.error("Укажите --ticket <id> или --all")

    # Собираем список тикетов к обработке
    if args.ticket:
        from backend.tickets.models import Ticket
        async with async_session_factory() as s:
            if len(args.ticket) == 36:
                r = await s.execute(select(Ticket.id).where(Ticket.id == args.ticket))
            else:
                r = await s.execute(
                    select(Ticket.id).where(Ticket.id.like(args.ticket.lower() + "%"))
                )
            ticket_ids = [row[0] for row in r.all()]
        if not ticket_ids:
            logger.error("Тикет не найден по префиксу %s", args.ticket)
            return
    else:
        from backend.tickets.models import Ticket
        async with async_session_factory() as s:
            r = await s.execute(select(Ticket.id))
            ticket_ids = [row[0] for row in r.all()]

    total_removed = 0
    total_kept = 0
    touched_tickets = 0
    for tid in ticket_ids:
        kept, removed = await _dedup_ticket(tid, args.dry_run)
        if removed:
            logger.info("ticket %s: kept %d, removed %d", tid[:8], kept, removed)
            touched_tickets += 1
        total_kept += kept
        total_removed += removed

    print("\n=== Dedup summary ===")
    print(f"  tickets scanned:  {len(ticket_ids)}")
    print(f"  tickets touched:  {touched_tickets}")
    print(f"  comments kept:    {total_kept}")
    print(f"  comments removed: {total_removed}{' (dry-run)' if args.dry_run else ''}")


if __name__ == "__main__":
    asyncio.run(main())

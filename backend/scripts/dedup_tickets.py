"""Чистка дублирующихся email-тикетов, накопленных до миграции 026.

Группирует тикеты по (contact_email, normalized_title, source='email') среди
записей с `email_message_id IS NULL` — только pre-migration дубли, которые
не защищены уникальным частичным индексом из миграции 026.

Для каждой группы с >1 тикетом:
  - primary = самый ранний по created_at
  - остальные («дубли») сливаются в primary тем же способом, что и ручной
    /tickets/{id}/merge в router.py:
      * comments и attachments переподвязываются на primary
        (UPDATE ticket_id);
      * ticket_events остаются у каждого тикета (индивидуальная история);
      * дубль получает `merged_into_ticket_id = primary.id` и статус CLOSED;
      * в primary и в дубле пишутся события с описанием слияния.
  - ни одна строка не удаляется — это non-destructive merge; при ошибке
    можно откатиться через merged_into_ticket_id.

Запуск:
  docker exec site-pass24-servicedesk python -m backend.scripts.dedup_tickets --dry-run
  docker exec site-pass24-servicedesk python -m backend.scripts.dedup_tickets --email client@example.com
  docker exec site-pass24-servicedesk python -m backend.scripts.dedup_tickets --all
"""
from __future__ import annotations

import argparse
import asyncio
import logging
from collections import defaultdict
from datetime import datetime

from sqlalchemy import update as sa_update
from sqlmodel import select

from backend.database import async_session_factory
from backend.tickets.models import (
    Attachment,
    Ticket,
    TicketComment,
    TicketEvent,
    TicketStatus,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
logger = logging.getLogger("dedup_tickets")

# Актор системных событий. Не связан с реальным пользователем, но полезен
# для фильтра при аудите: `WHERE actor_id = 'system:dedup-026'`.
SYSTEM_ACTOR = "system:dedup-026"


def _group_key(t: Ticket) -> tuple[str, str]:
    """Ключ дедупа: нормализованный email + stripped title.

    Source и email_message_id_is_null фильтруем на уровне SELECT, поэтому сюда
    попадают только кандидаты. Регистр email нормализуем (SMTP-адреса
    case-insensitive в local+domain частях), title — strip'аем одинаково
    с inbound.py::_handle_new_ticket.
    """
    email = (t.contact_email or "").strip().lower()
    title = (t.title or "").strip()
    return (email, title)


async def _load_candidates(email_filter: str | None) -> list[Ticket]:
    async with async_session_factory() as session:
        q = (
            select(Ticket)
            .where(
                Ticket.source == "email",
                Ticket.email_message_id.is_(None),
                Ticket.merged_into_ticket_id.is_(None),  # уже слитые не трогаем
            )
            .order_by(Ticket.contact_email, Ticket.title, Ticket.created_at)
        )
        if email_filter:
            q = q.where(Ticket.contact_email == email_filter)
        r = await session.execute(q)
        return list(r.scalars())


async def _merge_group(primary: Ticket, duplicates: list[Ticket], dry_run: bool) -> None:
    async with async_session_factory() as session:
        # Пересчитаем количество перемещаемых записей для лога (SELECT COUNT)
        # до любых UPDATE'ов — так же работает ручной /merge в router.py.
        for dup in duplicates:
            comments_q = await session.execute(
                select(TicketComment.id).where(TicketComment.ticket_id == dup.id)
            )
            comment_ids = [row[0] for row in comments_q.all()]
            attachments_q = await session.execute(
                select(Attachment.id).where(Attachment.ticket_id == dup.id)
            )
            attachment_ids = [row[0] for row in attachments_q.all()]

            logger.info(
                "  dup #%s created=%s → merge into #%s (comments=%d, attachments=%d) %s",
                dup.id[:8],
                dup.created_at.isoformat(timespec="seconds"),
                primary.id[:8],
                len(comment_ids),
                len(attachment_ids),
                "[dry-run]" if dry_run else "→ commit",
            )

            if dry_run:
                continue

            # Переподвязываем дочерние записи — тот же набор таблиц, что в ручном /merge.
            # ticket_events НЕ трогаем — история каждого тикета остаётся с ним.
            if comment_ids:
                await session.execute(
                    sa_update(TicketComment)
                    .where(TicketComment.ticket_id == dup.id)
                    .values(ticket_id=primary.id)
                )
            if attachment_ids:
                await session.execute(
                    sa_update(Attachment)
                    .where(Attachment.ticket_id == dup.id)
                    .values(ticket_id=primary.id)
                )

            # Отметка о слиянии на самом дубле.
            await session.execute(
                sa_update(Ticket)
                .where(Ticket.id == dup.id)
                .values(
                    merged_into_ticket_id=primary.id,
                    status=TicketStatus.CLOSED,
                    updated_at=datetime.utcnow(),
                )
            )

            # Журнал в обоих направлениях — как делает ручной /merge.
            session.add(
                TicketEvent(
                    ticket_id=primary.id,
                    actor_id=SYSTEM_ACTOR,
                    description=f"Слит дубликат #{dup.id[:8]} ({dup.title[:60]}) — миграция 026",
                )
            )
            session.add(
                TicketEvent(
                    ticket_id=dup.id,
                    actor_id=SYSTEM_ACTOR,
                    description=f"Слит в #{primary.id[:8]} — миграция 026 (cleanup pre-026 дублей)",
                )
            )

        if not dry_run:
            await session.commit()


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--email",
        help="Обработать только тикеты с таким contact_email (точное совпадение)",
    )
    parser.add_argument("--all", action="store_true", help="Обработать всех кандидатов")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if not args.email and not args.all:
        parser.error("Укажите --email <address> или --all")

    candidates = await _load_candidates(args.email)
    logger.info("Кандидаты (source=email, email_message_id IS NULL): %d", len(candidates))

    groups: dict[tuple[str, str], list[Ticket]] = defaultdict(list)
    for t in candidates:
        key = _group_key(t)
        if not key[0] or not key[1]:
            # Пропускаем тикеты без email или title — не наш класс дублей.
            continue
        groups[key].append(t)

    merge_groups = [g for g in groups.values() if len(g) > 1]
    logger.info("Групп с дублями (≥2 тикета): %d", len(merge_groups))

    total_merged = 0
    for group in merge_groups:
        group.sort(key=lambda t: t.created_at)
        primary = group[0]
        duplicates = group[1:]
        logger.info(
            "group email=%s title=%r — primary #%s, дублей %d",
            primary.contact_email, primary.title[:60],
            primary.id[:8], len(duplicates),
        )
        await _merge_group(primary, duplicates, args.dry_run)
        total_merged += len(duplicates)

    print("\n=== Dedup summary ===")
    print(f"  candidates scanned: {len(candidates)}")
    print(f"  groups with dupes:  {len(merge_groups)}")
    print(f"  tickets merged:     {total_merged}{' (dry-run)' if args.dry_run else ''}")


if __name__ == "__main__":
    asyncio.run(main())

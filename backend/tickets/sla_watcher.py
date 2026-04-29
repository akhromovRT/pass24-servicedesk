"""Фоновая задача: следит за SLA и шлёт предупреждения за 30 минут до нарушения."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta

from sqlmodel import select

from backend.database import async_session_factory
from backend.tickets.models import Ticket, TicketStatus
from backend.tickets.sla_service import compute_sla_state

logger = logging.getLogger(__name__)

CHECK_INTERVAL_SECONDS = 300  # 5 минут
WARN_BEFORE_MINUTES = 30


async def _check_sla_breaches() -> int:
    """Находит тикеты, которые нарушат SLA через 30 мин, и помечает их."""
    from backend.auth.models import User
    from backend.notifications.email import _send_email, ticket_subject_tag, STATUS_LABELS

    now = datetime.utcnow()
    warn_threshold = timedelta(minutes=WARN_BEFORE_MINUTES)
    warned = 0

    async with async_session_factory() as session:
        # Активные тикеты, которые ещё не были предупреждены
        r = await session.execute(
            select(Ticket).where(
                Ticket.status.in_(["new", "in_progress", "engineer_visit"]),
                Ticket.sla_breach_warned == False,  # noqa: E712
                Ticket.resolved_at.is_(None),
            )
        )
        tickets = list(r.scalars())

        for t in tickets:
            state = compute_sla_state(t, now)
            # Тикет на паузе (по статусу или ответу агента) — не warn-им,
            # пока пауза активна. Дедлайн «дойдёт» когда снова ноль reply/status.
            if state.is_paused:
                continue
            if state.active_due_at is None:
                continue
            deadline = state.active_due_at
            time_to_breach = deadline - now

            # Уже нарушено или до нарушения осталось меньше 30 минут
            if timedelta(0) < time_to_breach <= warn_threshold:
                t.sla_breach_warned = True
                session.add(t)
                warned += 1

                # Email админам
                tag = ticket_subject_tag(t.id)
                mins_left = int(time_to_breach.total_seconds() // 60)
                await _send_email(
                    to="support@pass24online.ru",
                    subject=f"{tag} ⚠️ SLA истекает через {mins_left} мин: {t.title}",
                    html_body=f"""
                    <div style="font-family: -apple-system, Arial, sans-serif; max-width: 600px;">
                        <div style="background: #dc2626; color: #fff; padding: 16px 24px; border-radius: 8px 8px 0 0;">
                            <strong>⚠️ SLA скоро истечёт</strong>
                        </div>
                        <div style="padding: 20px; border: 1px solid #e2e8f0; border-top: none; border-radius: 0 0 8px 8px;">
                            <p><strong>Заявка:</strong> {t.title}</p>
                            <p><strong>Осталось:</strong> {mins_left} мин до нарушения SLA</p>
                            <p><strong>Статус:</strong> {STATUS_LABELS.get(t.status.value if hasattr(t.status, 'value') else str(t.status), str(t.status))}</p>
                            <p><a href="https://support.pass24pro.ru/tickets/{t.id}" style="color: #2563eb;">Открыть заявку</a></p>
                        </div>
                    </div>
                    """,
                )
                logger.info("SLA warning sent for ticket %s (%d min left)", t.id[:8], mins_left)

                # Telegram-предупреждение создателю (best-effort, не блокирует коммит).
                try:
                    cr = await session.execute(
                        select(User).where(User.id == t.creator_id)
                    )
                    creator = cr.scalar_one_or_none()
                    if creator and creator.telegram_chat_id:
                        prefs = creator.telegram_preferences or {}
                        if prefs.get("notify_sla", True):
                            from backend.telegram.services.notify import (
                                notify_telegram_sla_warning,
                            )
                            await notify_telegram_sla_warning(
                                chat_id=creator.telegram_chat_id,
                                ticket_id=t.id,
                                ticket_title=t.title,
                                deadline=deadline,
                                user=creator,
                            )
                except Exception as exc:  # noqa: BLE001 — уведомление не должно падать SLA-луп
                    logger.warning(
                        "TG SLA warning failed for ticket %s: %s", t.id[:8], exc
                    )
            elif time_to_breach <= timedelta(0) and not t.sla_breached:
                # Нарушение — ставим флаг breached
                t.sla_breached = True
                session.add(t)

        await session.commit()

    return warned


async def sla_watcher_loop() -> None:
    """Бесконечный цикл проверки SLA."""
    logger.info("SLA watcher started, interval=%ds", CHECK_INTERVAL_SECONDS)
    while True:
        try:
            count = await _check_sla_breaches()
            if count > 0:
                logger.info("SLA check: warned %d tickets", count)
        except Exception as exc:
            logger.error("SLA watcher error: %s", exc)
        await asyncio.sleep(CHECK_INTERVAL_SECONDS)

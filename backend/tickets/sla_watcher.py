"""Фоновая задача: следит за SLA и шлёт предупреждения за 30 минут до нарушения."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta

from sqlmodel import select

from backend.database import async_session_factory
from backend.tickets.models import Ticket, TicketStatus

logger = logging.getLogger(__name__)

CHECK_INTERVAL_SECONDS = 300  # 5 минут
WARN_BEFORE_MINUTES = 30

# Рабочие часы МСК: пн-пт 9:00-18:00
WORK_START_HOUR = 9
WORK_END_HOUR = 18
# UTC offset МСК = +3
MSK_OFFSET_HOURS = 3


def _msk_hour(dt_utc: datetime) -> int:
    return (dt_utc.hour + MSK_OFFSET_HOURS) % 24


def _is_work_time(dt_utc: datetime) -> bool:
    """Проверка: рабочее время (пн-пт, 9-18 МСК)."""
    # weekday: 0=пн, 6=вс
    if dt_utc.weekday() >= 5:  # суббота/воскресенье
        return False
    h = _msk_hour(dt_utc)
    return WORK_START_HOUR <= h < WORK_END_HOUR


def business_hours_between(start: datetime, end: datetime) -> float:
    """Считает количество рабочих часов между двумя моментами.

    Упрощённая реализация: пробегаем по 30-мин интервалам.
    Достаточно точно для целей SLA (5 мин частота проверки).
    """
    if end <= start:
        return 0.0
    minutes = 0
    step = timedelta(minutes=30)
    cur = start
    while cur < end:
        if _is_work_time(cur):
            minutes += 30
        cur += step
    return minutes / 60.0


def deadline_with_business_hours(start: datetime, sla_hours: int) -> datetime:
    """Находит дедлайн, пропуская нерабочее время."""
    if sla_hours <= 0:
        return start
    target_minutes = sla_hours * 60
    accumulated = 0
    step = timedelta(minutes=30)
    cur = start
    while accumulated < target_minutes:
        if _is_work_time(cur):
            accumulated += 30
        cur += step
        # safety: не зацикливаемся более чем на год
        if cur - start > timedelta(days=365):
            return cur
    return cur


async def _check_sla_breaches() -> int:
    """Находит тикеты, которые нарушат SLA через 30 мин, и помечает их."""
    from backend.notifications.email import _send_email, ticket_subject_tag, STATUS_LABELS

    now = datetime.utcnow()
    warn_threshold = timedelta(minutes=WARN_BEFORE_MINUTES)
    warned = 0

    async with async_session_factory() as session:
        # Активные тикеты, которые ещё не были предупреждены
        r = await session.execute(
            select(Ticket).where(
                Ticket.status.in_([TicketStatus.NEW, TicketStatus.IN_PROGRESS, TicketStatus.ENGINEER_VISIT]),
                Ticket.sla_breach_warned == False,  # noqa: E712
                Ticket.resolved_at.is_(None),
            )
        )
        tickets = list(r.scalars())

        for t in tickets:
            if not t.sla_resolve_hours:
                continue
            pause_sec = t.sla_total_pause_seconds or 0
            # Дедлайн с учётом рабочих часов + пауз в WAITING_FOR_USER
            deadline = deadline_with_business_hours(t.created_at, t.sla_resolve_hours)
            deadline = deadline + timedelta(seconds=pause_sec)
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

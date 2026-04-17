"""Юнит-тесты логики расчёта дедлайна в SLA watcher."""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from backend.tickets.models import Ticket, TicketStatus


pytestmark = pytest.mark.asyncio


def _ticket_with_paused_sla(resolve_hours: int, created_at: datetime, paused_at: datetime | None) -> Ticket:
    t = Ticket(
        creator_id="u",
        title="t",
        description="",
        status=TicketStatus.IN_PROGRESS,
        sla_resolve_hours=resolve_hours,
        created_at=created_at,
    )
    t.sla_paused_at = paused_at
    t.sla_paused_by_reply = paused_at is not None
    return t


def test_active_pause_extends_effective_deadline():
    """Если сейчас активна пауза длительностью 2 часа, дедлайн сдвинут на 2 часа вперёд."""
    from backend.tickets.sla_watcher import deadline_with_business_hours

    now = datetime(2026, 4, 17, 16, 0, 0)  # вт, рабочее время МСК = 19:00 (вне), но для теста используем вычисление напрямую
    created = now - timedelta(hours=5)
    paused = now - timedelta(hours=2)
    t = _ticket_with_paused_sla(resolve_hours=4, created_at=created, paused_at=paused)

    base_deadline = deadline_with_business_hours(t.created_at, t.sla_resolve_hours)
    pause_sec = t.sla_total_pause_seconds or 0
    if t.sla_paused_at is not None:
        pause_sec += int((now - t.sla_paused_at).total_seconds())
    deadline = base_deadline + timedelta(seconds=pause_sec)

    # С учётом активной паузы (2ч) effective deadline должен быть в будущем.
    assert deadline > now, f"Активная пауза должна двигать дедлайн за now, deadline={deadline}"


async def test_check_sla_breaches_ignores_active_pause():
    """Тикет в in_progress с активной reply-паузой не должен получать breach warning,
    если с учётом паузы дедлайн далеко в будущем."""
    from backend.database import async_session_factory
    from backend.tickets.sla_watcher import _check_sla_breaches
    from backend.tickets.models import Ticket, TicketStatus

    async with async_session_factory() as s:
        now = datetime.utcnow()
        ticket = Ticket(
            creator_id="u",
            title="Test watcher pause",
            description="",
            status=TicketStatus.IN_PROGRESS,
            sla_resolve_hours=1,
            created_at=now - timedelta(minutes=89),
        )
        ticket.sla_paused_by_reply = True
        ticket.sla_paused_at = now - timedelta(hours=1)
        s.add(ticket)
        await s.commit()
        ticket_id = ticket.id

    try:
        await _check_sla_breaches()
        async with async_session_factory() as s:
            fresh = await s.get(Ticket, ticket_id)
            assert fresh.sla_breach_warned is False, (
                "Watcher не должен warn-ить тикет с активной паузой"
            )
    finally:
        async with async_session_factory() as s:
            t = await s.get(Ticket, ticket_id)
            if t:
                await s.delete(t)
                await s.commit()

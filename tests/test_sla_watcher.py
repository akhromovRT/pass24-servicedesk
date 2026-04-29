"""Юнит-тесты логики расчёта дедлайна в SLA watcher."""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from backend.tickets.business_hours import MSK_OFFSET_HOURS
from backend.tickets.models import Ticket, TicketStatus


pytestmark = pytest.mark.asyncio


def _msk(year: int, month: int, day: int, hour_msk: int, minute: int = 0) -> datetime:
    return datetime(year, month, day, hour_msk - MSK_OFFSET_HOURS, minute, 0)


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
    """compute_sla_state с активной паузой удлиняет дедлайн на бизнес-часы паузы."""
    from backend.tickets.sla_service import compute_sla_state

    # Все моменты в рабочее время понедельника, чтобы пауза целиком в бизнес-часах.
    created = _msk(2026, 4, 27, 9, 0)   # пн 09:00 МСК
    paused = _msk(2026, 4, 27, 10, 0)   # пн 10:00 МСК
    now = _msk(2026, 4, 27, 12, 0)      # пн 12:00 МСК — пауза идёт 2 рабочих часа

    t = _ticket_with_paused_sla(resolve_hours=4, created_at=created, paused_at=paused)
    state = compute_sla_state(t, now)

    # is_paused активна, active_due_at — это response (нет first_response_at).
    # response_due_at без паузы = пн 13:00; с 2ч паузы = пн 15:00.
    assert state.is_paused is True
    assert state.active_due_at == _msk(2026, 4, 27, 15, 0)
    assert state.active_due_at > now


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

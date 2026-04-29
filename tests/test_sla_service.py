"""Юнит-тесты compute_sla_state — единая точка истины состояния SLA."""
from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

from backend.tickets.business_hours import MSK_OFFSET_HOURS
from backend.tickets.sla_service import SlaState, compute_sla_state


def _msk(year: int, month: int, day: int, hour_msk: int, minute: int = 0) -> datetime:
    return datetime(year, month, day, hour_msk - MSK_OFFSET_HOURS, minute, 0)


def _ticket(
    *,
    created_at: datetime,
    sla_response_hours: int | None = 4,
    sla_resolve_hours: int | None = 24,
    first_response_at: datetime | None = None,
    resolved_at: datetime | None = None,
    sla_paused_at: datetime | None = None,
    sla_total_pause_seconds: int = 0,
) -> SimpleNamespace:
    return SimpleNamespace(
        created_at=created_at,
        sla_response_hours=sla_response_hours,
        sla_resolve_hours=sla_resolve_hours,
        first_response_at=first_response_at,
        resolved_at=resolved_at,
        sla_paused_at=sla_paused_at,
        sla_total_pause_seconds=sla_total_pause_seconds,
    )


def test_active_phase_is_response_when_no_first_reply():
    """Тикет создан пт 17:00 МСК, response 4ч, resolve 24ч, без first_response.
    Дедлайн ответа: пн 12:00 МСК. Active = response."""
    created = _msk(2026, 5, 1, 17, 0)
    now = _msk(2026, 5, 4, 10, 0)  # пн 10:00 МСК
    state = compute_sla_state(
        _ticket(created_at=created, sla_response_hours=4, sla_resolve_hours=24),
        now,
    )
    assert state.response_due_at == _msk(2026, 5, 4, 12, 0)
    assert state.active_due_at == state.response_due_at
    assert state.remaining_seconds == 7200  # 2 часа до 12:00
    assert state.is_paused is False


def test_overdue_negative_remaining():
    """Тикет давно нарушен — remaining_seconds отрицательный."""
    created = _msk(2026, 5, 4, 9, 0)  # пн 09:00 МСК
    now = _msk(2026, 5, 4, 14, 0)     # пн 14:00 МСК
    state = compute_sla_state(
        _ticket(created_at=created, sla_response_hours=1, sla_resolve_hours=4),
        now,
    )
    # Active phase = response (нет first_response). Дедлайн пн 10:00 МСК.
    assert state.response_due_at == _msk(2026, 5, 4, 10, 0)
    assert state.remaining_seconds == -14400  # -4 часа
    assert state.response_remaining_seconds == -14400
    # Resolve дедлайн пн 13:00 МСК → -1ч.
    assert state.resolve_due_at == _msk(2026, 5, 4, 13, 0)
    assert state.resolve_remaining_seconds == -3600


def test_active_phase_switches_to_resolve_after_first_reply():
    """first_response_at задан → active_due_at == resolve_due_at."""
    created = _msk(2026, 5, 4, 9, 0)  # пн 09:00 МСК
    first_reply = _msk(2026, 5, 4, 9, 30)
    now = _msk(2026, 5, 4, 11, 0)
    state = compute_sla_state(
        _ticket(
            created_at=created,
            sla_response_hours=1,
            sla_resolve_hours=4,
            first_response_at=first_reply,
        ),
        now,
    )
    assert state.active_due_at == state.resolve_due_at
    assert state.active_due_at == _msk(2026, 5, 4, 13, 0)
    assert state.remaining_seconds == 7200  # 2 часа до 13:00


def test_paused_ticket_is_paused_flag():
    """Тикет на паузе — is_paused True, active_pause считается в бизнес-часах."""
    created = _msk(2026, 5, 1, 14, 0)         # пт 14:00 МСК
    paused_at = _msk(2026, 5, 1, 17, 30)      # пт 17:30 МСК
    now = _msk(2026, 5, 4, 12, 0)             # пн 12:00 МСК
    state = compute_sla_state(
        _ticket(
            created_at=created,
            sla_response_hours=4,
            sla_resolve_hours=8,
            sla_paused_at=paused_at,
            sla_total_pause_seconds=0,
        ),
        now,
    )
    assert state.is_paused is True
    # Активная пауза в бизнес-часах: пт 17:30→18:00 = 30 мин, пн 09:00→12:00 = 3ч → 3.5ч.
    # Без паузы дедлайн response пт 18:00. С паузой 3.5ч → дедлайн пн 12:30.
    # (Алгоритм 30-мин шагами может дать ±30 мин — допустимо.)
    assert state.response_due_at >= _msk(2026, 5, 4, 12, 0)
    assert state.response_due_at <= _msk(2026, 5, 4, 13, 0)


def test_resolved_ticket_returns_zero_remaining():
    """resolved_at задан → remaining_seconds = 0, is_paused = False."""
    created = _msk(2026, 5, 4, 9, 0)
    resolved = _msk(2026, 5, 4, 11, 0)
    state = compute_sla_state(
        _ticket(
            created_at=created,
            sla_resolve_hours=4,
            resolved_at=resolved,
            first_response_at=_msk(2026, 5, 4, 9, 30),
        ),
        _msk(2026, 5, 5, 10, 0),
    )
    assert state.remaining_seconds == 0
    assert state.is_paused is False


def test_ticket_created_on_saturday_starts_monday():
    """Создан в сб 12:00 МСК → дедлайн начинает копиться с пн 09:00."""
    created = _msk(2026, 5, 2, 12, 0)  # сб 12:00 МСК
    state = compute_sla_state(
        _ticket(created_at=created, sla_response_hours=4),
        _msk(2026, 5, 4, 10, 0),
    )
    # 4 рабочих часа от пн 09:00 → пн 13:00 МСК.
    assert state.response_due_at == _msk(2026, 5, 4, 13, 0)


def test_no_sla_configured_returns_none():
    """sla_*_hours = None → due_at = None, remaining_seconds = None."""
    state = compute_sla_state(
        _ticket(
            created_at=_msk(2026, 5, 4, 9, 0),
            sla_response_hours=None,
            sla_resolve_hours=None,
        ),
        _msk(2026, 5, 4, 10, 0),
    )
    assert state.response_due_at is None
    assert state.resolve_due_at is None
    assert state.active_due_at is None
    assert state.remaining_seconds is None
    assert state.response_remaining_seconds is None
    assert state.resolve_remaining_seconds is None
    assert state.is_paused is False


def test_total_pause_seconds_extends_deadline_in_business_minutes():
    """sla_total_pause_seconds (бизнес-секунды) удлиняет дедлайн на бизнес-минуты."""
    created = _msk(2026, 5, 4, 9, 0)  # пн 09:00 МСК
    # 2 рабочих часа уже накоплено как пауза (7200 бизнес-секунд)
    state = compute_sla_state(
        _ticket(
            created_at=created,
            sla_response_hours=2,
            sla_total_pause_seconds=7200,
        ),
        _msk(2026, 5, 4, 10, 0),
    )
    # Без паузы: пн 09 + 2ч = пн 11. С паузой: + 2ч → пн 13.
    assert state.response_due_at == _msk(2026, 5, 4, 13, 0)


def test_recompute_sla_pause_accumulates_business_seconds_across_weekend():
    """Пауза с пт 17:00 МСК до пн 10:00 МСК = 2 бизнес-часа (1ч пт + 1ч пн), не 65."""
    from backend.tickets.models import Ticket, TicketStatus

    paused = _msk(2026, 5, 1, 17, 0)
    now = _msk(2026, 5, 4, 10, 0)

    ticket = Ticket(
        creator_id="u",
        title="t",
        description="",
        status=TicketStatus.WAITING_FOR_USER,
    )
    ticket.sla_paused_at = paused
    ticket.sla_paused_by_status = True
    # Симулируем снятие паузы: статус ушёл в IN_PROGRESS, флаг снят.
    ticket.sla_paused_by_status = False
    ticket.recompute_sla_pause(now)

    # 2 бизнес-часа = 7200 секунд (а не ~65 * 3600 = 234000 как было бы линейно).
    assert ticket.sla_total_pause_seconds == 7200
    assert ticket.sla_paused_at is None


def test_recompute_sla_pause_multiple_periods_accumulate():
    """Несколько циклов пауза-снятие — общий накопитель = сумма бизнес-часов всех."""
    from backend.tickets.models import Ticket, TicketStatus

    ticket = Ticket(
        creator_id="u",
        title="t",
        description="",
        status=TicketStatus.IN_PROGRESS,
    )
    # Период 1: пн 10:00 — пн 12:00 = 2 бизнес-часа
    ticket.sla_paused_at = _msk(2026, 5, 4, 10, 0)
    ticket.sla_paused_by_status = True
    ticket.sla_paused_by_status = False
    ticket.recompute_sla_pause(_msk(2026, 5, 4, 12, 0))
    assert ticket.sla_total_pause_seconds == 7200

    # Период 2: пн 14:00 — пн 15:30 = 1.5 бизнес-часа
    ticket.sla_paused_by_reply = True
    ticket.recompute_sla_pause(_msk(2026, 5, 4, 14, 0))  # включаем
    ticket.sla_paused_by_reply = False
    ticket.recompute_sla_pause(_msk(2026, 5, 4, 15, 30))  # снимаем

    # 2ч + 1.5ч = 3.5ч = 12600 сек
    assert ticket.sla_total_pause_seconds == 12600


def test_ticket_read_populates_sla_state():
    """TicketRead.model_validate(ticket) проставляет все 6 SLA-computed-полей."""
    from backend.tickets.models import Ticket, TicketStatus
    from backend.tickets.schemas import TicketRead

    ticket = Ticket(
        creator_id="u",
        title="t",
        description="",
        status=TicketStatus.IN_PROGRESS,
        sla_response_hours=4,
        sla_resolve_hours=24,
        # фиксированные даты, чтобы тест не зависел от now=datetime.utcnow()
        created_at=_msk(2026, 5, 4, 9, 0),
    )
    read = TicketRead.model_validate(ticket)

    assert read.sla_response_due_at == _msk(2026, 5, 4, 13, 0)  # пн 09 + 4ч
    # response_remaining_seconds зависит от now() — проверим только присутствие.
    assert isinstance(read.sla_response_remaining_seconds, int)
    assert isinstance(read.sla_resolve_remaining_seconds, int)
    assert isinstance(read.sla_remaining_seconds, int)
    assert read.sla_is_paused is False


def test_naive_datetime_guard_with_aware_input():
    """Если в ticket.sla_paused_at попадает aware datetime, функция не падает."""
    from datetime import timezone

    created = _msk(2026, 5, 4, 9, 0)
    paused_aware = _msk(2026, 5, 4, 10, 0).replace(tzinfo=timezone.utc)
    # now naive — потенциальный TypeError если без guard.
    now = _msk(2026, 5, 4, 11, 0)
    state = compute_sla_state(
        _ticket(
            created_at=created,
            sla_response_hours=4,
            sla_paused_at=paused_aware,
        ),
        now,
    )
    # Главное — не упало; is_paused True.
    assert state.is_paused is True

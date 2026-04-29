"""Юнит-тесты бизнес-часов SLA (пн-пт 9-18 МСК = UTC+3).

Все datetime — naive UTC. Перевод в МСК: +3 часа.
"""
from __future__ import annotations

from datetime import datetime

from backend.tickets.business_hours import (
    WORK_START_HOUR,
    WORK_END_HOUR,
    MSK_OFFSET_HOURS,
    _is_work_time,
    _msk_hour,
    business_hours_between,
    deadline_with_business_hours,
)


def _msk(year: int, month: int, day: int, hour_msk: int, minute: int = 0) -> datetime:
    """Удобный конструктор: задаём момент в МСК, получаем naive UTC."""
    return datetime(year, month, day, hour_msk - MSK_OFFSET_HOURS, minute, 0)


def test_constants():
    assert WORK_START_HOUR == 9
    assert WORK_END_HOUR == 18
    assert MSK_OFFSET_HOURS == 3


def test_is_work_time_boundaries():
    # Пн 09:00 МСК — рабочее
    assert _is_work_time(_msk(2026, 4, 27, 9, 0)) is True
    # Пн 17:59 МСК — рабочее
    assert _is_work_time(_msk(2026, 4, 27, 17, 59)) is True
    # Пн 18:00 МСК — НЕ рабочее (граница верхняя исключающая)
    assert _is_work_time(_msk(2026, 4, 27, 18, 0)) is False
    # Пн 08:59 МСК — НЕ рабочее
    assert _is_work_time(_msk(2026, 4, 27, 8, 59)) is False
    # Сб 12:00 МСК — НЕ рабочее (выходной)
    assert _is_work_time(_msk(2026, 5, 2, 12, 0)) is False
    # Вс 10:00 МСК — НЕ рабочее
    assert _is_work_time(_msk(2026, 5, 3, 10, 0)) is False


def test_msk_hour():
    # 06:00 UTC → 09:00 МСК
    assert _msk_hour(datetime(2026, 4, 27, 6, 0)) == 9
    # 21:00 UTC → 00:00 МСК (следующий день)
    assert _msk_hour(datetime(2026, 4, 27, 21, 0)) == 0


def test_business_hours_between_friday_to_monday():
    """Пт 17:00 МСК → пн 10:00 МСК = 2 рабочих часа (1 ч пт 17-18 + 1 ч пн 9-10)."""
    start = _msk(2026, 5, 1, 17, 0)  # пт 17:00 МСК
    end = _msk(2026, 5, 4, 10, 0)    # пн 10:00 МСК
    assert business_hours_between(start, end) == 2.0


def test_business_hours_between_friday_to_tuesday():
    """Пт 17:00 МСК → вт 10:00 МСК = 1 ч пт + 9 ч пн (9-18) + 1 ч вт = 11 ч."""
    start = _msk(2026, 5, 1, 17, 0)
    end = _msk(2026, 5, 5, 10, 0)
    assert business_hours_between(start, end) == 11.0


def test_business_hours_between_weekend_only():
    """Сб 12:00 → вс 15:00 = 0 рабочих часов."""
    start = _msk(2026, 5, 2, 12, 0)
    end = _msk(2026, 5, 3, 15, 0)
    assert business_hours_between(start, end) == 0.0


def test_business_hours_between_zero_when_end_le_start():
    start = _msk(2026, 4, 27, 12, 0)
    assert business_hours_between(start, start) == 0.0
    earlier = _msk(2026, 4, 27, 11, 0)
    assert business_hours_between(start, earlier) == 0.0


def test_deadline_friday_evening():
    """Создан в пт 17:00 МСК с SLA 4ч → дедлайн пн 12:00 МСК (1 ч пт + 3 ч пн)."""
    start = _msk(2026, 5, 1, 17, 0)
    deadline = deadline_with_business_hours(start, 4)
    expected = _msk(2026, 5, 4, 12, 0)
    assert deadline == expected


def test_deadline_saturday():
    """Создан в сб 12:00 МСК с SLA 4ч → дедлайн пн 13:00 МСК (4 ч понедельника)."""
    start = _msk(2026, 5, 2, 12, 0)
    deadline = deadline_with_business_hours(start, 4)
    expected = _msk(2026, 5, 4, 13, 0)
    assert deadline == expected


def test_deadline_zero_hours_returns_start():
    start = _msk(2026, 4, 27, 12, 0)
    assert deadline_with_business_hours(start, 0) == start
    assert deadline_with_business_hours(start, -1) == start

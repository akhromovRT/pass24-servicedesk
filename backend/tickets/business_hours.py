"""Бизнес-часы SLA: пн-пт 9-18 МСК (UTC+3).

Чистый модуль без зависимостей от моделей — пригоден для импорта из
любого слоя (models, schemas, services, watcher).

Все datetime принимаются как naive UTC. Перевод в МСК — арифметический
сдвиг на +3 часа (см. ADR-005).
"""
from __future__ import annotations

from datetime import datetime, timedelta

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
    if dt_utc.weekday() >= 5:
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


def deadline_with_business_minutes(start: datetime, target_minutes: int) -> datetime:
    """Находит дедлайн от `start`, накапливая `target_minutes` рабочих минут.

    Шаг 30 минут — точность ±30 мин (см. ADR-005). При `target_minutes <= 0`
    возвращает `start`.
    """
    if target_minutes <= 0:
        return start
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


def deadline_with_business_hours(start: datetime, sla_hours: int) -> datetime:
    """Удобный wrapper над `deadline_with_business_minutes` (часы → минуты)."""
    if sla_hours <= 0:
        return start
    return deadline_with_business_minutes(start, sla_hours * 60)

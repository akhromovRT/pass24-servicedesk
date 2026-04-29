"""Сервис состояния SLA — единая точка истины для бэка и API.

`compute_sla_state(ticket, now)` принимает duck-typed ticket и возвращает
`SlaState` со всеми вычисляемыми полями: дедлайны (response/resolve),
оставшееся время (может быть отрицательным при просрочке), флаг паузы.

Зависимости — только бизнес-часы (`backend.tickets.business_hours`).
Не импортирует модели и схемы, чтобы не было циклов и чтобы функция
была одинаково применима к SQLModel-`Ticket` и Pydantic-`TicketRead`.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Protocol

from backend.tickets.business_hours import (
    business_hours_between,
    deadline_with_business_minutes,
)


class _TicketLike(Protocol):
    """Минимальный набор атрибутов, необходимый для расчёта SLA."""

    created_at: datetime
    resolved_at: Optional[datetime]
    first_response_at: Optional[datetime]
    sla_response_hours: Optional[int]
    sla_resolve_hours: Optional[int]
    sla_paused_at: Optional[datetime]
    sla_total_pause_seconds: int


@dataclass
class SlaState:
    """Полное состояние SLA на момент `now`.

    `*_remaining_seconds` положительное — есть запас, отрицательное — просрочка.
    `None` означает, что соответствующий SLA не настроен.
    """

    response_due_at: Optional[datetime]
    resolve_due_at: Optional[datetime]
    active_due_at: Optional[datetime]
    response_remaining_seconds: Optional[int]
    resolve_remaining_seconds: Optional[int]
    remaining_seconds: Optional[int]  # для активной фазы (response → resolve)
    is_paused: bool


def _to_naive(dt: Optional[datetime]) -> Optional[datetime]:
    """Срезает tzinfo, если datetime aware. Защита от смешивания naive/aware."""
    if dt is None:
        return None
    if dt.tzinfo is not None:
        return dt.replace(tzinfo=None)
    return dt


def compute_sla_state(ticket: _TicketLike, now: datetime) -> SlaState:
    """Вычисляет полное состояние SLA для тикета на момент `now`.

    Семантика:
    - дедлайны считаются в бизнес-минутах от `created_at`, удлиняются на
      `sla_total_pause_seconds` + активная пауза (тоже в бизнес-секундах);
    - `remaining_seconds` для resolved-тикетов всегда 0;
    - при `sla_paused_at is not None` `is_paused = True`, активная пауза
      считается через `business_hours_between(sla_paused_at, now)`.
    """
    now = _to_naive(now)
    created_at = _to_naive(ticket.created_at)
    sla_paused_at = _to_naive(ticket.sla_paused_at)

    is_paused = sla_paused_at is not None

    # Завершённый тикет: оставшееся = 0, дедлайн как был.
    if ticket.resolved_at is not None:
        resolve_due = (
            deadline_with_business_minutes(
                created_at,
                ticket.sla_resolve_hours * 60
                + (ticket.sla_total_pause_seconds // 60),
            )
            if ticket.sla_resolve_hours
            else None
        )
        response_due = (
            deadline_with_business_minutes(
                created_at,
                ticket.sla_response_hours * 60
                + (ticket.sla_total_pause_seconds // 60),
            )
            if ticket.sla_response_hours
            else None
        )
        return SlaState(
            response_due_at=response_due,
            resolve_due_at=resolve_due,
            active_due_at=resolve_due,
            response_remaining_seconds=0 if response_due else None,
            resolve_remaining_seconds=0 if resolve_due else None,
            remaining_seconds=0 if resolve_due else None,
            is_paused=False,
        )

    # Активная пауза: считается в бизнес-часах от sla_paused_at до now.
    active_pause_sec = 0
    if is_paused:
        active_pause_sec = int(business_hours_between(sla_paused_at, now) * 3600)

    total_pause_sec = (ticket.sla_total_pause_seconds or 0) + active_pause_sec
    pause_minutes = total_pause_sec // 60

    response_due: Optional[datetime] = None
    response_rem: Optional[int] = None
    if ticket.sla_response_hours:
        response_due = deadline_with_business_minutes(
            created_at, ticket.sla_response_hours * 60 + pause_minutes
        )
        response_rem = int((response_due - now).total_seconds())

    resolve_due: Optional[datetime] = None
    resolve_rem: Optional[int] = None
    if ticket.sla_resolve_hours:
        resolve_due = deadline_with_business_minutes(
            created_at, ticket.sla_resolve_hours * 60 + pause_minutes
        )
        resolve_rem = int((resolve_due - now).total_seconds())

    if ticket.first_response_at is None:
        active_due = response_due
        active_rem = response_rem
    else:
        active_due = resolve_due
        active_rem = resolve_rem

    return SlaState(
        response_due_at=response_due,
        resolve_due_at=resolve_due,
        active_due_at=active_due,
        response_remaining_seconds=response_rem,
        resolve_remaining_seconds=resolve_rem,
        remaining_seconds=active_rem,
        is_paused=is_paused,
    )

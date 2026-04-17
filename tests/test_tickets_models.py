"""
Юнит-тесты для доменной логики тикетов.

Тестируют бизнес-правила без БД и фреймворков:
- Автоприоритет по ключевым словам
- FSM переходов статусов
- Неизменяемость закрытых тикетов
"""

from __future__ import annotations

import pytest

from backend.tickets.models import Ticket, TicketPriority, TicketStatus


def _make_ticket(title: str = "", description: str = "") -> Ticket:
    """Создать тикет для теста без обращения к БД."""
    return Ticket(creator_id="test-user", title=title, description=description)


# ---------------------------------------------------------------------------
# Автоприоритет
# ---------------------------------------------------------------------------


def test_critical_priority_when_user_cannot_enter_home():
    ticket = _make_ticket(title="Не могу попасть домой")
    ticket.assign_priority_based_on_context()
    assert ticket.priority == TicketPriority.CRITICAL


def test_critical_priority_door_not_opened():
    ticket = _make_ticket(description="дверь не открылась, стою перед подъездом")
    ticket.assign_priority_based_on_context()
    assert ticket.priority == TicketPriority.CRITICAL


def test_critical_priority_not_letting_in():
    ticket = _make_ticket(title="Домофон не пускает")
    ticket.assign_priority_based_on_context()
    assert ticket.priority == TicketPriority.CRITICAL


def test_high_priority_for_parking_or_gate_issues():
    ticket = _make_ticket(title="Шлагбаум не поднимается")
    ticket.assign_priority_based_on_context()
    assert ticket.priority == TicketPriority.HIGH


def test_high_priority_for_parking():
    ticket = _make_ticket(description="Проблема с парковка")
    ticket.assign_priority_based_on_context()
    assert ticket.priority == TicketPriority.HIGH


def test_low_priority_for_notification_issues():
    ticket = _make_ticket(title="Не приходят пуш-уведомления")
    ticket.assign_priority_based_on_context()
    assert ticket.priority == TicketPriority.LOW


def test_normal_priority_for_generic_issues():
    ticket = _make_ticket(title="Вопрос по интерфейсу")
    ticket.assign_priority_based_on_context()
    assert ticket.priority == TicketPriority.NORMAL


# ---------------------------------------------------------------------------
# FSM переходов статусов
# ---------------------------------------------------------------------------


def test_status_transitions_follow_rules():
    ticket = _make_ticket(title="Тест FSM")
    assert ticket.status == TicketStatus.NEW

    ticket.transition(actor_id="agent-1", new_status=TicketStatus.IN_PROGRESS)
    assert ticket.status == TicketStatus.IN_PROGRESS

    ticket.transition(actor_id="agent-1", new_status=TicketStatus.WAITING_FOR_USER)
    assert ticket.status == TicketStatus.WAITING_FOR_USER

    ticket.transition(actor_id="agent-1", new_status=TicketStatus.IN_PROGRESS)
    assert ticket.status == TicketStatus.IN_PROGRESS


def test_transition_new_to_resolved():
    ticket = _make_ticket(title="Быстрое решение")
    ticket.transition(actor_id="agent-1", new_status=TicketStatus.RESOLVED)
    assert ticket.status == TicketStatus.RESOLVED


def test_transition_resolved_to_closed():
    ticket = _make_ticket(title="Закрытие")
    ticket.transition(actor_id="agent-1", new_status=TicketStatus.RESOLVED)
    ticket.transition(actor_id="agent-1", new_status=TicketStatus.CLOSED)
    assert ticket.status == TicketStatus.CLOSED


def test_transition_reopen():
    ticket = _make_ticket(title="Переоткрытие")
    ticket.transition(actor_id="agent-1", new_status=TicketStatus.RESOLVED)
    ticket.transition(actor_id="user-1", new_status=TicketStatus.IN_PROGRESS)
    assert ticket.status == TicketStatus.IN_PROGRESS


def test_invalid_transition_raises():
    ticket = _make_ticket(title="Недопустимый переход")
    with pytest.raises(ValueError, match="Недопустимый переход"):
        ticket.transition(actor_id="agent-1", new_status=TicketStatus.CLOSED)


def test_closed_ticket_cannot_change_status():
    ticket = _make_ticket(title="Закрытый тикет")
    ticket.transition(actor_id="agent-1", new_status=TicketStatus.RESOLVED)
    ticket.transition(actor_id="agent-1", new_status=TicketStatus.CLOSED)

    with pytest.raises(ValueError, match="закрытого тикета"):
        ticket.transition(actor_id="agent-1", new_status=TicketStatus.IN_PROGRESS)


def test_transition_creates_event():
    ticket = _make_ticket(title="Событие перехода")
    event = ticket.transition(actor_id="agent-1", new_status=TicketStatus.IN_PROGRESS)

    assert event is not None
    assert event.actor_id == "agent-1"
    assert "in_progress" in event.description


# ---------------------------------------------------------------------------
# SLA pause — OR-семантика двух источников
# ---------------------------------------------------------------------------

from datetime import datetime, timedelta


def test_recompute_sla_pause_reply_flag_starts_pause():
    ticket = _make_ticket()
    now = datetime(2026, 4, 17, 12, 0, 0)
    ticket.sla_paused_by_reply = True
    ticket.recompute_sla_pause(now)
    assert ticket.sla_paused_at == now
    assert ticket.sla_total_pause_seconds == 0


def test_recompute_sla_pause_status_flag_starts_pause():
    ticket = _make_ticket()
    now = datetime(2026, 4, 17, 12, 0, 0)
    ticket.sla_paused_by_status = True
    ticket.recompute_sla_pause(now)
    assert ticket.sla_paused_at == now


def test_recompute_sla_pause_both_false_ends_pause_and_accumulates():
    ticket = _make_ticket()
    start = datetime(2026, 4, 17, 12, 0, 0)
    end = start + timedelta(hours=1)
    ticket.sla_paused_by_reply = True
    ticket.recompute_sla_pause(start)

    ticket.sla_paused_by_reply = False
    ticket.recompute_sla_pause(end)

    assert ticket.sla_paused_at is None
    assert ticket.sla_total_pause_seconds == 3600


def test_recompute_sla_pause_one_flag_active_keeps_pause():
    """Если reply-флаг снят, но статус-флаг ещё активен — пауза продолжается."""
    ticket = _make_ticket()
    start = datetime(2026, 4, 17, 12, 0, 0)
    ticket.sla_paused_by_status = True
    ticket.sla_paused_by_reply = True
    ticket.recompute_sla_pause(start)

    # reply снят, status ещё активен
    ticket.sla_paused_by_reply = False
    ticket.recompute_sla_pause(start + timedelta(minutes=30))

    assert ticket.sla_paused_at == start  # не обнулили
    assert ticket.sla_total_pause_seconds == 0  # ничего не накопили


def test_recompute_sla_pause_noop_when_state_unchanged():
    ticket = _make_ticket()
    now = datetime(2026, 4, 17, 12, 0, 0)
    ticket.sla_paused_by_reply = True
    ticket.recompute_sla_pause(now)
    # повторный вызов без изменения флагов не должен ничего портить
    ticket.recompute_sla_pause(now + timedelta(hours=2))
    assert ticket.sla_paused_at == now
    assert ticket.sla_total_pause_seconds == 0


def test_transition_to_waiting_sets_paused_by_status_flag():
    ticket = _make_ticket()
    ticket.transition(actor_id="agent-1", new_status=TicketStatus.IN_PROGRESS)
    ticket.transition(actor_id="agent-1", new_status=TicketStatus.WAITING_FOR_USER)
    assert ticket.sla_paused_by_status is True
    assert ticket.sla_paused_at is not None


def test_transition_out_of_waiting_clears_paused_by_status_flag():
    ticket = _make_ticket()
    ticket.transition(actor_id="agent-1", new_status=TicketStatus.IN_PROGRESS)
    ticket.transition(actor_id="agent-1", new_status=TicketStatus.WAITING_FOR_USER)
    ticket.transition(actor_id="agent-1", new_status=TicketStatus.IN_PROGRESS)
    assert ticket.sla_paused_by_status is False
    assert ticket.sla_paused_at is None
    assert ticket.sla_total_pause_seconds >= 0


def test_transition_on_hold_also_pauses():
    ticket = _make_ticket()
    ticket.transition(actor_id="agent-1", new_status=TicketStatus.ON_HOLD)
    assert ticket.sla_paused_by_status is True
    assert ticket.sla_paused_at is not None

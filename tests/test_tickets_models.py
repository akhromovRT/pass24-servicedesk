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

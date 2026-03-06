import pytest

from AndrewTEST.backend.tickets.models import Ticket, TicketPriority, TicketStatus


def test_critical_priority_when_user_cannot_enter_home():
    ticket = Ticket(
        id="t1",
        creator_id="user-1",
        title="Не могу попасть домой",
        description="Дверь не открылась в подъезд 3",
    )

    ticket.assign_priority_based_on_context()

    assert ticket.priority == TicketPriority.CRITICAL


def test_high_priority_for_parking_or_gate_issues():
    ticket = Ticket(
        id="t2",
        creator_id="user-1",
        title="Не открывается шлагбаум",
        description="Парковка блокирована",
    )

    ticket.assign_priority_based_on_context()

    assert ticket.priority == TicketPriority.HIGH


def test_low_priority_for_notification_issues():
    ticket = Ticket(
        id="t3",
        creator_id="user-1",
        title="Не приходят пуш‑уведомления",
        description="Пуш уведомлен о проходах не приходит",
    )

    ticket.assign_priority_based_on_context()

    assert ticket.priority == TicketPriority.LOW


def test_status_transitions_follow_rules():
    ticket = Ticket(id="t4", creator_id="user-1")

    # NEW -> IN_PROGRESS
    ticket.transition(actor_id="agent-1", new_status=TicketStatus.IN_PROGRESS)
    assert ticket.status == TicketStatus.IN_PROGRESS

    # IN_PROGRESS -> WAITING_FOR_USER
    ticket.transition(actor_id="agent-1", new_status=TicketStatus.WAITING_FOR_USER)
    assert ticket.status == TicketStatus.WAITING_FOR_USER

    # WAITING_FOR_USER -> IN_PROGRESS
    ticket.transition(actor_id="agent-1", new_status=TicketStatus.IN_PROGRESS)
    assert ticket.status == TicketStatus.IN_PROGRESS


def test_invalid_transition_raises():
    ticket = Ticket(id="t5", creator_id="user-1")

    # Нельзя перейти из NEW сразу в CLOSED
    with pytest.raises(ValueError):
        ticket.transition(actor_id="agent-1", new_status=TicketStatus.CLOSED)


def test_closed_ticket_cannot_change_status():
    ticket = Ticket(id="t6", creator_id="user-1")
    ticket.transition(actor_id="agent-1", new_status=TicketStatus.RESOLVED)
    ticket.transition(actor_id="agent-1", new_status=TicketStatus.CLOSED)

    assert ticket.status == TicketStatus.CLOSED

    with pytest.raises(ValueError):
        ticket.transition(actor_id="agent-1", new_status=TicketStatus.IN_PROGRESS)


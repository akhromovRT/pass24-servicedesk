from __future__ import annotations

from typing import Dict, List

from fastapi import APIRouter, HTTPException, status

from .models import Ticket, TicketStatus
from .schemas import TicketCreate, TicketRead, TicketStatusUpdate

router = APIRouter(prefix="/tickets", tags=["tickets"])


# На ранней стадии используем простое in-memory хранилище,
# чтобы иметь рабочий API и примеры для тестов.
_TICKETS: Dict[str, Ticket] = {}


@router.post("/", response_model=TicketRead, status_code=status.HTTP_201_CREATED)
def create_ticket(payload: TicketCreate) -> TicketRead:
    ticket_id = f"t_{len(_TICKETS) + 1}"
    ticket = Ticket(
        id=ticket_id,
        creator_id=payload.creator_id,
        object_id=payload.object_id,
        access_point_id=payload.access_point_id,
        category=payload.category,
        user_role=payload.user_role,
        occurred_at=payload.occurred_at,
        contact=payload.contact,
        urgent=payload.urgent,
        title=payload.title,
        description=payload.description,
    )
    ticket.assign_priority_based_on_context()
    _TICKETS[ticket_id] = ticket
    return TicketRead.model_validate(ticket)


@router.get("/", response_model=List[TicketRead])
def list_tickets() -> List[TicketRead]:
    """
    Минимальный список тикетов.

    Позже сюда добавятся фильтры по ролям, объектам, статусам.
    """
    return [TicketRead.model_validate(t) for t in _TICKETS.values()]


@router.get("/{ticket_id}", response_model=TicketRead)
def get_ticket(ticket_id: str) -> TicketRead:
    ticket = _TICKETS.get(ticket_id)
    if not ticket:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")
    return TicketRead.model_validate(ticket)


@router.post("/{ticket_id}/status", response_model=TicketRead)
def update_ticket_status(ticket_id: str, payload: TicketStatusUpdate) -> TicketRead:
    ticket = _TICKETS.get(ticket_id)
    if not ticket:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")

    try:
        ticket.transition(actor_id=payload.actor_id, new_status=payload.new_status)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    # Пример: если тикет перешёл в RESOLVED, позже можно будет начислять SLA‑метрики и т.п.
    return TicketRead.model_validate(ticket)


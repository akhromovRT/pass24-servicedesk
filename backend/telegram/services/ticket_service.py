from __future__ import annotations

from sqlmodel import select, func

from backend.database import async_session_factory
from backend.tickets.models import Ticket, TicketStatus


async def count_active_tickets(user_id: str) -> int:
    """Count tickets where creator_id=user_id and status != closed."""
    async with async_session_factory() as session:
        result = await session.execute(
            select(func.count(Ticket.id)).where(
                Ticket.creator_id == user_id,
                Ticket.status != TicketStatus.CLOSED.value,
            )
        )
        return int(result.scalar_one() or 0)

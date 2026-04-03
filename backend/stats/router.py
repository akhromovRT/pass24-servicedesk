from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func as sa_func, case, extract
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from backend.auth.dependencies import get_current_user
from backend.auth.models import User
from backend.database import get_session
from backend.tickets.models import Ticket, TicketStatus, TicketPriority

router = APIRouter(prefix="/stats", tags=["stats"])


@router.get("/overview")
async def get_overview(
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Общая сводка: количество тикетов по статусам и приоритетам."""
    # По статусам
    status_result = await session.execute(
        select(Ticket.status, sa_func.count())
        .group_by(Ticket.status)
    )
    by_status = {row[0]: row[1] for row in status_result.all()}

    # По приоритетам
    priority_result = await session.execute(
        select(Ticket.priority, sa_func.count())
        .group_by(Ticket.priority)
    )
    by_priority = {row[0]: row[1] for row in priority_result.all()}

    # По категориям
    category_result = await session.execute(
        select(Ticket.category, sa_func.count())
        .group_by(Ticket.category)
    )
    by_category = {row[0]: row[1] for row in category_result.all()}

    # Общие цифры
    total = sum(by_status.values())
    open_statuses = {TicketStatus.NEW, TicketStatus.IN_PROGRESS, TicketStatus.WAITING_FOR_USER}
    open_count = sum(v for k, v in by_status.items() if k in open_statuses)

    return {
        "total": total,
        "open": open_count,
        "resolved": by_status.get(TicketStatus.RESOLVED, 0),
        "closed": by_status.get(TicketStatus.CLOSED, 0),
        "by_status": {k.value if hasattr(k, 'value') else k: v for k, v in by_status.items()},
        "by_priority": {k.value if hasattr(k, 'value') else k: v for k, v in by_priority.items()},
        "by_category": dict(by_category),
    }


@router.get("/timeline")
async def get_timeline(
    days: int = Query(default=30, ge=1, le=365, description="Количество дней"),
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Тикеты по дням за указанный период."""
    since = datetime.utcnow() - timedelta(days=days)

    result = await session.execute(
        select(
            sa_func.date_trunc('day', Ticket.created_at).label('day'),
            sa_func.count().label('count'),
        )
        .where(Ticket.created_at >= since)
        .group_by('day')
        .order_by('day')
    )

    return [
        {"date": row[0].isoformat()[:10], "count": row[1]}
        for row in result.all()
    ]

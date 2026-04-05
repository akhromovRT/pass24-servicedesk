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


@router.get("/sla")
async def get_sla_stats(
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """SLA-статистика: средние времена, процент нарушений."""
    # Тикеты с first_response_at (время первого ответа)
    response_result = await session.execute(
        select(
            sa_func.count().label("total"),
            sa_func.avg(
                extract("epoch", Ticket.first_response_at - Ticket.created_at) / 3600
            ).label("avg_hours"),
        )
        .where(Ticket.first_response_at.is_not(None))
    )
    resp_row = response_result.one()
    response_total = resp_row[0] or 0
    avg_response_hours = round(float(resp_row[1] or 0), 1)

    # Нарушения SLA по первому ответу
    sla_response_breached = 0
    if response_total > 0:
        breach_result = await session.execute(
            select(sa_func.count())
            .where(
                Ticket.first_response_at.is_not(None),
                (extract("epoch", Ticket.first_response_at - Ticket.created_at) / 3600)
                > Ticket.sla_response_hours,
            )
        )
        sla_response_breached = breach_result.scalar_one()

    # Тикеты с resolved_at (время решения)
    resolve_result = await session.execute(
        select(
            sa_func.count().label("total"),
            sa_func.avg(
                extract("epoch", Ticket.resolved_at - Ticket.created_at) / 3600
            ).label("avg_hours"),
        )
        .where(Ticket.resolved_at.is_not(None))
    )
    res_row = resolve_result.one()
    resolve_total = res_row[0] or 0
    avg_resolve_hours = round(float(res_row[1] or 0), 1)

    # Нарушения SLA по решению
    sla_resolve_breached = 0
    if resolve_total > 0:
        breach_result = await session.execute(
            select(sa_func.count())
            .where(
                Ticket.resolved_at.is_not(None),
                (extract("epoch", Ticket.resolved_at - Ticket.created_at) / 3600)
                > Ticket.sla_resolve_hours,
            )
        )
        sla_resolve_breached = breach_result.scalar_one()

    return {
        "response": {
            "total": response_total,
            "avg_hours": avg_response_hours,
            "breached": sla_response_breached,
            "compliance_pct": round((1 - sla_response_breached / max(response_total, 1)) * 100, 1),
        },
        "resolution": {
            "total": resolve_total,
            "avg_hours": avg_resolve_hours,
            "breached": sla_resolve_breached,
            "compliance_pct": round((1 - sla_resolve_breached / max(resolve_total, 1)) * 100, 1),
        },
    }


@router.get("/agents")
async def get_agent_stats(
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Статистика по агентам: назначено, решено, средний CSAT."""
    from backend.auth.models import UserRole
    if current_user.role not in (UserRole.SUPPORT_AGENT, UserRole.ADMIN):
        return []

    # Все агенты
    r = await session.execute(
        select(User).where(
            User.role.in_([UserRole.SUPPORT_AGENT, UserRole.ADMIN]),
            User.is_active == True,  # noqa: E712
        )
    )
    agents = list(r.scalars())
    result = []

    for agent in agents:
        agent_id = str(agent.id)

        assigned = await session.execute(
            select(sa_func.count()).select_from(Ticket).where(Ticket.assignee_id == agent_id)
        )
        assigned_total = assigned.scalar_one()

        resolved = await session.execute(
            select(sa_func.count()).select_from(Ticket).where(
                Ticket.assignee_id == agent_id,
                Ticket.resolved_at.is_not(None),
            )
        )
        resolved_total = resolved.scalar_one()

        csat_r = await session.execute(
            select(sa_func.avg(Ticket.satisfaction_rating), sa_func.count(Ticket.satisfaction_rating))
            .where(
                Ticket.assignee_id == agent_id,
                Ticket.satisfaction_rating.is_not(None),
            )
        )
        csat_row = csat_r.one()
        avg_csat = round(float(csat_row[0]), 2) if csat_row[0] else None
        csat_count = csat_row[1] or 0

        # Среднее время решения
        avg_res = await session.execute(
            select(sa_func.avg(extract("epoch", Ticket.resolved_at - Ticket.created_at) / 3600))
            .where(
                Ticket.assignee_id == agent_id,
                Ticket.resolved_at.is_not(None),
            )
        )
        avg_res_hours = round(float(avg_res.scalar_one() or 0), 1)

        result.append({
            "id": agent_id,
            "full_name": agent.full_name,
            "email": agent.email,
            "assigned": assigned_total,
            "resolved": resolved_total,
            "avg_csat": avg_csat,
            "csat_count": csat_count,
            "avg_resolve_hours": avg_res_hours,
        })

    # Сортируем по резолвам
    result.sort(key=lambda x: x["resolved"], reverse=True)
    return result

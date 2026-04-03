from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy import delete as sa_delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlmodel import func, select

from backend.auth.dependencies import get_current_user
from backend.auth.models import User
from backend.database import get_session
from backend.notifications.email import (
    notify_ticket_comment,
    notify_ticket_created,
    notify_ticket_status_changed,
)

from .models import Ticket, TicketComment, TicketEvent, TicketStatus
from .schemas import (
    CommentCreate,
    CommentRead,
    TicketCreate,
    TicketListResponse,
    TicketRead,
    TicketStatusUpdate,
)

router = APIRouter(prefix="/tickets", tags=["tickets"])


@router.post("/", response_model=TicketRead, status_code=status.HTTP_201_CREATED)
async def create_ticket(
    payload: TicketCreate,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> TicketRead:
    """Создать новый тикет. Автор определяется по JWT-токену."""
    ticket = Ticket(
        creator_id=str(current_user.id),
        title=payload.title,
        description=payload.description,
        category=payload.category,
        object_id=payload.object_id,
        access_point_id=payload.access_point_id,
        user_role=payload.user_role,
        occurred_at=payload.occurred_at,
        contact=payload.contact,
        urgent=payload.urgent,
    )
    ticket.assign_priority_based_on_context()

    # Событие создания
    event = TicketEvent(
        ticket_id=ticket.id,
        actor_id=str(current_user.id),
        description="Тикет создан",
    )

    session.add(ticket)
    session.add(event)
    await session.commit()
    await session.refresh(ticket)

    # Email-уведомление
    background_tasks.add_task(
        notify_ticket_created,
        creator_email=current_user.email,
        ticket_id=ticket.id,
        title=ticket.title,
        priority=ticket.priority.value if hasattr(ticket.priority, 'value') else str(ticket.priority),
    )

    # Загрузка связей для ответа
    result = await session.execute(
        select(Ticket)
        .where(Ticket.id == ticket.id)
        .options(selectinload(Ticket.events), selectinload(Ticket.comments))  # type: ignore[arg-type]
    )
    ticket = result.scalar_one()
    return TicketRead.model_validate(ticket)


@router.get("/", response_model=TicketListResponse)
async def list_tickets(
    page: int = Query(default=1, ge=1, description="Номер страницы"),
    per_page: int = Query(default=20, ge=1, le=100, description="Записей на странице"),
    ticket_status: Optional[TicketStatus] = Query(
        default=None, alias="status", description="Фильтр по статусу"
    ),
    category: Optional[str] = Query(default=None, description="Фильтр по категории"),
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> TicketListResponse:
    """
    Список тикетов с пагинацией и фильтрацией.

    Параметры: ?page=1&per_page=20&status=new&category=access
    """
    # Базовый запрос
    query = select(Ticket)
    count_query = select(func.count()).select_from(Ticket)

    # Фильтры
    if ticket_status is not None:
        query = query.where(Ticket.status == ticket_status)
        count_query = count_query.where(Ticket.status == ticket_status)
    if category is not None:
        query = query.where(Ticket.category == category)
        count_query = count_query.where(Ticket.category == category)

    # Общее количество
    total_result = await session.execute(count_query)
    total = total_result.scalar_one()

    # Пагинация и сортировка
    offset = (page - 1) * per_page
    query = (
        query.order_by(Ticket.created_at.desc())  # type: ignore[union-attr]
        .offset(offset)
        .limit(per_page)
        .options(selectinload(Ticket.events), selectinload(Ticket.comments))  # type: ignore[arg-type]
    )

    result = await session.execute(query)
    tickets = result.scalars().all()

    return TicketListResponse(
        items=[TicketRead.model_validate(t) for t in tickets],
        total=total,
        page=page,
        per_page=per_page,
    )


@router.get("/{ticket_id}", response_model=TicketRead)
async def get_ticket(
    ticket_id: str,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> TicketRead:
    """Получить тикет по ID с событиями и комментариями."""
    result = await session.execute(
        select(Ticket)
        .where(Ticket.id == ticket_id)
        .options(selectinload(Ticket.events), selectinload(Ticket.comments))  # type: ignore[arg-type]
    )
    ticket = result.scalar_one_or_none()
    if not ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Тикет не найден",
        )
    return TicketRead.model_validate(ticket)


@router.post("/{ticket_id}/status", response_model=TicketRead)
async def update_ticket_status(
    ticket_id: str,
    payload: TicketStatusUpdate,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> TicketRead:
    """Обновить статус тикета. Актор определяется по JWT-токену."""
    result = await session.execute(
        select(Ticket)
        .where(Ticket.id == ticket_id)
        .options(selectinload(Ticket.events), selectinload(Ticket.comments))  # type: ignore[arg-type]
    )
    ticket = result.scalar_one_or_none()
    if not ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Тикет не найден",
        )

    old_status = ticket.status.value if hasattr(ticket.status, 'value') else str(ticket.status)

    try:
        event = ticket.transition(
            actor_id=str(current_user.id),
            new_status=payload.new_status,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    session.add(event)
    session.add(ticket)
    await session.commit()
    await session.refresh(ticket)

    # Email-уведомление создателю тикета
    creator = await session.execute(select(User).where(User.id == ticket.creator_id))
    creator_user = creator.scalar_one_or_none()
    if creator_user:
        new_status_val = payload.new_status.value if hasattr(payload.new_status, 'value') else str(payload.new_status)
        background_tasks.add_task(
            notify_ticket_status_changed,
            creator_email=creator_user.email,
            ticket_id=ticket.id,
            title=ticket.title,
            old_status=old_status,
            new_status=new_status_val,
            actor_name=current_user.full_name or current_user.email,
        )

    # Перезагрузка со связями
    result = await session.execute(
        select(Ticket)
        .where(Ticket.id == ticket.id)
        .options(selectinload(Ticket.events), selectinload(Ticket.comments))  # type: ignore[arg-type]
    )
    ticket = result.scalar_one()
    return TicketRead.model_validate(ticket)


@router.post("/{ticket_id}/comments", response_model=CommentRead, status_code=status.HTTP_201_CREATED)
async def add_comment(
    ticket_id: str,
    payload: CommentCreate,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> CommentRead:
    """Добавить комментарий к тикету. Автор определяется по JWT-токену."""
    result = await session.execute(select(Ticket).where(Ticket.id == ticket_id))
    ticket = result.scalar_one_or_none()
    if not ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Тикет не найден",
        )

    comment = TicketComment(
        ticket_id=ticket_id,
        author_id=str(current_user.id),
        author_name=current_user.full_name or "",
        text=payload.text,
    )
    session.add(comment)
    await session.commit()
    await session.refresh(comment)

    # Email-уведомление создателю тикета (если комментирует не он сам)
    if ticket.creator_id != str(current_user.id):
        creator = await session.execute(select(User).where(User.id == ticket.creator_id))
        creator_user = creator.scalar_one_or_none()
        if creator_user:
            background_tasks.add_task(
                notify_ticket_comment,
                creator_email=creator_user.email,
                title=ticket.title,
                comment_text=payload.text,
                author_name=current_user.full_name or current_user.email,
            )

    return CommentRead.model_validate(comment)


@router.delete("/{ticket_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def delete_ticket(
    ticket_id: str,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """
    Удалить тикет (только для администраторов).

    Выполняет полное удаление тикета вместе с событиями и комментариями.
    """
    # Проверка роли: только ADMIN может удалять
    from backend.auth.models import UserRole

    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Только администратор может удалять тикеты",
        )

    result = await session.execute(select(Ticket).where(Ticket.id == ticket_id))
    ticket = result.scalar_one_or_none()
    if not ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Тикет не найден",
        )

    # Удаляем связанные события и комментарии, затем сам тикет
    await session.execute(
        sa_delete(TicketEvent).where(TicketEvent.ticket_id == ticket_id)
    )
    await session.execute(
        sa_delete(TicketComment).where(TicketComment.ticket_id == ticket_id)
    )
    await session.delete(ticket)
    await session.commit()

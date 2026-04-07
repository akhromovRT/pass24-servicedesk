from __future__ import annotations

import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import delete as sa_delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlmodel import func, select

UPLOAD_DIR = Path("/app/data/attachments")
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
ALLOWED_TYPES = {
    "image/jpeg", "image/png", "image/gif", "image/webp",
    "application/pdf",
    "text/plain",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}

from pydantic import BaseModel

from backend.auth.dependencies import get_current_user
from backend.auth.models import User
from backend.database import get_session
from backend.notifications.email import (
    notify_ticket_comment,
    notify_ticket_created,
    notify_ticket_status_changed,
)

from .models import Attachment, Ticket, TicketComment, TicketEvent, TicketStatus
from .schemas import (
    AttachmentRead,
    CommentCreate,
    CommentRead,
    CsatSubmit,
    GuestTicketCreate,
    GuestTicketResponse,
    TicketAssignmentUpdate,
    TicketCreate,
    TicketListResponse,
    TicketPriorityUpdate,
    TicketRead,
    TicketStatusUpdate,
)


# Общий набор selectinload для тикетов
def _ticket_load_options():
    return [
        selectinload(Ticket.events),  # type: ignore[arg-type]
        selectinload(Ticket.comments),  # type: ignore[arg-type]
        selectinload(Ticket.attachments),  # type: ignore[arg-type]
    ]

router = APIRouter(prefix="/tickets", tags=["tickets"])


@router.post("/guest", response_model=GuestTicketResponse, status_code=status.HTTP_201_CREATED)
async def create_guest_ticket(
    payload: GuestTicketCreate,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
) -> GuestTicketResponse:
    """
    Создание тикета без авторизации — по email.

    Если email уже зарегистрирован → создаёт тикет от имени существующего пользователя.
    Если email новый → авто-регистрирует пользователя и создаёт тикет.
    """
    from backend.auth.models import User
    from backend.auth.utils import hash_password
    from backend.notifications.email import _send_email, notify_ticket_created
    import uuid as uuid_mod

    email = payload.email.strip().lower()

    # Ищем пользователя по email
    result = await session.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    is_new_user = False
    if not user:
        # Авто-регистрация
        temp_password = uuid_mod.uuid4().hex[:10]
        user = User(
            email=email,
            hashed_password=hash_password(temp_password),
            full_name=payload.name or email.split("@")[0],
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        is_new_user = True

    # Создаём тикет
    ticket = Ticket(
        creator_id=str(user.id),
        title=payload.title,
        description=payload.description,
        product=payload.product or "pass24_online",
        category=payload.category or "other",
        ticket_type=payload.ticket_type or "problem",
        source="web",
        object_name=payload.object_name,
        contact_name=payload.name or user.full_name,
        contact_email=email,
        contact_phone=payload.contact_phone,
        urgent=payload.urgent,
    )
    ticket.auto_detect_category()
    ticket.assign_priority_based_on_context()
    ticket.auto_assign_group()

    event = TicketEvent(
        ticket_id=ticket.id,
        actor_id=str(user.id),
        description="Тикет создан (гостевой)",
    )

    session.add(ticket)
    session.add(event)
    await session.commit()
    await session.refresh(ticket)

    # Автопривязка к статье БЗ, если клиент пришёл из неё
    if payload.source_article_slug:
        from backend.knowledge.models import Article
        from backend.tickets.templates import TicketArticleLink
        ar = await session.execute(select(Article).where(Article.slug == payload.source_article_slug))
        article = ar.scalar_one_or_none()
        if article:
            link = TicketArticleLink(
                ticket_id=ticket.id,
                article_id=str(article.id),
                relation_type="created_from",
                linked_by=str(user.id),
            )
            session.add(link)
            link_event = TicketEvent(
                ticket_id=ticket.id,
                actor_id=str(user.id),
                description=f"Клиент пришёл из статьи БЗ: «{article.title}» (не нашёл ответа)",
            )
            session.add(link_event)
            await session.commit()

    # Email: уведомление о тикете с полным контекстом
    background_tasks.add_task(
        notify_ticket_created,
        creator_email=email,
        ticket_id=ticket.id,
        title=ticket.title,
        priority=ticket.priority.value if hasattr(ticket.priority, 'value') else str(ticket.priority),
        description=ticket.description or "",
        product=ticket.product or "",
        ticket_type=ticket.ticket_type or "",
        object_name=ticket.object_name or "",
        access_point=ticket.access_point or "",
        contact_phone=ticket.contact_phone or "",
        sla_response_hours=ticket.sla_response_hours or 4,
        sla_resolve_hours=ticket.sla_resolve_hours or 24,
    )

    # Если новый пользователь — приветственное письмо
    if is_new_user:
        background_tasks.add_task(
            _send_email,
            to=email,
            subject="Добро пожаловать в PASS24 Service Desk",
            html_body=f"""
            <div style="font-family: -apple-system, Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                <div style="background: #0f172a; color: #f8fafc; padding: 16px 24px; border-radius: 8px 8px 0 0;">
                    <strong>PASS24 Service Desk</strong>
                </div>
                <div style="padding: 24px; background: #fff; border: 1px solid #e2e8f0; border-top: none; border-radius: 0 0 8px 8px;">
                    <h2 style="margin: 0 0 16px; color: #1e293b;">Добро пожаловать!</h2>
                    <p style="color: #475569;">Здравствуйте, {user.full_name}!</p>
                    <p style="color: #475569;">Ваша заявка <strong>«{ticket.title}»</strong> принята. Мы сообщим о ходе решения на этот email.</p>
                    <p style="color: #475569;">Все обновления по заявке будут приходить на <strong>{email}</strong>. Вы можете отвечать прямо на письма — ваш ответ будет добавлен как комментарий.</p>
                    <div style="background: #f8fafc; border-radius: 8px; padding: 16px; margin: 16px 0; border: 1px solid #e2e8f0;">
                        <p style="color: #334155; font-weight: 600; margin: 0 0 8px;">Хотите видеть все заявки на портале?</p>
                        <p style="color: #64748b; margin: 0;">Зарегистрируйтесь на портале Service Desk с этим же email — все ваши заявки уже будут привязаны к аккаунту.</p>
                    </div>
                </div>
            </div>
            """,
        )

    return GuestTicketResponse(
        ticket_id=ticket.id,
        title=ticket.title,
        status="new",
        auth_required=False,
    )


@router.post("/", response_model=TicketRead, status_code=status.HTTP_201_CREATED)
async def create_ticket(
    payload: TicketCreate,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> TicketRead:
    """Создать новый тикет.

    Автор определяется по JWT-токену. Агенты/админы могут указать
    on_behalf_of_email — в этом случае creator_id подставляется
    от имени клиента (создаётся пользователь если его нет).
    """
    from backend.auth.models import UserRole
    from backend.auth.utils import hash_password
    import uuid as uuid_mod

    # Кто реальный заявитель тикета
    creator_user = current_user
    creator_email_for_notify = current_user.email

    # Создание от имени клиента (только для агентов/админов)
    if payload.on_behalf_of_email and current_user.role in (UserRole.SUPPORT_AGENT, UserRole.ADMIN):
        target_email = payload.on_behalf_of_email.strip().lower()
        r = await session.execute(select(User).where(User.email == target_email))
        target = r.scalar_one_or_none()
        if target is None:
            target = User(
                email=target_email,
                hashed_password=hash_password(uuid_mod.uuid4().hex[:16]),
                full_name=(payload.on_behalf_of_name or target_email.split("@")[0]).strip(),
                role=UserRole.RESIDENT,
            )
            session.add(target)
            await session.commit()
            await session.refresh(target)
        creator_user = target
        creator_email_for_notify = target.email

    ticket = Ticket(
        creator_id=str(creator_user.id),
        title=payload.title,
        description=payload.description,
        product=payload.product or "pass24_online",
        category=payload.category or "other",
        ticket_type=payload.ticket_type or "problem",
        source=payload.source or "web",
        object_name=payload.object_name,
        object_address=payload.object_address,
        access_point=payload.access_point,
        contact_name=payload.contact_name or payload.on_behalf_of_name or creator_user.full_name,
        contact_email=creator_user.email,
        contact_phone=payload.contact_phone,
        company=payload.company,
        device_type=payload.device_type,
        app_version=payload.app_version,
        error_message=payload.error_message,
        urgent=payload.urgent,
        customer_id=payload.customer_id or (creator_user.customer_id if hasattr(creator_user, 'customer_id') else None),
    )
    ticket.auto_detect_category()
    ticket.assign_priority_based_on_context()
    ticket.auto_assign_group()

    # Событие создания (actor — тот, кто реально создал через UI)
    actor_desc = "Тикет создан"
    if creator_user.id != current_user.id:
        actor_desc = f"Тикет создан агентом {current_user.full_name or current_user.email} от имени клиента"
    event = TicketEvent(
        ticket_id=ticket.id,
        actor_id=str(current_user.id),
        description=actor_desc,
    )

    session.add(ticket)
    session.add(event)
    await session.commit()
    await session.refresh(ticket)

    # Если тикет создан ИЗ статьи БЗ — автопривязываем (relation_type='created_from')
    if payload.source_article_slug:
        from backend.knowledge.models import Article
        from backend.tickets.templates import TicketArticleLink
        ar = await session.execute(select(Article).where(Article.slug == payload.source_article_slug))
        article = ar.scalar_one_or_none()
        if article:
            link = TicketArticleLink(
                ticket_id=ticket.id,
                article_id=str(article.id),
                relation_type="created_from",
                linked_by=str(creator_user.id),
            )
            session.add(link)
            # Событие в историю
            link_event = TicketEvent(
                ticket_id=ticket.id,
                actor_id=str(creator_user.id),
                description=f"Клиент пришёл из статьи БЗ: «{article.title}» (не нашёл ответа)",
            )
            session.add(link_event)
            await session.commit()

    # Email-уведомление заявителю с полным контекстом
    background_tasks.add_task(
        notify_ticket_created,
        creator_email=creator_email_for_notify,
        ticket_id=ticket.id,
        title=ticket.title,
        priority=ticket.priority.value if hasattr(ticket.priority, 'value') else str(ticket.priority),
        description=ticket.description or "",
        product=ticket.product or "",
        ticket_type=ticket.ticket_type or "",
        object_name=ticket.object_name or "",
        access_point=ticket.access_point or "",
        contact_phone=ticket.contact_phone or "",
        sla_response_hours=ticket.sla_response_hours or 4,
        sla_resolve_hours=ticket.sla_resolve_hours or 24,
    )

    # Загрузка связей для ответа
    result = await session.execute(
        select(Ticket)
        .where(Ticket.id == ticket.id)
        .options(*_ticket_load_options())
    )
    ticket = result.scalar_one()
    return TicketRead.model_validate(ticket)


@router.get("/", response_model=TicketListResponse)
async def list_tickets(
    page: int = Query(default=1, ge=1, description="Номер страницы"),
    per_page: int = Query(default=20, ge=1, le=100, description="Записей на странице"),
    ticket_status: Optional[str] = Query(
        default=None, alias="status", description="Фильтр по статусу (через запятую: new,in_progress)"
    ),
    category: Optional[str] = Query(default=None, description="Фильтр по категории (через запятую)"),
    product: Optional[str] = Query(default=None, description="Фильтр по продукту (через запятую)"),
    ticket_type: Optional[str] = Query(default=None, alias="type", description="Фильтр по типу (через запятую)"),
    creator_id: Optional[str] = Query(default=None, description="Фильтр по создателю"),
    my: Optional[bool] = Query(default=None, description="Только мои тикеты"),
    q: Optional[str] = Query(default=None, description="Поиск по теме, описанию, email, объекту"),
    view: Optional[str] = Query(default=None, description="Saved view: open/overdue/urgent/waiting/closed"),
    sort: Optional[str] = Query(default=None, description="Сортировка: created_desc, created_asc, updated_desc, priority_desc"),
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> TicketListResponse:
    """
    Список тикетов с пагинацией и фильтрацией.

    Параметры: ?page=1&per_page=20&status=new&category=access&object_id=obj1&my=true
    """
    from backend.auth.models import UserRole

    # Базовый запрос
    query = select(Ticket)
    count_query = select(func.count()).select_from(Ticket)

    # Резиденты и УК видят только свои тикеты
    if current_user.role not in (UserRole.SUPPORT_AGENT, UserRole.ADMIN):
        query = query.where(Ticket.creator_id == str(current_user.id))
        count_query = count_query.where(Ticket.creator_id == str(current_user.id))

    # Фильтры (поддержка нескольких значений через запятую)
    if ticket_status:
        vals = [v.strip() for v in ticket_status.split(",") if v.strip()]
        if len(vals) == 1:
            query = query.where(Ticket.status == vals[0])
            count_query = count_query.where(Ticket.status == vals[0])
        elif vals:
            query = query.where(Ticket.status.in_(vals))
            count_query = count_query.where(Ticket.status.in_(vals))
    if category:
        vals = [v.strip() for v in category.split(",") if v.strip()]
        if len(vals) == 1:
            query = query.where(Ticket.category == vals[0])
            count_query = count_query.where(Ticket.category == vals[0])
        elif vals:
            query = query.where(Ticket.category.in_(vals))
            count_query = count_query.where(Ticket.category.in_(vals))
    if product:
        vals = [v.strip() for v in product.split(",") if v.strip()]
        if len(vals) == 1:
            query = query.where(Ticket.product == vals[0])
            count_query = count_query.where(Ticket.product == vals[0])
        elif vals:
            query = query.where(Ticket.product.in_(vals))
            count_query = count_query.where(Ticket.product.in_(vals))
    if ticket_type:
        vals = [v.strip() for v in ticket_type.split(",") if v.strip()]
        if len(vals) == 1:
            query = query.where(Ticket.ticket_type == vals[0])
            count_query = count_query.where(Ticket.ticket_type == vals[0])
        elif vals:
            query = query.where(Ticket.ticket_type.in_(vals))
            count_query = count_query.where(Ticket.ticket_type.in_(vals))
    if creator_id is not None:
        query = query.where(Ticket.creator_id == creator_id)
        count_query = count_query.where(Ticket.creator_id == creator_id)
    if my:
        query = query.where(Ticket.creator_id == str(current_user.id))
        count_query = count_query.where(Ticket.creator_id == str(current_user.id))

    # Saved views (пресеты)
    from datetime import timedelta
    now = datetime.utcnow()
    if view == "open":
        open_statuses = ["new", "in_progress", "waiting_for_user", "on_hold", "engineer_visit"]
        query = query.where(Ticket.status.in_(open_statuses))
        count_query = count_query.where(Ticket.status.in_(open_statuses))
    elif view == "urgent":
        open_statuses = ["new", "in_progress", "waiting_for_user", "on_hold", "engineer_visit"]
        query = query.where(
            Ticket.status.in_(open_statuses)
            & ((Ticket.priority == "critical") | (Ticket.priority == "CRITICAL") | (Ticket.urgent == True))  # noqa: E712
        )
        count_query = count_query.where(
            Ticket.status.in_(open_statuses)
            & ((Ticket.priority == "critical") | (Ticket.priority == "CRITICAL") | (Ticket.urgent == True))  # noqa: E712
        )
    elif view == "overdue":
        # Просроченные: open + (first_response_at IS NULL AND created_at + sla_response_hours < now)
        # упрощённо: статус открыт и с даты создания прошло больше sla_resolve_hours часов
        open_statuses = ["new", "in_progress", "waiting_for_user", "on_hold", "engineer_visit"]
        query = query.where(
            Ticket.status.in_(open_statuses) & (Ticket.sla_breached == True)  # noqa: E712
        )
        count_query = count_query.where(
            Ticket.status.in_(open_statuses) & (Ticket.sla_breached == True)  # noqa: E712
        )
    elif view == "waiting":
        query = query.where(Ticket.status == "waiting_for_user")
        count_query = count_query.where(Ticket.status == "waiting_for_user")
    elif view == "engineer_visit":
        query = query.where(Ticket.status == "engineer_visit")
        count_query = count_query.where(Ticket.status == "engineer_visit")
    elif view == "closed":
        query = query.where(Ticket.status.in_(["resolved", "closed"]))
        count_query = count_query.where(Ticket.status.in_(["resolved", "closed"]))

    # Поиск по тексту
    if q and q.strip():
        pattern = f"%{q.strip()}%"
        search_cond = (
            Ticket.title.ilike(pattern)
            | Ticket.description.ilike(pattern)
            | Ticket.contact_email.ilike(pattern)
            | Ticket.contact_name.ilike(pattern)
            | Ticket.object_name.ilike(pattern)
        )
        query = query.where(search_cond)
        count_query = count_query.where(search_cond)

    # Общее количество
    total_result = await session.execute(count_query)
    total = total_result.scalar_one()

    # Умная сортировка: SLA breach → critical → urgent → по дате
    from sqlalchemy import case
    priority_order = case(
        (Ticket.priority == "critical", 0),
        (Ticket.priority == "CRITICAL", 0),
        (Ticket.priority == "high", 1),
        (Ticket.priority == "HIGH", 1),
        (Ticket.priority == "normal", 2),
        (Ticket.priority == "NORMAL", 2),
        (Ticket.priority == "low", 3),
        (Ticket.priority == "LOW", 3),
        else_=4,
    )
    status_order = case(
        (Ticket.status == "new", 0),
        (Ticket.status == "engineer_visit", 1),
        (Ticket.status == "in_progress", 2),
        (Ticket.status == "on_hold", 3),
        (Ticket.status == "waiting_for_user", 4),
        (Ticket.status == "resolved", 5),
        (Ticket.status == "closed", 6),
        else_=7,
    )

    # Пагинация и сортировка
    offset = (page - 1) * per_page
    if sort == "created_asc":
        query = query.order_by(Ticket.created_at.asc())
    elif sort == "created_desc":
        query = query.order_by(Ticket.created_at.desc())
    elif sort == "updated_desc":
        query = query.order_by(Ticket.updated_at.desc())
    elif sort == "priority_desc":
        query = query.order_by(priority_order, Ticket.created_at.desc())
    else:
        # По умолчанию: smart-сортировка для агентов
        query = query.order_by(
            Ticket.sla_breached.desc(),  # просроченные первыми
            status_order,                 # открытые первыми
            priority_order,               # critical → low
            Ticket.created_at.desc(),     # свежие первыми
        )
    query = (
        query
        .offset(offset)
        .limit(per_page)
        .options(*_ticket_load_options())
    )

    result = await session.execute(query)
    tickets = result.scalars().all()

    return TicketListResponse(
        items=[TicketRead.model_validate(t) for t in tickets],
        total=total,
        page=page,
        per_page=per_page,
    )


@router.get("/stats")
async def get_ticket_stats(
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Статистика по заявкам для dashboard-карточек."""
    from backend.auth.models import UserRole

    open_statuses = ["new", "in_progress", "waiting_for_user", "on_hold", "engineer_visit"]

    # Базовый фильтр: резиденты/УК видят только свои
    base_filter = None
    if current_user.role not in (UserRole.SUPPORT_AGENT, UserRole.ADMIN):
        base_filter = Ticket.creator_id == str(current_user.id)

    def count_where(*conditions):
        q = select(func.count()).select_from(Ticket)
        if base_filter is not None:
            q = q.where(base_filter)
        for c in conditions:
            q = q.where(c)
        return q

    # Открытые
    r = await session.execute(count_where(Ticket.status.in_(open_statuses)))
    open_count = r.scalar_one()

    # Просроченные
    r = await session.execute(count_where(
        Ticket.status.in_(open_statuses),
        Ticket.sla_breached == True,  # noqa: E712
    ))
    overdue_count = r.scalar_one()

    # Ждут ответа клиента
    r = await session.execute(count_where(Ticket.status == "waiting_for_user"))
    waiting_count = r.scalar_one()

    # Срочные (critical или urgent)
    r = await session.execute(count_where(
        Ticket.status.in_(open_statuses),
        ((Ticket.priority == "critical") | (Ticket.priority == "CRITICAL") | (Ticket.urgent == True)),  # noqa: E712
    ))
    urgent_count = r.scalar_one()

    # Новые (без первого ответа)
    r = await session.execute(count_where(
        Ticket.status == "new",
        Ticket.first_response_at == None,  # noqa: E711
    ))
    new_count = r.scalar_one()

    # Всего
    r = await session.execute(count_where())
    total_count = r.scalar_one()

    return {
        "total": total_count,
        "open": open_count,
        "overdue": overdue_count,
        "waiting": waiting_count,
        "urgent": urgent_count,
        "new": new_count,
    }


@router.get("/notifications/unread")
async def get_unread_notifications(
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Список тикетов с непрочитанными ответами клиента (для агентов/админов)."""
    from backend.auth.models import UserRole
    if current_user.role not in (UserRole.SUPPORT_AGENT, UserRole.ADMIN):
        return {"count": 0, "items": []}

    result = await session.execute(
        select(Ticket)
        .where(Ticket.has_unread_reply == True)  # noqa: E712
        .order_by(Ticket.updated_at.desc())
        .limit(20)
    )
    tickets = result.scalars().all()
    count_result = await session.execute(
        select(func.count()).select_from(Ticket).where(Ticket.has_unread_reply == True)  # noqa: E712
    )
    total = count_result.scalar_one()

    return {
        "count": total,
        "items": [
            {
                "id": t.id,
                "title": t.title,
                "status": t.status.value if hasattr(t.status, 'value') else str(t.status),
                "priority": t.priority.value if hasattr(t.priority, 'value') else str(t.priority),
                "contact_name": t.contact_name,
                "contact_email": t.contact_email,
                "updated_at": t.updated_at.isoformat(),
            }
            for t in tickets
        ],
    }


@router.get("/{ticket_id}", response_model=TicketRead)
async def get_ticket(
    ticket_id: str,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> TicketRead:
    """Получить тикет по ID с событиями, комментариями и вложениями."""
    from backend.auth.models import UserRole

    result = await session.execute(
        select(Ticket)
        .where(Ticket.id == ticket_id)
        .options(*_ticket_load_options())
    )
    ticket = result.scalar_one_or_none()
    if not ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Тикет не найден",
        )

    # Агент открыл тикет → сбрасываем флаг unread
    if current_user.role in (UserRole.SUPPORT_AGENT, UserRole.ADMIN) and ticket.has_unread_reply:
        ticket.has_unread_reply = False
        session.add(ticket)
        await session.commit()
        await session.refresh(ticket)

    ticket_data = TicketRead.model_validate(ticket)
    # Скрыть внутренние комментарии от обычных пользователей
    if current_user.role not in (UserRole.SUPPORT_AGENT, UserRole.ADMIN):
        ticket_data.comments = [c for c in ticket_data.comments if not c.is_internal]
    return ticket_data


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
        .options(*_ticket_load_options())
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

    # Уведомление создателю тикета (Telegram или email по источнику)
    creator = await session.execute(select(User).where(User.id == ticket.creator_id))
    creator_user = creator.scalar_one_or_none()
    if creator_user:
        new_status_val = payload.new_status.value if hasattr(payload.new_status, 'value') else str(payload.new_status)
        if ticket.source == "telegram" and creator_user.telegram_chat_id:
            from backend.notifications.telegram import notify_telegram_status
            background_tasks.add_task(
                notify_telegram_status,
                chat_id=creator_user.telegram_chat_id,
                ticket_id=ticket.id,
                ticket_title=ticket.title,
                old_status=old_status,
                new_status=new_status_val,
            )
        else:
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
        .options(*_ticket_load_options())
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

    # Внутренние комментарии — только для агентов и админов
    from backend.auth.models import UserRole
    is_staff = current_user.role in (UserRole.SUPPORT_AGENT, UserRole.ADMIN)
    is_internal = payload.is_internal and is_staff

    comment = TicketComment(
        ticket_id=ticket_id,
        author_id=str(current_user.id),
        author_name=current_user.full_name or "",
        text=payload.text,
        is_internal=is_internal,
    )
    session.add(comment)

    # Авто-переход статуса + флаг unread
    if not is_internal:
        if is_staff:
            # Первый ответ агента → переводим в работу (агент сам решит когда ждать ответа)
            if ticket.status == TicketStatus.NEW:
                try:
                    event = ticket.transition(
                        actor_id=str(current_user.id),
                        new_status=TicketStatus.IN_PROGRESS,
                    )
                    session.add(event)
                except ValueError:
                    pass
            ticket.has_unread_reply = False  # агент обработал
        else:
            # Клиент ответил → агентам нужно работать
            if ticket.status == TicketStatus.WAITING_FOR_USER:
                try:
                    event = ticket.transition(
                        actor_id=str(current_user.id),
                        new_status=TicketStatus.IN_PROGRESS,
                    )
                    session.add(event)
                except ValueError:
                    pass
            ticket.has_unread_reply = True
        session.add(ticket)

    await session.commit()
    await session.refresh(comment)

    # Уведомление создателю тикета (если комментирует не он сам и не внутренний)
    if not is_internal and ticket.creator_id != str(current_user.id):
        creator = await session.execute(select(User).where(User.id == ticket.creator_id))
        creator_user = creator.scalar_one_or_none()
        if creator_user:
            # Telegram — если источник Telegram и есть chat_id
            if (ticket.source == "telegram"
                    and creator_user.telegram_chat_id):
                from backend.notifications.telegram import notify_telegram_comment
                background_tasks.add_task(
                    notify_telegram_comment,
                    chat_id=creator_user.telegram_chat_id,
                    ticket_id=ticket.id,
                    ticket_title=ticket.title,
                    comment_text=payload.text,
                    author_name=current_user.full_name or current_user.email,
                )
            else:
                # Email — для всех остальных источников
                background_tasks.add_task(
                    notify_ticket_comment,
                    creator_email=creator_user.email,
                    ticket_id=ticket.id,
                    title=ticket.title,
                    comment_text=payload.text,
                    author_name=current_user.full_name or current_user.email,
                )

    return CommentRead.model_validate(comment)


@router.post("/{ticket_id}/attachments", response_model=AttachmentRead, status_code=status.HTTP_201_CREATED)
async def upload_attachment(
    ticket_id: str,
    file: UploadFile,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> AttachmentRead:
    """Загрузить вложение к тикету. Макс. 10 МБ."""
    result = await session.execute(select(Ticket).where(Ticket.id == ticket_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Тикет не найден")

    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Недопустимый тип файла")

    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Файл слишком большой (макс. 10 МБ)")

    # Сохранение на диск
    file_id = str(uuid.uuid4())
    ext = Path(file.filename or "file").suffix
    storage_path = f"{ticket_id}/{file_id}{ext}"
    full_path = UPLOAD_DIR / storage_path
    full_path.parent.mkdir(parents=True, exist_ok=True)
    full_path.write_bytes(content)

    attachment = Attachment(
        ticket_id=ticket_id,
        uploader_id=str(current_user.id),
        filename=file.filename or "file",
        content_type=file.content_type or "application/octet-stream",
        size=len(content),
        storage_path=storage_path,
    )
    session.add(attachment)
    await session.commit()
    await session.refresh(attachment)
    return AttachmentRead.model_validate(attachment)


@router.get("/{ticket_id}/attachments/{attachment_id}")
async def download_attachment(
    ticket_id: str,
    attachment_id: str,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Скачать вложение."""
    result = await session.execute(
        select(Attachment).where(Attachment.id == attachment_id, Attachment.ticket_id == ticket_id)
    )
    attachment = result.scalar_one_or_none()
    if not attachment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Вложение не найдено")

    file_path = UPLOAD_DIR / attachment.storage_path
    if not file_path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Файл не найден на сервере")

    return FileResponse(
        path=str(file_path),
        filename=attachment.filename,
        media_type=attachment.content_type,
    )


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


# ---------------------------------------------------------------------------
# ITIL: Impact / Urgency / Assignment
# ---------------------------------------------------------------------------


@router.put("/{ticket_id}/priority", response_model=TicketRead)
async def update_priority(
    ticket_id: str,
    payload: TicketPriorityUpdate,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> TicketRead:
    """Ручное изменение impact/urgency (только для агентов). Priority пересчитывается из матрицы."""
    from backend.auth.models import UserRole
    if current_user.role not in (UserRole.SUPPORT_AGENT, UserRole.ADMIN):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Только агент может менять приоритет")

    result = await session.execute(
        select(Ticket).where(Ticket.id == ticket_id).options(*_ticket_load_options())
    )
    ticket = result.scalar_one_or_none()
    if not ticket:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Тикет не найден")

    ticket.impact = payload.impact
    ticket.urgency = payload.urgency
    ticket.recalculate_priority()
    ticket.updated_at = datetime.utcnow()

    event = TicketEvent(
        ticket_id=ticket.id,
        actor_id=str(current_user.id),
        description=f"Приоритет пересчитан: impact={payload.impact}, urgency={payload.urgency} → {ticket.priority.value}",
    )
    session.add(event)
    session.add(ticket)
    await session.commit()
    await session.refresh(ticket)
    return TicketRead.model_validate(ticket)


@router.put("/{ticket_id}/assignment", response_model=TicketRead)
async def update_assignment(
    ticket_id: str,
    payload: TicketAssignmentUpdate,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> TicketRead:
    """Назначение группы / агента на тикет (только для агентов)."""
    from backend.auth.models import UserRole
    if current_user.role not in (UserRole.SUPPORT_AGENT, UserRole.ADMIN):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Только агент может назначать")

    result = await session.execute(
        select(Ticket).where(Ticket.id == ticket_id).options(*_ticket_load_options())
    )
    ticket = result.scalar_one_or_none()
    if not ticket:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Тикет не найден")

    changes = []
    if payload.assignment_group is not None and ticket.assignment_group != payload.assignment_group:
        ticket.assignment_group = payload.assignment_group
        changes.append(f"группа: {payload.assignment_group}")
    if payload.assignee_id is not None and ticket.assignee_id != payload.assignee_id:
        ticket.assignee_id = payload.assignee_id or None
        changes.append(f"агент: {payload.assignee_id or 'снят'}")

    if changes:
        ticket.updated_at = datetime.utcnow()
        event = TicketEvent(
            ticket_id=ticket.id,
            actor_id=str(current_user.id),
            description=f"Назначение: {', '.join(changes)}",
        )
        session.add(event)
        session.add(ticket)
        await session.commit()
        await session.refresh(ticket)

    return TicketRead.model_validate(ticket)


@router.get("/{ticket_id}/rate", include_in_schema=False)
async def rate_via_link(
    ticket_id: str,
    r: int = Query(..., ge=1, le=5, description="Оценка 1-5"),
    session: AsyncSession = Depends(get_session),
):
    """Один клик оценки из письма — возвращает HTML-страницу с благодарностью.

    Если оценка уже стоит — показываем её без изменений (без ошибки).
    """
    from fastapi.responses import HTMLResponse

    EMOJI_MAP = {1: "😞", 2: "😐", 3: "🙂", 4: "😀", 5: "🤩"}
    RATING_LABELS = {1: "Плохо", 2: "Так себе", 3: "Нормально", 4: "Хорошо", 5: "Отлично"}

    result = await session.execute(select(Ticket).where(Ticket.id == ticket_id))
    ticket = result.scalar_one_or_none()

    emoji = EMOJI_MAP.get(r, "⭐")
    label = RATING_LABELS.get(r, "")

    if ticket is None:
        message_title = "Заявка не найдена"
        message_body = "Возможно, ссылка устарела или заявка была удалена."
        success = False
    elif ticket.satisfaction_submitted_at is not None:
        # Уже оценено — показываем текущую оценку
        already_emoji = EMOJI_MAP.get(ticket.satisfaction_rating or 0, "⭐")
        message_title = "Спасибо, оценка уже сохранена"
        message_body = f"Вы оценили эту заявку: {already_emoji}"
        success = True
    else:
        ticket.satisfaction_rating = r
        ticket.satisfaction_submitted_at = datetime.utcnow()
        session.add(ticket)
        await session.commit()
        message_title = "Спасибо за обратную связь!"
        message_body = f"Ваша оценка: {emoji} {label}. Она поможет нам стать лучше."
        success = True

    color = "#10b981" if success else "#ef4444"

    html = f"""<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>PASS24 Service Desk — оценка</title>
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            background: linear-gradient(135deg, #f0f9ff 0%, #e0f2fe 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }}
        .card {{
            background: white;
            border-radius: 16px;
            box-shadow: 0 10px 40px rgba(15, 23, 42, 0.1);
            padding: 40px 32px;
            max-width: 480px;
            width: 100%;
            text-align: center;
        }}
        .brand {{
            background: linear-gradient(135deg, #ef4444, #991b1b);
            color: white;
            font-weight: 700;
            font-size: 12px;
            padding: 4px 10px;
            border-radius: 6px;
            display: inline-block;
            margin-bottom: 24px;
            letter-spacing: 0.5px;
        }}
        .big-emoji {{ font-size: 72px; line-height: 1; margin-bottom: 16px; animation: pop 0.4s ease-out; }}
        @keyframes pop {{
            0% {{ transform: scale(0.5); opacity: 0; }}
            60% {{ transform: scale(1.1); opacity: 1; }}
            100% {{ transform: scale(1); }}
        }}
        h1 {{ font-size: 22px; font-weight: 600; color: {color}; margin-bottom: 12px; }}
        p {{ color: #475569; font-size: 15px; line-height: 1.6; }}
        .footer {{ margin-top: 28px; padding-top: 20px; border-top: 1px solid #e2e8f0; font-size: 13px; color: #94a3b8; }}
        .footer a {{ color: #3b82f6; text-decoration: none; font-weight: 500; }}
    </style>
</head>
<body>
    <div class="card">
        <span class="brand">PASS24 SERVICE DESK</span>
        <div class="big-emoji">{emoji}</div>
        <h1>{message_title}</h1>
        <p>{message_body}</p>
        <div class="footer">
            Можете закрыть эту страницу или <a href="https://support.pass24pro.ru/">перейти к заявкам</a>
        </div>
    </div>
</body>
</html>"""

    return HTMLResponse(content=html, status_code=200)


# =====================================================================
# Agents list, Bulk actions, CSV export, Dashboard, Merge, Macros
# =====================================================================

@router.get("/agents/list")
async def list_agents(
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Список агентов поддержки (для назначения)."""
    from backend.auth.models import UserRole
    if current_user.role not in (UserRole.SUPPORT_AGENT, UserRole.ADMIN):
        raise HTTPException(status_code=403, detail="Только для агентов")
    r = await session.execute(
        select(User).where(
            User.role.in_([UserRole.SUPPORT_AGENT, UserRole.ADMIN]),
            User.is_active == True,  # noqa: E712
        ).order_by(User.full_name)
    )
    return [
        {"id": str(u.id), "full_name": u.full_name, "email": u.email, "role": u.role.value if hasattr(u.role, 'value') else str(u.role)}
        for u in r.scalars()
    ]


class BulkActionPayload(BaseModel):
    ticket_ids: list[str]
    action: str  # "status" | "assign" | "delete"
    value: Optional[str] = None  # новый статус / id агента


@router.post("/bulk")
async def bulk_action(
    payload: BulkActionPayload,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Массовые действия на выбранных тикетах (агент/админ)."""
    from backend.auth.models import UserRole
    if current_user.role not in (UserRole.SUPPORT_AGENT, UserRole.ADMIN):
        raise HTTPException(status_code=403, detail="Только для агентов")
    if not payload.ticket_ids:
        return {"updated": 0}

    r = await session.execute(select(Ticket).where(Ticket.id.in_(payload.ticket_ids)))
    tickets = list(r.scalars())
    updated = 0
    now = datetime.utcnow()

    for t in tickets:
        if payload.action == "status" and payload.value:
            try:
                new_status = TicketStatus(payload.value)
                event = t.transition(actor_id=str(current_user.id), new_status=new_status)
                session.add(event)
                updated += 1
            except (ValueError, Exception):
                pass
        elif payload.action == "assign":
            t.assignee_id = payload.value or None
            t.updated_at = now
            event = TicketEvent(
                ticket_id=t.id,
                actor_id=str(current_user.id),
                description=f"Массовое назначение: {payload.value or 'снят'}",
            )
            session.add(event)
            session.add(t)
            updated += 1
        elif payload.action == "delete" and current_user.role == UserRole.ADMIN:
            from sqlalchemy import delete as sa_delete
            await session.execute(sa_delete(Attachment).where(Attachment.ticket_id == t.id))
            await session.execute(sa_delete(TicketComment).where(TicketComment.ticket_id == t.id))
            await session.execute(sa_delete(TicketEvent).where(TicketEvent.ticket_id == t.id))
            await session.delete(t)
            updated += 1

    await session.commit()
    return {"updated": updated}


@router.get("/export.csv", include_in_schema=False)
async def export_tickets_csv(
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Экспорт тикетов в CSV (агент/админ)."""
    from backend.auth.models import UserRole
    from fastapi.responses import StreamingResponse
    import csv
    import io

    if current_user.role not in (UserRole.SUPPORT_AGENT, UserRole.ADMIN):
        raise HTTPException(status_code=403, detail="Только для агентов")

    r = await session.execute(
        select(Ticket).order_by(Ticket.created_at.desc()).limit(10000)
    )
    tickets = list(r.scalars())

    buf = io.StringIO()
    buf.write("\ufeff")  # BOM для Excel
    w = csv.writer(buf, delimiter=";")
    w.writerow([
        "ID", "Создано", "Статус", "Приоритет", "Тема", "Клиент email",
        "Клиент имя", "Продукт", "Категория", "Объект", "SLA нарушен",
        "Первый ответ", "Решено", "Оценка",
    ])
    for t in tickets:
        w.writerow([
            t.id[:8],
            t.created_at.strftime("%Y-%m-%d %H:%M") if t.created_at else "",
            t.status.value if hasattr(t.status, 'value') else str(t.status),
            t.priority.value if hasattr(t.priority, 'value') else str(t.priority),
            t.title,
            t.contact_email or "",
            t.contact_name or "",
            t.product or "",
            t.category or "",
            t.object_name or "",
            "да" if t.sla_breached else "",
            t.first_response_at.strftime("%Y-%m-%d %H:%M") if t.first_response_at else "",
            t.resolved_at.strftime("%Y-%m-%d %H:%M") if t.resolved_at else "",
            t.satisfaction_rating or "",
        ])

    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename=tickets-{datetime.utcnow().strftime('%Y%m%d')}.csv"},
    )


@router.get("/dashboard/me")
async def agent_dashboard(
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Персональный дашборд агента."""
    from backend.auth.models import UserRole
    if current_user.role not in (UserRole.SUPPORT_AGENT, UserRole.ADMIN):
        raise HTTPException(status_code=403, detail="Только для агентов")

    agent_id = str(current_user.id)
    # Мои назначенные
    assigned = await session.execute(
        select(func.count()).select_from(Ticket).where(Ticket.assignee_id == agent_id)
    )
    assigned_total = assigned.scalar_one()

    # По статусам
    open_st = await session.execute(
        select(func.count()).select_from(Ticket)
        .where(Ticket.assignee_id == agent_id, Ticket.status.in_(["new", "in_progress", "waiting_for_user", "on_hold", "engineer_visit"]))
    )
    open_count = open_st.scalar_one()

    # Решённые мной за последние 30 дней
    from datetime import timedelta
    since = datetime.utcnow() - timedelta(days=30)
    resolved_r = await session.execute(
        select(func.count()).select_from(Ticket)
        .where(Ticket.assignee_id == agent_id, Ticket.resolved_at.is_not(None), Ticket.resolved_at >= since)
    )
    resolved_30d = resolved_r.scalar_one()

    # Среднее CSAT
    csat_r = await session.execute(
        select(func.avg(Ticket.satisfaction_rating)).where(
            Ticket.assignee_id == agent_id,
            Ticket.satisfaction_rating.is_not(None),
        )
    )
    avg_csat = csat_r.scalar_one()

    return {
        "assigned_total": assigned_total,
        "open": open_count,
        "resolved_30d": resolved_30d,
        "avg_csat": round(float(avg_csat), 2) if avg_csat else None,
    }


class MergePayload(BaseModel):
    target_ticket_id: str  # тикет, в который сливаем


@router.post("/{ticket_id}/merge", response_model=TicketRead)
async def merge_ticket(
    ticket_id: str,
    payload: MergePayload,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> TicketRead:
    """Сливает тикет в другой (current → target). Агент/админ."""
    from backend.auth.models import UserRole
    if current_user.role not in (UserRole.SUPPORT_AGENT, UserRole.ADMIN):
        raise HTTPException(status_code=403, detail="Только для агентов")
    if ticket_id == payload.target_ticket_id:
        raise HTTPException(status_code=400, detail="Нельзя слить тикет сам в себя")

    r = await session.execute(select(Ticket).where(Ticket.id == ticket_id))
    source = r.scalar_one_or_none()
    r2 = await session.execute(select(Ticket).where(Ticket.id == payload.target_ticket_id).options(*_ticket_load_options()))
    target = r2.scalar_one_or_none()
    if not source or not target:
        raise HTTPException(status_code=404, detail="Тикет не найден")

    # Переносим комментарии, вложения, события
    from sqlalchemy import update as sa_update
    await session.execute(
        sa_update(TicketComment).where(TicketComment.ticket_id == source.id).values(ticket_id=target.id)
    )
    await session.execute(
        sa_update(Attachment).where(Attachment.ticket_id == source.id).values(ticket_id=target.id)
    )

    # Закрываем source с пометкой
    source.merged_into_ticket_id = target.id
    source.status = TicketStatus.CLOSED
    source.updated_at = datetime.utcnow()
    session.add(source)

    # Событие в target
    merge_event = TicketEvent(
        ticket_id=target.id,
        actor_id=str(current_user.id),
        description=f"В тикет слит дубликат #{source.id[:8]} ({source.title})",
    )
    session.add(merge_event)
    close_event = TicketEvent(
        ticket_id=source.id,
        actor_id=str(current_user.id),
        description=f"Слит в #{target.id[:8]}",
    )
    session.add(close_event)

    await session.commit()
    await session.refresh(target)

    # Перечитываем target со связями
    r3 = await session.execute(select(Ticket).where(Ticket.id == target.id).options(*_ticket_load_options()))
    return TicketRead.model_validate(r3.scalar_one())


class ApplyMacroPayload(BaseModel):
    macro_id: str


@router.post("/{ticket_id}/apply-macro", response_model=TicketRead)
async def apply_macro(
    ticket_id: str,
    payload: ApplyMacroPayload,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Применяет макрос к тикету: статус + комментарий + назначение."""
    from backend.auth.models import UserRole
    from backend.tickets.templates import Macro
    import json as json_mod

    if current_user.role not in (UserRole.SUPPORT_AGENT, UserRole.ADMIN):
        raise HTTPException(status_code=403, detail="Только для агентов")

    # Загружаем макрос
    mr = await session.execute(select(Macro).where(Macro.id == payload.macro_id))
    macro = mr.scalar_one_or_none()
    if not macro:
        raise HTTPException(status_code=404, detail="Макрос не найден")
    actions = json_mod.loads(macro.actions)

    # Загружаем тикет
    r = await session.execute(select(Ticket).where(Ticket.id == ticket_id).options(*_ticket_load_options()))
    ticket = r.scalar_one_or_none()
    if not ticket:
        raise HTTPException(status_code=404, detail="Тикет не найден")

    # Применяем действия
    if actions.get("comment"):
        comment = TicketComment(
            ticket_id=ticket.id,
            author_id=str(current_user.id),
            author_name=current_user.full_name or "",
            text=actions["comment"],
            is_internal=bool(actions.get("is_internal_comment")),
        )
        session.add(comment)

    if actions.get("assign_self"):
        ticket.assignee_id = str(current_user.id)
        event = TicketEvent(
            ticket_id=ticket.id,
            actor_id=str(current_user.id),
            description="Назначен себе (макрос)",
        )
        session.add(event)

    if actions.get("assignment_group"):
        ticket.assignment_group = actions["assignment_group"]

    if actions.get("status"):
        try:
            event = ticket.transition(
                actor_id=str(current_user.id),
                new_status=TicketStatus(actions["status"]),
            )
            session.add(event)
        except (ValueError, Exception):
            pass

    session.add(ticket)
    await session.commit()
    await session.refresh(ticket)

    # Перечитываем со связями
    r = await session.execute(select(Ticket).where(Ticket.id == ticket.id).options(*_ticket_load_options()))
    return TicketRead.model_validate(r.scalar_one())


@router.post("/{ticket_id}/satisfaction", response_model=TicketRead)
async def submit_satisfaction(
    ticket_id: str,
    payload: CsatSubmit,
    session: AsyncSession = Depends(get_session),
) -> TicketRead:
    """Отправка оценки удовлетворённости клиентом (публичный endpoint)."""
    result = await session.execute(
        select(Ticket).where(Ticket.id == ticket_id).options(*_ticket_load_options())
    )
    ticket = result.scalar_one_or_none()
    if not ticket:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Тикет не найден")

    if ticket.satisfaction_submitted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Оценка уже отправлена",
        )

    ticket.satisfaction_rating = payload.rating
    ticket.satisfaction_comment = payload.comment
    ticket.satisfaction_submitted_at = datetime.utcnow()
    session.add(ticket)
    await session.commit()
    await session.refresh(ticket)
    return TicketRead.model_validate(ticket)

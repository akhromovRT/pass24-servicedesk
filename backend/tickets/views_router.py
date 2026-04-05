"""API для Saved Views + KB links + parent-child связей тикетов."""
from __future__ import annotations

import json
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select, func

from backend.auth.dependencies import get_current_user
from backend.auth.models import User, UserRole
from backend.database import get_session

from .models import Ticket
from .templates import KbImprovementSuggestion, SavedView, TicketArticleLink

router = APIRouter(prefix="/tickets", tags=["views"])


# ========================================================================
# Saved Views
# ========================================================================


class SavedViewCreate(BaseModel):
    name: str = Field(..., max_length=128)
    icon: Optional[str] = Field(default=None, max_length=64)
    filters: dict = Field(..., description="Объект фильтров")
    is_shared: bool = False
    sort_order: int = 0


class SavedViewRead(BaseModel):
    id: str
    name: str
    icon: Optional[str]
    filters: dict
    owner_id: str
    is_shared: bool
    sort_order: int
    usage_count: int
    created_at: datetime


@router.get("/saved-views", response_model=List[SavedViewRead])
async def list_saved_views(
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> List[SavedViewRead]:
    """Список saved views: личные + shared от других агентов."""
    # Личные + расшаренные
    result = await session.execute(
        select(SavedView)
        .where((SavedView.owner_id == str(current_user.id)) | (SavedView.is_shared == True))  # noqa: E712
        .order_by(SavedView.sort_order, SavedView.created_at.desc())
    )
    views = result.scalars().all()
    return [
        SavedViewRead(
            id=v.id,
            name=v.name,
            icon=v.icon,
            filters=json.loads(v.filters),
            owner_id=v.owner_id,
            is_shared=v.is_shared,
            sort_order=v.sort_order,
            usage_count=v.usage_count,
            created_at=v.created_at,
        )
        for v in views
    ]


@router.post("/saved-views", response_model=SavedViewRead, status_code=status.HTTP_201_CREATED)
async def create_saved_view(
    payload: SavedViewCreate,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> SavedViewRead:
    """Создать saved view."""
    view = SavedView(
        name=payload.name,
        icon=payload.icon,
        filters=json.dumps(payload.filters, ensure_ascii=False),
        owner_id=str(current_user.id),
        is_shared=payload.is_shared,
        sort_order=payload.sort_order,
    )
    session.add(view)
    await session.commit()
    await session.refresh(view)
    return SavedViewRead(
        id=view.id, name=view.name, icon=view.icon, filters=payload.filters,
        owner_id=view.owner_id, is_shared=view.is_shared, sort_order=view.sort_order,
        usage_count=view.usage_count, created_at=view.created_at,
    )


@router.delete("/saved-views/{view_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def delete_saved_view(
    view_id: str,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Удалить saved view (только владелец)."""
    result = await session.execute(select(SavedView).where(SavedView.id == view_id))
    view = result.scalar_one_or_none()
    if not view:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="View не найден")
    if view.owner_id != str(current_user.id) and current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Нельзя удалить чужой view")
    await session.delete(view)
    await session.commit()


@router.post("/saved-views/{view_id}/use", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def use_saved_view(
    view_id: str,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(get_current_user),
):
    """Инкрементировать usage_count (вызывать при применении view)."""
    result = await session.execute(select(SavedView).where(SavedView.id == view_id))
    view = result.scalar_one_or_none()
    if view:
        view.usage_count += 1
        session.add(view)
        await session.commit()


# ========================================================================
# KB Article links (тикет ↔ статья)
# ========================================================================


class ArticleLinkCreate(BaseModel):
    article_id: str
    relation_type: str = Field(default="helped", description="helped / related / created_from")


class ArticleLinkRead(BaseModel):
    id: str
    ticket_id: str
    article_id: str
    article_title: Optional[str] = None
    article_slug: Optional[str] = None
    relation_type: str
    linked_by: str
    created_at: datetime


@router.get("/{ticket_id}/articles", response_model=List[ArticleLinkRead])
async def list_ticket_articles(
    ticket_id: str,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(get_current_user),
) -> List[ArticleLinkRead]:
    """Список статей БЗ, привязанных к тикету."""
    from backend.knowledge.models import Article

    result = await session.execute(
        select(TicketArticleLink).where(TicketArticleLink.ticket_id == ticket_id)
        .order_by(TicketArticleLink.created_at.desc())
    )
    links = result.scalars().all()

    # Загружаем заголовки статей
    enriched = []
    for link in links:
        art_res = await session.execute(select(Article).where(Article.id == link.article_id))
        art = art_res.scalar_one_or_none()
        enriched.append(ArticleLinkRead(
            id=link.id,
            ticket_id=link.ticket_id,
            article_id=link.article_id,
            article_title=art.title if art else None,
            article_slug=art.slug if art else None,
            relation_type=link.relation_type,
            linked_by=link.linked_by,
            created_at=link.created_at,
        ))
    return enriched


@router.post("/{ticket_id}/articles", response_model=ArticleLinkRead, status_code=status.HTTP_201_CREATED)
async def link_article_to_ticket(
    ticket_id: str,
    payload: ArticleLinkCreate,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ArticleLinkRead:
    """Привязать статью БЗ к тикету."""
    if current_user.role not in (UserRole.SUPPORT_AGENT, UserRole.ADMIN):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Только агент может привязывать статьи")

    # Проверяем существование тикета
    t_res = await session.execute(select(Ticket).where(Ticket.id == ticket_id))
    if not t_res.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Тикет не найден")

    # Проверяем что такой связи ещё нет
    exists = await session.execute(
        select(TicketArticleLink).where(
            TicketArticleLink.ticket_id == ticket_id,
            TicketArticleLink.article_id == payload.article_id,
        )
    )
    if exists.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Статья уже привязана")

    link = TicketArticleLink(
        ticket_id=ticket_id,
        article_id=payload.article_id,
        relation_type=payload.relation_type,
        linked_by=str(current_user.id),
    )
    session.add(link)
    await session.commit()
    await session.refresh(link)

    from backend.knowledge.models import Article
    art_res = await session.execute(select(Article).where(Article.id == link.article_id))
    art = art_res.scalar_one_or_none()

    return ArticleLinkRead(
        id=link.id,
        ticket_id=link.ticket_id,
        article_id=link.article_id,
        article_title=art.title if art else None,
        article_slug=art.slug if art else None,
        relation_type=link.relation_type,
        linked_by=link.linked_by,
        created_at=link.created_at,
    )


@router.delete("/{ticket_id}/articles/{link_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def unlink_article(
    ticket_id: str,
    link_id: str,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Отвязать статью от тикета."""
    if current_user.role not in (UserRole.SUPPORT_AGENT, UserRole.ADMIN):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Только агент")

    result = await session.execute(select(TicketArticleLink).where(TicketArticleLink.id == link_id))
    link = result.scalar_one_or_none()
    if not link or link.ticket_id != ticket_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Связь не найдена")
    await session.delete(link)
    await session.commit()


# ========================================================================
# Article stats (кто помогает чаще всего)
# ========================================================================


@router.get("/articles/stats")
async def articles_stats(
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Топ статей БЗ по использованию в тикетах (для агентов/админов)."""
    if current_user.role not in (UserRole.SUPPORT_AGENT, UserRole.ADMIN):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)

    from backend.knowledge.models import Article

    result = await session.execute(
        select(
            TicketArticleLink.article_id,
            func.count(TicketArticleLink.id).label("count"),
        )
        .where(TicketArticleLink.relation_type == "helped")
        .group_by(TicketArticleLink.article_id)
        .order_by(func.count(TicketArticleLink.id).desc())
        .limit(20)
    )
    rows = result.all()

    items = []
    for row in rows:
        art_res = await session.execute(select(Article).where(Article.id == row.article_id))
        art = art_res.scalar_one_or_none()
        items.append({
            "article_id": row.article_id,
            "article_title": art.title if art else "(удалена)",
            "article_slug": art.slug if art else None,
            "helped_count": row.count,
        })
    return {"items": items}


# ========================================================================
# Parent-Child (Incident → Problem)
# ========================================================================


class LinkToParentRequest(BaseModel):
    parent_ticket_id: str


@router.put("/{ticket_id}/parent", response_model=dict)
async def link_to_parent(
    ticket_id: str,
    payload: LinkToParentRequest,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Привязать тикет к родительскому (Problem)."""
    if current_user.role not in (UserRole.SUPPORT_AGENT, UserRole.ADMIN):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Только агент")

    if ticket_id == payload.parent_ticket_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Нельзя привязать к самому себе")

    # Проверяем оба тикета
    result = await session.execute(select(Ticket).where(Ticket.id == ticket_id))
    ticket = result.scalar_one_or_none()
    if not ticket:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Тикет не найден")

    parent_res = await session.execute(select(Ticket).where(Ticket.id == payload.parent_ticket_id))
    parent = parent_res.scalar_one_or_none()
    if not parent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Родительский тикет не найден")

    ticket.parent_ticket_id = payload.parent_ticket_id
    ticket.updated_at = datetime.utcnow()
    session.add(ticket)
    await session.commit()

    return {"ticket_id": ticket.id, "parent_ticket_id": payload.parent_ticket_id}


@router.delete("/{ticket_id}/parent", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def unlink_parent(
    ticket_id: str,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Отвязать тикет от родителя."""
    if current_user.role not in (UserRole.SUPPORT_AGENT, UserRole.ADMIN):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Только агент")

    result = await session.execute(select(Ticket).where(Ticket.id == ticket_id))
    ticket = result.scalar_one_or_none()
    if not ticket:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Тикет не найден")
    ticket.parent_ticket_id = None
    ticket.updated_at = datetime.utcnow()
    session.add(ticket)
    await session.commit()


class BulkLinkToParentRequest(BaseModel):
    ticket_ids: List[str] = Field(..., min_length=1)
    parent_ticket_id: str


@router.post("/bulk-link-to-parent", response_model=dict)
async def bulk_link_to_parent(
    payload: BulkLinkToParentRequest,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Массовое привязывание тикетов к родителю (Problem)."""
    if current_user.role not in (UserRole.SUPPORT_AGENT, UserRole.ADMIN):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Только агент")

    # Исключаем сам parent из списка
    ids = [tid for tid in payload.ticket_ids if tid != payload.parent_ticket_id]
    if not ids:
        return {"updated": 0}

    # Проверяем существование parent
    parent_res = await session.execute(select(Ticket).where(Ticket.id == payload.parent_ticket_id))
    if not parent_res.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Родительский тикет не найден")

    from sqlalchemy import update
    now = datetime.utcnow()
    await session.execute(
        update(Ticket)
        .where(Ticket.id.in_(ids))
        .values(parent_ticket_id=payload.parent_ticket_id, updated_at=now)
    )
    await session.commit()
    return {"updated": len(ids), "parent_ticket_id": payload.parent_ticket_id}


@router.get("/{ticket_id}/children", response_model=dict)
async def list_children(
    ticket_id: str,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(get_current_user),
) -> dict:
    """Дочерние тикеты (Incidents для этого Problem)."""
    result = await session.execute(
        select(Ticket)
        .where(Ticket.parent_ticket_id == ticket_id)
        .order_by(Ticket.created_at.desc())
    )
    children = result.scalars().all()
    return {
        "count": len(children),
        "items": [
            {
                "id": c.id,
                "title": c.title,
                "status": c.status.value if hasattr(c.status, 'value') else str(c.status),
                "priority": c.priority.value if hasattr(c.priority, 'value') else str(c.priority),
                "created_at": c.created_at.isoformat(),
            }
            for c in children
        ],
    }


# ========================================================================
# KB Improvement Suggestions
# ========================================================================


class ImprovementCreate(BaseModel):
    article_id: str
    suggestion: str = Field(..., min_length=10, max_length=4000)


class ImprovementStatusUpdate(BaseModel):
    status: str = Field(..., pattern=r"^(applied|rejected|pending)$")


@router.post("/{ticket_id}/kb-improvement", status_code=status.HTTP_201_CREATED)
async def suggest_kb_improvement(
    ticket_id: str,
    payload: ImprovementCreate,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Предложить улучшение статьи БЗ на основе тикета."""
    if current_user.role not in (UserRole.SUPPORT_AGENT, UserRole.ADMIN):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)

    t_res = await session.execute(select(Ticket).where(Ticket.id == ticket_id))
    if not t_res.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Тикет не найден")

    sug = KbImprovementSuggestion(
        ticket_id=ticket_id,
        article_id=payload.article_id,
        suggestion=payload.suggestion,
        suggested_by=str(current_user.id),
    )
    session.add(sug)
    await session.commit()
    await session.refresh(sug)

    return {
        "id": sug.id,
        "status": sug.status,
        "created_at": sug.created_at.isoformat(),
    }


@router.get("/kb-improvements/pending")
async def list_pending_improvements(
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Список предложений по улучшению БЗ в статусе pending (для агентов/админов)."""
    if current_user.role not in (UserRole.SUPPORT_AGENT, UserRole.ADMIN):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)

    from backend.knowledge.models import Article

    res = await session.execute(
        select(KbImprovementSuggestion)
        .where(KbImprovementSuggestion.status == "pending")
        .order_by(KbImprovementSuggestion.created_at.desc())
    )
    items = []
    for sug in res.scalars():
        art_res = await session.execute(select(Article).where(Article.id == sug.article_id))
        art = art_res.scalar_one_or_none()
        items.append({
            "id": sug.id,
            "article_id": sug.article_id,
            "article_title": art.title if art else "(удалена)",
            "article_slug": art.slug if art else None,
            "ticket_id": sug.ticket_id,
            "suggestion": sug.suggestion,
            "suggested_by": sug.suggested_by,
            "created_at": sug.created_at.isoformat(),
        })
    return {"count": len(items), "items": items}


@router.put("/kb-improvements/{suggestion_id}/status")
async def update_improvement_status(
    suggestion_id: str,
    payload: ImprovementStatusUpdate,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Обновить статус предложения (admin)."""
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Только admin")

    r = await session.execute(select(KbImprovementSuggestion).where(KbImprovementSuggestion.id == suggestion_id))
    sug = r.scalar_one_or_none()
    if not sug:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    sug.status = payload.status
    if payload.status in ("applied", "rejected"):
        sug.resolved_at = datetime.utcnow()
    session.add(sug)
    await session.commit()
    return {"id": sug.id, "status": sug.status}

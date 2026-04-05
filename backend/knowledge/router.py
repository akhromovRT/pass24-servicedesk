from __future__ import annotations

import re
import unicodedata
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text as sa_text
from sqlmodel import func, select

from backend.auth.dependencies import get_current_user, require_role
from backend.auth.models import User, UserRole
from backend.database import get_session

from .models import Article, ArticleCategory, ArticleFeedback, ArticleType
from .schemas import (
    ArticleCreate,
    ArticleListResponse,
    ArticleRead,
    ArticleUpdate,
    FeedbackCreate,
    FeedbackResponse,
)

router = APIRouter(prefix="/knowledge", tags=["knowledge"])

# Таблица транслитерации кириллицы в латиницу
_TRANSLIT_MAP: dict[str, str] = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e",
    "ё": "yo", "ж": "zh", "з": "z", "и": "i", "й": "y", "к": "k",
    "л": "l", "м": "m", "н": "n", "о": "o", "п": "p", "р": "r",
    "с": "s", "т": "t", "у": "u", "ф": "f", "х": "kh", "ц": "ts",
    "ч": "ch", "ш": "sh", "щ": "shch", "ъ": "", "ы": "y", "ь": "",
    "э": "e", "ю": "yu", "я": "ya",
}


def _slugify(text: str) -> str:
    """
    Генерирует slug из заголовка.

    Транслитерирует кириллицу в латиницу, приводит к нижнему регистру,
    заменяет пробелы и спецсимволы на дефисы.
    """
    text = text.lower()

    # Транслитерация кириллицы
    result: list[str] = []
    for char in text:
        if char in _TRANSLIT_MAP:
            result.append(_TRANSLIT_MAP[char])
        else:
            result.append(char)
    text = "".join(result)

    # Нормализация Unicode (диакритика и пр.)
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")

    # Замена не-алфанумерных символов на дефисы
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = text.strip("-")

    return text


async def _build_article_read(article: Article, session: AsyncSession) -> ArticleRead:
    """Собирает ArticleRead с именем автора из БД."""
    result = await session.execute(select(User).where(User.id == article.author_id))
    author = result.scalar_one_or_none()
    author_name = author.full_name if author else "Неизвестный автор"

    return ArticleRead(
        id=article.id,
        title=article.title,
        slug=article.slug,
        category=article.category,
        article_type=article.article_type,
        content=article.content,
        is_published=article.is_published,
        views_count=article.views_count,
        helpful_count=article.helpful_count,
        not_helpful_count=article.not_helpful_count,
        author_id=article.author_id,
        author_name=author_name,
        created_at=article.created_at,
        updated_at=article.updated_at,
    )


@router.get("/", response_model=ArticleListResponse)
async def list_articles(
    page: int = Query(default=1, ge=1, description="Номер страницы"),
    per_page: int = Query(default=20, ge=1, le=100, description="Статей на страницу"),
    category: Optional[ArticleCategory] = Query(default=None, description="Фильтр по категории"),
    article_type: Optional[ArticleType] = Query(default=None, alias="type", description="Тип: faq или guide"),
    session: AsyncSession = Depends(get_session),
) -> ArticleListResponse:
    """Список опубликованных статей с пагинацией и фильтрацией."""
    # Базовый запрос — только опубликованные
    query = select(Article).where(Article.is_published == True)  # noqa: E712
    count_query = select(func.count()).select_from(Article).where(Article.is_published == True)  # noqa: E712

    if article_type is not None:
        query = query.where(Article.article_type == article_type)
        count_query = count_query.where(Article.article_type == article_type)
    if category is not None:
        query = query.where(Article.category == category)
        count_query = count_query.where(Article.category == category)

    # Общее количество
    total_result = await session.execute(count_query)
    total = total_result.scalar_one()

    # Пагинация
    offset = (page - 1) * per_page
    query = query.order_by(Article.created_at.desc()).offset(offset).limit(per_page)

    result = await session.execute(query)
    articles = result.scalars().all()

    items = [await _build_article_read(a, session) for a in articles]

    return ArticleListResponse(
        items=items,
        total=total,
        page=page,
        per_page=per_page,
    )


@router.get("/search", response_model=ArticleListResponse)
async def search_articles(
    query: str = Query(..., min_length=1, description="Поисковый запрос"),
    category: Optional[ArticleCategory] = Query(default=None, description="Фильтр по категории"),
    article_type: Optional[ArticleType] = Query(default=None, alias="type", description="Тип: faq или guide"),
    page: int = Query(default=1, ge=1, description="Номер страницы"),
    per_page: int = Query(default=20, ge=1, le=100, description="Статей на страницу"),
    session: AsyncSession = Depends(get_session),
) -> ArticleListResponse:
    """
    Полнотекстовый поиск по статьям базы знаний.

    Использует PostgreSQL FTS (to_tsvector/to_tsquery) с ранжированием.
    Fallback на ILIKE если FTS не даёт результатов.
    """
    # FTS-фильтр
    fts_condition = sa_text(
        "to_tsvector('russian', coalesce(title, '') || ' ' || coalesce(content, '')) "
        "@@ plainto_tsquery('russian', :query)"
    ).bindparams(query=query)

    base_filter = (Article.is_published == True) & fts_condition  # noqa: E712

    stmt = select(Article).where(base_filter)
    count_stmt = select(func.count()).select_from(Article).where(base_filter)

    if article_type is not None:
        stmt = stmt.where(Article.article_type == article_type)
        count_stmt = count_stmt.where(Article.article_type == article_type)
    if category is not None:
        stmt = stmt.where(Article.category == category)
        count_stmt = count_stmt.where(Article.category == category)

    # Общее количество
    total_result = await session.execute(count_stmt)
    total = total_result.scalar_one()

    # Если FTS не дал результатов — fallback на ILIKE
    if total == 0:
        search_pattern = f"%{query}%"
        ilike_filter = (
            (Article.is_published == True)  # noqa: E712
            & (Article.title.ilike(search_pattern) | Article.content.ilike(search_pattern))
        )
        stmt = select(Article).where(ilike_filter)
        count_stmt = select(func.count()).select_from(Article).where(ilike_filter)
        if article_type is not None:
            stmt = stmt.where(Article.article_type == article_type)
            count_stmt = count_stmt.where(Article.article_type == article_type)
        if category is not None:
            stmt = stmt.where(Article.category == category)
            count_stmt = count_stmt.where(Article.category == category)
        total_result = await session.execute(count_stmt)
        total = total_result.scalar_one()

    # Пагинация и ранжирование
    offset = (page - 1) * per_page
    stmt = stmt.order_by(Article.created_at.desc()).offset(offset).limit(per_page)

    result = await session.execute(stmt)
    articles = result.scalars().all()

    items = [await _build_article_read(a, session) for a in articles]

    return ArticleListResponse(
        items=items,
        total=total,
        page=page,
        per_page=per_page,
    )


@router.get("/stats/deflection")
async def deflection_stats(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Статистика deflection: топ статей по helpful, underperforming, created_from.

    Доступна только support_agent и admin.
    """
    if current_user.role not in (UserRole.SUPPORT_AGENT, UserRole.ADMIN):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Только для агентов")

    from backend.tickets.templates import TicketArticleLink

    # Топ статей по helpful_ratio (минимум 3 feedback для релевантности)
    top_helpful_result = await session.execute(
        select(Article)
        .where(Article.is_published == True, (Article.helpful_count + Article.not_helpful_count) >= 3)  # noqa: E712
        .order_by(
            (Article.helpful_count * 1.0 / func.nullif(Article.helpful_count + Article.not_helpful_count, 0)).desc(),
            Article.helpful_count.desc(),
        )
        .limit(10)
    )
    top_helpful = top_helpful_result.scalars().all()

    # Underperforming: много просмотров + низкий helpful_ratio + много created_from
    created_from_counts = await session.execute(
        select(
            TicketArticleLink.article_id,
            func.count(TicketArticleLink.id).label("ticket_anyway_count"),
        )
        .where(TicketArticleLink.relation_type == "created_from")
        .group_by(TicketArticleLink.article_id)
        .order_by(func.count(TicketArticleLink.id).desc())
        .limit(10)
    )
    underperforming = []
    for row in created_from_counts.all():
        art_res = await session.execute(select(Article).where(Article.id == row.article_id))
        art = art_res.scalar_one_or_none()
        if art:
            total_fb = art.helpful_count + art.not_helpful_count
            ratio = art.helpful_count / total_fb if total_fb > 0 else None
            underperforming.append({
                "article_id": str(art.id),
                "title": art.title,
                "slug": art.slug,
                "views_count": art.views_count,
                "helpful_count": art.helpful_count,
                "not_helpful_count": art.not_helpful_count,
                "helpful_ratio": round(ratio, 2) if ratio is not None else None,
                "ticket_anyway_count": row.ticket_anyway_count,
            })

    # Totals
    totals_result = await session.execute(
        select(
            func.coalesce(func.sum(Article.helpful_count), 0).label("helpful"),
            func.coalesce(func.sum(Article.not_helpful_count), 0).label("not_helpful"),
            func.coalesce(func.sum(Article.views_count), 0).label("views"),
        ).where(Article.is_published == True)  # noqa: E712
    )
    totals_row = totals_result.one()

    created_from_total_result = await session.execute(
        select(func.count(TicketArticleLink.id)).where(TicketArticleLink.relation_type == "created_from")
    )
    created_from_total = created_from_total_result.scalar_one()

    return {
        "totals": {
            "views": totals_row.views,
            "helpful_count": totals_row.helpful,
            "not_helpful_count": totals_row.not_helpful,
            "helpful_ratio": round(
                totals_row.helpful / (totals_row.helpful + totals_row.not_helpful), 2
            ) if (totals_row.helpful + totals_row.not_helpful) > 0 else None,
            "ticket_created_from_article": created_from_total,
        },
        "top_helpful": [
            {
                "article_id": str(a.id),
                "title": a.title,
                "slug": a.slug,
                "helpful_count": a.helpful_count,
                "not_helpful_count": a.not_helpful_count,
                "helpful_ratio": round(
                    a.helpful_count / (a.helpful_count + a.not_helpful_count), 2
                ) if (a.helpful_count + a.not_helpful_count) > 0 else None,
            }
            for a in top_helpful
        ],
        "underperforming": underperforming,
    }


@router.post("/{article_id}/feedback", response_model=FeedbackResponse)
async def submit_feedback(
    article_id: uuid.UUID,
    payload: FeedbackCreate,
    session: AsyncSession = Depends(get_session),
) -> FeedbackResponse:
    """Отправка feedback по статье (помогла/не помогла + опциональный комментарий).

    Не требует авторизации. Ограничение: один отзыв с одной сессии (session_id
    из localStorage) на статью. При повторной попытке возвращает recorded=False.
    """
    # Проверяем статью
    result = await session.execute(select(Article).where(Article.id == article_id))
    article = result.scalar_one_or_none()
    if article is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Статья не найдена")

    # Проверяем уникальность session_id + article_id
    existing_result = await session.execute(
        select(ArticleFeedback).where(
            ArticleFeedback.session_id == payload.session_id,
            ArticleFeedback.article_id == str(article.id),
        )
    )
    existing = existing_result.scalar_one_or_none()
    if existing is not None:
        return FeedbackResponse(
            article_id=article.id,
            helpful_count=article.helpful_count,
            not_helpful_count=article.not_helpful_count,
            recorded=False,
        )

    # Создаём feedback + инкрементим денормализованный counter
    feedback = ArticleFeedback(
        article_id=str(article.id),
        session_id=payload.session_id,
        user_id=None,  # опционально: прокинуть из auth dep в будущем
        helpful=payload.helpful,
        comment=payload.comment,
        source=payload.source,
    )
    if payload.helpful:
        article.helpful_count += 1
    else:
        article.not_helpful_count += 1

    session.add(feedback)
    session.add(article)
    await session.commit()
    await session.refresh(article)

    return FeedbackResponse(
        article_id=article.id,
        helpful_count=article.helpful_count,
        not_helpful_count=article.not_helpful_count,
        recorded=True,
    )


@router.get("/{slug}", response_model=ArticleRead)
async def get_article(
    slug: str,
    session: AsyncSession = Depends(get_session),
) -> ArticleRead:
    """Получение статьи по slug. Увеличивает счётчик просмотров."""
    result = await session.execute(
        select(Article).where(Article.slug == slug, Article.is_published == True)  # noqa: E712
    )
    article = result.scalar_one_or_none()

    if article is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Статья не найдена",
        )

    # Инкремент счётчика просмотров
    article.views_count += 1
    session.add(article)
    await session.commit()
    await session.refresh(article)

    return await _build_article_read(article, session)


@router.post("/", response_model=ArticleRead, status_code=status.HTTP_201_CREATED)
async def create_article(
    payload: ArticleCreate,
    current_user: User = Depends(require_role(UserRole.SUPPORT_AGENT, UserRole.ADMIN)),
    session: AsyncSession = Depends(get_session),
) -> ArticleRead:
    """Создание новой статьи. Доступно только агентам поддержки и администраторам."""
    slug = _slugify(payload.title)

    # Проверяем уникальность slug, при необходимости добавляем суффикс
    existing = await session.execute(select(Article).where(Article.slug == slug))
    if existing.scalar_one_or_none() is not None:
        slug = f"{slug}-{uuid.uuid4().hex[:8]}"

    article = Article(
        title=payload.title,
        slug=slug,
        category=payload.category,
        article_type=payload.article_type,
        content=payload.content,
        is_published=payload.is_published,
        author_id=current_user.id,
    )

    session.add(article)
    await session.commit()
    await session.refresh(article)

    return await _build_article_read(article, session)


@router.put("/{article_id}", response_model=ArticleRead)
async def update_article(
    article_id: uuid.UUID,
    payload: ArticleUpdate,
    current_user: User = Depends(require_role(UserRole.SUPPORT_AGENT, UserRole.ADMIN)),
    session: AsyncSession = Depends(get_session),
) -> ArticleRead:
    """Обновление статьи. Доступно только агентам поддержки и администраторам."""
    result = await session.execute(select(Article).where(Article.id == article_id))
    article = result.scalar_one_or_none()

    if article is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Статья не найдена",
        )

    update_data = payload.model_dump(exclude_unset=True)

    # Если обновляется заголовок — пересоздаём slug
    if "title" in update_data:
        new_slug = _slugify(update_data["title"])
        # Проверяем уникальность slug (кроме текущей статьи)
        existing = await session.execute(
            select(Article).where(Article.slug == new_slug, Article.id != article_id)
        )
        if existing.scalar_one_or_none() is not None:
            new_slug = f"{new_slug}-{uuid.uuid4().hex[:8]}"
        update_data["slug"] = new_slug

    for field_name, value in update_data.items():
        setattr(article, field_name, value)

    article.updated_at = datetime.utcnow()

    session.add(article)
    await session.commit()
    await session.refresh(article)

    return await _build_article_read(article, session)


@router.delete("/{article_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def delete_article(
    article_id: uuid.UUID,
    current_user: User = Depends(require_role(UserRole.ADMIN)),
    session: AsyncSession = Depends(get_session),
):
    """Удаление статьи. Доступно только администраторам."""
    result = await session.execute(select(Article).where(Article.id == article_id))
    article = result.scalar_one_or_none()

    if article is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Статья не найдена",
        )

    await session.delete(article)
    await session.commit()

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

from .models import Article, ArticleCategory, ArticleType
from .schemas import ArticleCreate, ArticleListResponse, ArticleRead, ArticleUpdate

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

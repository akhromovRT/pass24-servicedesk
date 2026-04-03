from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from .models import ArticleCategory, ArticleType


class ArticleCreate(BaseModel):
    """Схема создания новой статьи."""

    title: str = Field(..., max_length=512, description="Заголовок статьи")
    category: ArticleCategory = Field(..., description="Категория статьи")
    content: str = Field(..., description="Содержимое статьи (Markdown)")
    article_type: ArticleType = Field(default=ArticleType.FAQ, description="Тип: faq или guide")
    is_published: bool = Field(default=True, description="Опубликована ли статья")


class ArticleUpdate(BaseModel):
    """Схема обновления статьи. Все поля опциональны."""

    title: Optional[str] = Field(default=None, max_length=512, description="Заголовок статьи")
    category: Optional[ArticleCategory] = Field(default=None, description="Категория статьи")
    content: Optional[str] = Field(default=None, description="Содержимое статьи (Markdown)")
    is_published: Optional[bool] = Field(default=None, description="Опубликована ли статья")


class ArticleRead(BaseModel):
    """Схема ответа с данными статьи."""

    id: uuid.UUID
    title: str
    slug: str
    category: ArticleCategory
    article_type: ArticleType
    content: str
    is_published: bool
    views_count: int
    author_id: uuid.UUID
    author_name: str = Field(description="Имя автора статьи")
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ArticleListResponse(BaseModel):
    """Пагинированный список статей."""

    items: list[ArticleRead]
    total: int
    page: int
    per_page: int


class ArticleSearch(BaseModel):
    """Параметры поиска по базе знаний."""

    query: str = Field(..., min_length=1, description="Поисковый запрос")
    category: Optional[ArticleCategory] = Field(
        default=None, description="Фильтр по категории"
    )

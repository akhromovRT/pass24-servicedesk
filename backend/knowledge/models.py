from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum

from sqlmodel import Column, Field, Index, SQLModel, String


class ArticleType(str, Enum):
    """Тип статьи: FAQ (база знаний) или guide (инструкция)."""

    FAQ = "faq"
    GUIDE = "guide"


class ArticleCategory(str, Enum):
    """Категории статей базы знаний."""

    ACCESS = "access"  # Проблемы с доступом (двери, домофоны, барьеры)
    PASS = "pass"  # Управление пропусками
    GATE = "gate"  # Шлагбаумы и ворота
    APP = "app"  # Использование мобильного приложения
    NOTIFICATIONS = "notifications"  # Настройки уведомлений
    GENERAL = "general"  # Общие вопросы и устранение неполадок


class Article(SQLModel, table=True):
    """Таблица статей базы знаний."""

    __tablename__ = "articles"
    __table_args__ = (
        Index("ix_articles_category_published", "category", "is_published"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    title: str = Field(max_length=512, index=True)
    slug: str = Field(max_length=512, unique=True, index=True)
    category: ArticleCategory = Field(
        default=ArticleCategory.GENERAL,
        sa_column=Column(String, index=True),
    )
    article_type: ArticleType = Field(
        default=ArticleType.FAQ,
        sa_column=Column(String, index=True, default="faq"),
    )
    content: str = Field(description="Содержимое статьи в формате Markdown")
    is_published: bool = Field(default=True, index=True)
    views_count: int = Field(default=0)
    author_id: uuid.UUID = Field(foreign_key="users.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

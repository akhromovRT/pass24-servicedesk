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
    helpful_count: int = Field(default=0, description="Количество 👍 feedback")
    not_helpful_count: int = Field(default=0, description="Количество 👎 feedback")
    author_id: uuid.UUID = Field(foreign_key="users.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class ArticleFeedback(SQLModel, table=True):
    """Фидбэк пользователя по статье: помогла / не помогла.

    Уникальный индекс по (session_id, article_id) гарантирует один отзыв
    с одной сессии на статью. Для user'ов без аккаунта session_id —
    UUID из localStorage браузера.
    """

    __tablename__ = "article_feedback"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    article_id: str = Field(index=True)
    session_id: str = Field(max_length=64, description="UUID сессии из localStorage")
    user_id: str | None = Field(default=None, description="User.id если авторизован")
    helpful: bool = Field(description="True = помогла, False = не помогла")
    comment: str | None = Field(default=None, max_length=500)
    source: str = Field(default="web", max_length=16, description="web / email / telegram")
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)

"""Модели шаблонов ответов и макросов."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class ResponseTemplate(SQLModel, table=True):
    """Шаблон ответа агента — для быстрой вставки в комментарий."""

    __tablename__ = "response_templates"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    name: str = Field(max_length=256)
    body: str = Field(max_length=4000)
    category: Optional[str] = Field(default=None, max_length=64)
    author_id: str = Field(index=True)
    is_shared: bool = Field(default=True)
    usage_count: int = Field(default=0)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Macro(SQLModel, table=True):
    """Макрос — набор действий, применяемых одним кликом."""

    __tablename__ = "macros"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    name: str = Field(max_length=256)
    icon: Optional[str] = Field(default=None, max_length=64)
    # JSON: { "status": "in_progress", "comment": "...", "assign_self": true }
    actions: str
    author_id: str
    is_shared: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class SavedView(SQLModel, table=True):
    """Сохранённый набор фильтров для списка тикетов."""

    __tablename__ = "saved_views"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    name: str = Field(max_length=128)
    icon: Optional[str] = Field(default=None, max_length=64)
    # JSON: { "status": ["new","in_progress"], "category": [...], "q": "...", "view": "open" }
    filters: str
    owner_id: str = Field(index=True)
    is_shared: bool = Field(default=False, description="Виден всем агентам")
    sort_order: int = Field(default=0)
    usage_count: int = Field(default=0)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class TicketArticleLink(SQLModel, table=True):
    """Связь тикета со статьёй базы знаний (m2m)."""

    __tablename__ = "ticket_article_links"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    ticket_id: str = Field(foreign_key="tickets.id", index=True)
    article_id: str = Field(index=True)
    # 'helped' (помогла решить), 'related' (связана), 'created_from' (создана из этого тикета)
    relation_type: str = Field(default="helped", max_length=32)
    linked_by: str = Field(description="user_id того кто привязал")
    created_at: datetime = Field(default_factory=datetime.utcnow)


class KbImprovementSuggestion(SQLModel, table=True):
    """Предложение по улучшению статьи БЗ — создаётся агентом на основе тикета.

    Когда клиент пришёл из статьи БЗ и задал вопрос, ответ на который
    должен был быть в этой статье, — агент после решения тикета может
    предложить улучшение. Коллективная доработка базы знаний.
    """

    __tablename__ = "kb_improvement_suggestions"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    article_id: str = Field(index=True)
    ticket_id: str
    suggestion: str = Field(max_length=4000)
    suggested_by: str
    status: str = Field(default="pending", max_length=32, index=True)
    # pending — ждёт review; applied — применено; rejected — отклонено
    created_at: datetime = Field(default_factory=datetime.utcnow)
    resolved_at: Optional[datetime] = None

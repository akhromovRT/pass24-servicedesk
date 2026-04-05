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

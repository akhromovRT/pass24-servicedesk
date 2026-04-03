from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field

from .models import TicketPriority, TicketStatus


# ---------------------------------------------------------------------------
# Тикеты
# ---------------------------------------------------------------------------


class TicketCreate(BaseModel):
    """Схема создания тикета. creator_id берётся из JWT-токена."""

    title: str = Field(..., max_length=200)
    description: str = Field(..., max_length=4000)
    category: str = Field(default="general", max_length=64)
    object_id: Optional[str] = Field(
        default=None, description="Идентификатор объекта PASS24 (ЖК / БЦ)"
    )
    access_point_id: Optional[str] = Field(
        default=None, description="Идентификатор точки доступа (дверь / домофон / шлагбаум)"
    )
    user_role: Optional[str] = Field(
        default=None,
        description="Кто пишет: житель, гость, УК, администратор и т.п.",
        max_length=64,
    )
    occurred_at: Optional[str] = Field(
        default=None,
        description="Когда примерно произошла проблема (свободный текст)",
        max_length=128,
    )
    contact: Optional[str] = Field(
        default=None,
        description="Телефон или email для связи",
        max_length=128,
    )
    urgent: bool = Field(
        default=False,
        description="Отметка 'не могу войти / въехать прямо сейчас'",
    )


class EventRead(BaseModel):
    """Схема чтения события тикета."""

    id: str
    ticket_id: str
    actor_id: Optional[str]
    description: str
    created_at: datetime

    model_config = {"from_attributes": True}


class CommentCreate(BaseModel):
    """Схема создания комментария. author_id берётся из JWT-токена."""

    text: str = Field(..., min_length=1, max_length=4000)
    is_internal: bool = Field(default=False, description="Внутренний комментарий (виден только агентам)")


class CommentRead(BaseModel):
    """Схема чтения комментария."""

    id: str
    ticket_id: str
    author_id: str
    author_name: str
    text: str
    is_internal: bool = False
    created_at: datetime

    model_config = {"from_attributes": True}


class AttachmentRead(BaseModel):
    """Схема чтения вложения."""

    id: str
    ticket_id: str
    uploader_id: str
    filename: str
    content_type: str
    size: int
    created_at: datetime

    model_config = {"from_attributes": True}


class TicketRead(BaseModel):
    """Полная схема чтения тикета с событиями и комментариями."""

    id: str
    creator_id: str
    title: str
    description: str
    category: str
    object_id: Optional[str]
    access_point_id: Optional[str]
    user_role: Optional[str]
    occurred_at: Optional[str]
    contact: Optional[str]
    urgent: bool
    status: TicketStatus
    priority: TicketPriority
    created_at: datetime
    updated_at: datetime
    first_response_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    sla_response_hours: Optional[int] = None
    sla_resolve_hours: Optional[int] = None
    events: List[EventRead] = []
    comments: List[CommentRead] = []
    attachments: List[AttachmentRead] = []

    model_config = {"from_attributes": True}


class TicketStatusUpdate(BaseModel):
    """Схема обновления статуса тикета. actor_id берётся из JWT-токена."""

    new_status: TicketStatus


class TicketListResponse(BaseModel):
    """Пагинированный ответ со списком тикетов."""

    items: List[TicketRead]
    total: int
    page: int
    per_page: int

from __future__ import annotations

from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, Field, model_validator

from .models import TicketPriority, TicketStatus


class TicketCreate(BaseModel):
    """Схема создания тикета."""

    title: str = Field(..., max_length=200)
    description: str = Field(..., max_length=10000)

    # 5-осевая классификация (всё опционально — авто-определяется)
    product: Optional[str] = Field(default="pass24_online", max_length=64)
    category: Optional[str] = Field(default="other", max_length=64)
    ticket_type: Optional[str] = Field(default="problem", max_length=64)
    source: Optional[str] = Field(default="web", max_length=64)

    # Объект
    object_name: Optional[str] = Field(default=None, max_length=256, description="ЖК / БЦ / КП")
    object_address: Optional[str] = Field(default=None, max_length=512)
    access_point: Optional[str] = Field(default=None, max_length=128, description="КПП, подъезд, дверь")

    # Контакт
    contact_name: Optional[str] = Field(default=None, max_length=256)
    contact_phone: Optional[str] = Field(default=None, max_length=20)
    company: Optional[str] = Field(default=None, max_length=256)

    # Техника
    device_type: Optional[str] = Field(default=None, max_length=32, description="ios / android / web")
    app_version: Optional[str] = Field(default=None, max_length=32)
    error_message: Optional[str] = Field(default=None, max_length=500)

    urgent: bool = Field(default=False)

    # Создание от имени другого пользователя (только для агентов/админов)
    on_behalf_of_email: Optional[str] = Field(
        default=None, max_length=320,
        description="Email заявителя (если агент создаёт за клиента)"
    )
    on_behalf_of_name: Optional[str] = Field(
        default=None, max_length=256,
        description="Имя заявителя (если агент создаёт за клиента)"
    )

    # Клиент пришёл из конкретной статьи БЗ — не нашёл ответ
    source_article_slug: Optional[str] = Field(
        default=None, max_length=512,
        description="Slug статьи БЗ, из которой создан тикет (клиент не нашёл ответа)"
    )
    customer_id: Optional[str] = Field(
        default=None, description="ID компании-клиента (Customer)"
    )


class GuestTicketCreate(BaseModel):
    """Создание тикета без авторизации — только email."""

    email: str = Field(..., min_length=5, max_length=320, pattern=r"^[^\s@]+@[^\s@]+\.[^\s@]+$", description="Email заявителя")
    name: Optional[str] = Field(default=None, max_length=256, description="Имя")
    title: str = Field(..., max_length=200)
    description: str = Field(..., max_length=10000)
    product: Optional[str] = Field(default="pass24_online", max_length=64)
    category: Optional[str] = Field(default="other", max_length=64)
    ticket_type: Optional[str] = Field(default="problem", max_length=64)
    object_name: Optional[str] = Field(default=None, max_length=256)
    contact_phone: Optional[str] = Field(default=None, max_length=20)
    urgent: bool = Field(default=False)
    source_article_slug: Optional[str] = Field(default=None, max_length=512)
    # window.location.hostname host-страницы, где встроен embed-виджет.
    # Для bristol.pass24online.ru → backend извлечёт subdomain "bristol",
    # найдёт Customer и проставит ticket.customer_id / company / object_name.
    embed_host: Optional[str] = Field(default=None, max_length=253)


class GuestTicketResponse(BaseModel):
    """Ответ на создание гостевого тикета."""

    ticket_id: str
    title: str
    status: str = "new"
    auth_required: bool = False  # True если email уже зарегистрирован с паролем


class EventRead(BaseModel):
    id: str
    ticket_id: str
    actor_id: Optional[str]
    description: str
    created_at: datetime
    model_config = {"from_attributes": True}


class CommentCreate(BaseModel):
    text: str = Field(..., min_length=1, max_length=10000)
    is_internal: bool = Field(default=False, description="Внутренний комментарий")


class CommentRead(BaseModel):
    id: str
    ticket_id: str
    author_id: str
    author_name: str
    text: str
    is_internal: bool = False
    author_is_staff: bool = False
    created_at: datetime
    model_config = {"from_attributes": True}


class AttachmentRead(BaseModel):
    id: str
    ticket_id: str
    uploader_id: str
    filename: str
    content_type: str
    size: int
    comment_id: Optional[str] = None
    created_at: datetime
    model_config = {"from_attributes": True}


class TicketRead(BaseModel):
    """Полная схема чтения тикета."""

    id: str
    creator_id: str
    assignee_id: Optional[str] = None
    title: str
    description: str

    # Классификация
    product: Optional[str] = None
    category: Optional[str] = None
    ticket_type: Optional[str] = None
    source: Optional[str] = None
    status: TicketStatus
    priority: TicketPriority

    # Объект
    object_name: Optional[str] = None
    object_address: Optional[str] = None
    access_point: Optional[str] = None

    # Контакт
    contact_name: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    company: Optional[str] = None

    # Техника
    device_type: Optional[str] = None
    app_version: Optional[str] = None
    error_message: Optional[str] = None

    urgent: bool = False
    created_at: datetime
    updated_at: datetime

    # ITIL
    impact: Optional[str] = None
    urgency: Optional[str] = None
    assignment_group: Optional[str] = None

    # SLA
    first_response_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    sla_response_hours: Optional[int] = None
    sla_resolve_hours: Optional[int] = None
    sla_breached: bool = False
    sla_paused_at: Optional[datetime] = None
    sla_total_pause_seconds: int = 0
    sla_paused_by_status: bool = False
    sla_paused_by_reply: bool = False
    has_unread_reply: bool = False

    # CSAT
    satisfaction_rating: Optional[int] = None
    satisfaction_comment: Optional[str] = None
    satisfaction_requested_at: Optional[datetime] = None
    satisfaction_submitted_at: Optional[datetime] = None

    # Implementation project link
    implementation_project_id: Optional[str] = None
    is_implementation_blocker: bool = False
    customer_id: Optional[str] = None

    events: List[EventRead] = []
    comments: List[CommentRead] = []
    attachments: List[AttachmentRead] = []

    # Кто ответил последним в переписке. Вычисляется из comments:
    # берётся последний по created_at публичный комментарий (не internal),
    # значение author_is_staff. Null, если публичных комментариев нет.
    last_public_reply_by: Optional[Literal["client", "staff"]] = None

    model_config = {"from_attributes": True}

    @model_validator(mode="after")
    def _compute_last_public_reply_by(self) -> "TicketRead":
        if not self.comments:
            return self
        latest = None
        for c in self.comments:
            if c.is_internal:
                continue
            if latest is None or c.created_at > latest.created_at:
                latest = c
        if latest is not None:
            self.last_public_reply_by = "staff" if latest.author_is_staff else "client"
        return self


class TicketStatusUpdate(BaseModel):
    new_status: TicketStatus


class TicketPriorityUpdate(BaseModel):
    """Ручное изменение impact/urgency агентом."""
    impact: str
    urgency: str


class TicketAssignmentUpdate(BaseModel):
    """Назначение группы / агента."""
    assignment_group: Optional[str] = None
    assignee_id: Optional[str] = None


class CsatSubmit(BaseModel):
    """Оценка удовлетворённости клиентом."""
    rating: int = Field(..., ge=1, le=5)
    comment: Optional[str] = Field(default=None, max_length=2000)


class TicketListResponse(BaseModel):
    items: List[TicketRead]
    total: int
    page: int
    per_page: int

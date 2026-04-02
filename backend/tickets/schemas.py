from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from .models import TicketPriority, TicketStatus


class TicketBase(BaseModel):
    title: str = Field(..., max_length=200)
    description: str = Field(..., max_length=4000)
    # Код типа проблемы (например: access, pass, gate, notifications, other)
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


class TicketCreate(TicketBase):
    creator_id: str = Field(..., description="Идентификатор пользователя PASS24")


class TicketRead(TicketBase):
    id: str
    creator_id: str
    status: TicketStatus
    priority: TicketPriority
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TicketStatusUpdate(BaseModel):
    new_status: TicketStatus
    actor_id: str = Field(..., description="Кто меняет статус (агент/УК)")


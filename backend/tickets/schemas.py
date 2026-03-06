from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from .models import TicketPriority, TicketStatus


class TicketBase(BaseModel):
    title: str = Field(..., max_length=200)
    description: str = Field(..., max_length=4000)
    category: str = Field(default="general", max_length=64)
    object_id: Optional[str] = Field(
        default=None, description="Идентификатор объекта PASS24 (ЖК / БЦ)"
    )
    access_point_id: Optional[str] = Field(
        default=None, description="Идентификатор точки доступа (дверь / домофон / шлагбаум)"
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


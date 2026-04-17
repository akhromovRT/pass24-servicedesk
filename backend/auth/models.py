from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import JSON
from sqlmodel import Column, Field, SQLModel


class UserRole(str, Enum):
    """Роли пользователей в системе PASS24 Service Desk."""

    RESIDENT = "resident"
    PROPERTY_MANAGER = "property_manager"
    SUPPORT_AGENT = "support_agent"
    ADMIN = "admin"


class User(SQLModel, table=True):
    """Таблица пользователей системы."""

    __tablename__ = "users"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    email: str = Field(unique=True, index=True, max_length=320)
    hashed_password: str
    full_name: str = Field(max_length=256)
    role: UserRole = Field(default=UserRole.RESIDENT)
    is_active: bool = Field(default=True)
    telegram_chat_id: int | None = Field(default=None, index=True)
    telegram_linked_at: datetime | None = Field(default=None)
    telegram_preferences: dict = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False, server_default="{}"),
    )
    customer_id: str | None = Field(default=None, index=True)  # FK → customers.id
    created_at: datetime = Field(default_factory=datetime.utcnow)
    password_reset_token: str | None = Field(default=None)
    password_reset_expires_at: datetime | None = Field(default=None)

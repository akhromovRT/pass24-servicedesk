from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

from .models import UserRole


class UserCreate(BaseModel):
    """Схема регистрации нового пользователя."""

    email: EmailStr
    password: str = Field(..., min_length=6, description="Пароль (минимум 6 символов)")
    full_name: str = Field(..., max_length=256, description="Полное имя пользователя")
    role: UserRole = Field(default=UserRole.RESIDENT, description="Роль в системе")


class UserLogin(BaseModel):
    """Схема входа в систему."""

    email: EmailStr
    password: str


class UserRead(BaseModel):
    """Схема ответа с данными пользователя (без пароля)."""

    id: uuid.UUID
    email: str
    full_name: str
    role: UserRole
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class Token(BaseModel):
    """Схема JWT-токена."""

    access_token: str
    token_type: str = "bearer"

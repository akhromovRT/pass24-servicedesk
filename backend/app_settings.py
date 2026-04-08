"""Настройки приложения, хранимые в БД (key-value)."""
from __future__ import annotations

import uuid
from typing import Optional

from sqlmodel import Field, SQLModel, select

from .database import async_session_factory


class AppSetting(SQLModel, table=True):
    """Одна настройка приложения. Ключ уникален."""

    __tablename__ = "app_settings"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    key: str = Field(unique=True, index=True, max_length=100)
    value: str = Field(default="", max_length=1000)


# Известные ключи
DEFAULT_ASSIGNEE_KEY = "default_assignee_id"


async def get_setting(key: str) -> Optional[str]:
    """Получить значение настройки по ключу."""
    async with async_session_factory() as session:
        result = await session.execute(
            select(AppSetting).where(AppSetting.key == key)
        )
        setting = result.scalar_one_or_none()
        return setting.value if setting else None


async def set_setting(key: str, value: str) -> None:
    """Установить значение настройки (upsert)."""
    async with async_session_factory() as session:
        result = await session.execute(
            select(AppSetting).where(AppSetting.key == key)
        )
        setting = result.scalar_one_or_none()
        if setting:
            setting.value = value
        else:
            setting = AppSetting(key=key, value=value)
        session.add(setting)
        await session.commit()


async def get_default_assignee_id() -> Optional[str]:
    """Получить ID агента для автоназначения новых заявок."""
    value = await get_setting(DEFAULT_ASSIGNEE_KEY)
    return value if value else None

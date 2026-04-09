"""Модель компании-клиента. ИНН — ключ синхронизации с Bitrix24."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class Customer(SQLModel, table=True):
    """Компания-клиент PASS24 — синхронизируется с Bitrix24 CRM по ИНН."""

    __tablename__ = "customers"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    inn: str = Field(max_length=20, index=True, unique=True)
    name: str = Field(max_length=512)
    bitrix24_company_id: Optional[int] = Field(default=None, index=True)
    address: Optional[str] = Field(default=None, max_length=1024)
    phone: Optional[str] = Field(default=None, max_length=64)
    email: Optional[str] = Field(default=None, max_length=320)
    industry: Optional[str] = Field(default=None, max_length=128)
    comment: Optional[str] = Field(default=None, max_length=2000)
    is_active: bool = Field(default=True)
    is_permanent_client: bool = Field(default=False)
    synced_at: Optional[datetime] = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

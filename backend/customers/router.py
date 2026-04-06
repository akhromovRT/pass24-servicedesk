"""API для компаний-клиентов и синхронизации с Bitrix24."""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import func, select

from backend.auth.dependencies import get_current_user
from backend.auth.models import User, UserRole
from backend.database import get_session

from .models import Customer

router = APIRouter(prefix="/customers", tags=["customers"])


class CustomerRead(BaseModel):
    id: str
    inn: str
    name: str
    bitrix24_company_id: Optional[int] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    industry: Optional[str] = None
    is_active: bool
    synced_at: Optional[datetime] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class CustomerCreate(BaseModel):
    inn: str = Field(..., min_length=10, max_length=20)
    name: str = Field(..., max_length=512)
    address: Optional[str] = Field(default=None, max_length=1024)
    phone: Optional[str] = Field(default=None, max_length=64)
    email: Optional[str] = Field(default=None, max_length=320)
    industry: Optional[str] = Field(default=None, max_length=128)
    comment: Optional[str] = Field(default=None, max_length=2000)


class ContactRead(BaseModel):
    id: str
    email: str
    full_name: str
    role: str

    model_config = {"from_attributes": True}


@router.get("/", response_model=List[CustomerRead])
async def list_customers(
    q: Optional[str] = Query(default=None, description="Поиск по названию или ИНН"),
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Список компаний-клиентов (для агентов/админов + property_manager видит свою)."""
    query = select(Customer).where(Customer.is_active == True)  # noqa: E712

    if current_user.role in (UserRole.SUPPORT_AGENT, UserRole.ADMIN):
        pass  # видят все
    elif current_user.role == UserRole.PROPERTY_MANAGER:
        # УК видит только свою компанию
        if current_user.customer_id:
            query = query.where(Customer.id == current_user.customer_id)
        else:
            return []
    else:
        return []

    if q and q.strip():
        pattern = f"%{q.strip()}%"
        query = query.where(Customer.name.ilike(pattern) | Customer.inn.ilike(pattern))

    query = query.order_by(Customer.name)
    r = await session.execute(query)
    return list(r.scalars())


@router.get("/{customer_id}", response_model=CustomerRead)
async def get_customer(
    customer_id: str,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Получить компанию по ID."""
    r = await session.execute(select(Customer).where(Customer.id == customer_id))
    customer = r.scalar_one_or_none()
    if not customer:
        raise HTTPException(status_code=404, detail="Компания не найдена")
    return customer


@router.post("/", response_model=CustomerRead, status_code=201)
async def create_customer(
    payload: CustomerCreate,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Создать компанию вручную (агент/админ)."""
    if current_user.role not in (UserRole.SUPPORT_AGENT, UserRole.ADMIN):
        raise HTTPException(status_code=403, detail="Только для агентов")

    # Проверка уникальности ИНН
    existing = await session.execute(select(Customer).where(Customer.inn == payload.inn))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"Компания с ИНН {payload.inn} уже существует")

    customer = Customer(
        inn=payload.inn,
        name=payload.name,
        address=payload.address,
        phone=payload.phone,
        email=payload.email,
        industry=payload.industry,
        comment=payload.comment,
    )
    session.add(customer)
    await session.commit()
    await session.refresh(customer)
    return customer


@router.get("/{customer_id}/contacts", response_model=List[ContactRead])
async def get_customer_contacts(
    customer_id: str,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Контакты (пользователи) привязанные к компании."""
    r = await session.execute(
        select(User).where(User.customer_id == customer_id, User.is_active == True)  # noqa: E712
        .order_by(User.full_name)
    )
    users = list(r.scalars())
    return [
        ContactRead(
            id=str(u.id),
            email=u.email,
            full_name=u.full_name,
            role=u.role.value if hasattr(u.role, 'value') else str(u.role),
        )
        for u in users
    ]


@router.post("/sync", status_code=200)
async def sync_from_bitrix24(
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
):
    """Запускает синхронизацию компаний и контактов из Bitrix24 (admin-only)."""
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Только для администратора")

    from .bitrix24_sync import sync_companies, sync_contacts

    async def _run_sync():
        try:
            companies_result = await sync_companies()
            contacts_result = await sync_contacts()
            import logging
            logging.getLogger(__name__).info(
                "Bitrix24 sync done: companies=%s, contacts=%s",
                companies_result, contacts_result,
            )
        except Exception as exc:
            import logging
            logging.getLogger(__name__).error("Bitrix24 sync failed: %s", exc)

    background_tasks.add_task(_run_sync)
    return {"status": "sync_started", "message": "Синхронизация запущена в фоне"}

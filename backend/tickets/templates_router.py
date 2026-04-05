"""API для шаблонов ответов и макросов."""
from __future__ import annotations

import json
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from backend.auth.dependencies import get_current_user
from backend.auth.models import User, UserRole
from backend.database import get_session

from .templates import Macro, ResponseTemplate

router = APIRouter(prefix="/tickets", tags=["templates"])


# ----- Schemas -----

class TemplateCreate(BaseModel):
    name: str = Field(..., max_length=256)
    body: str = Field(..., max_length=4000)
    category: Optional[str] = Field(default=None, max_length=64)
    is_shared: bool = True


class TemplateRead(BaseModel):
    id: str
    name: str
    body: str
    category: Optional[str]
    author_id: str
    is_shared: bool
    usage_count: int
    created_at: datetime

    model_config = {"from_attributes": True}


class MacroActions(BaseModel):
    status: Optional[str] = None
    comment: Optional[str] = None
    is_internal_comment: bool = False
    assign_self: bool = False
    assignment_group: Optional[str] = None


class MacroCreate(BaseModel):
    name: str = Field(..., max_length=256)
    icon: Optional[str] = Field(default=None, max_length=64)
    actions: MacroActions
    is_shared: bool = True


class MacroRead(BaseModel):
    id: str
    name: str
    icon: Optional[str]
    actions: MacroActions
    author_id: str
    is_shared: bool
    created_at: datetime


def _require_staff(user: User):
    if user.role not in (UserRole.SUPPORT_AGENT, UserRole.ADMIN):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Только для агентов и администраторов",
        )


# ----- Templates endpoints -----

@router.get("/templates", response_model=List[TemplateRead])
async def list_templates(
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Список шаблонов: свои + все общие."""
    _require_staff(current_user)
    r = await session.execute(
        select(ResponseTemplate).where(
            (ResponseTemplate.author_id == str(current_user.id))
            | (ResponseTemplate.is_shared == True)  # noqa: E712
        ).order_by(ResponseTemplate.usage_count.desc(), ResponseTemplate.name)
    )
    return list(r.scalars())


@router.post("/templates", response_model=TemplateRead, status_code=201)
async def create_template(
    payload: TemplateCreate,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    _require_staff(current_user)
    t = ResponseTemplate(
        name=payload.name,
        body=payload.body,
        category=payload.category,
        is_shared=payload.is_shared,
        author_id=str(current_user.id),
    )
    session.add(t)
    await session.commit()
    await session.refresh(t)
    return t


@router.delete("/templates/{template_id}", status_code=204)
async def delete_template(
    template_id: str,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    _require_staff(current_user)
    r = await session.execute(select(ResponseTemplate).where(ResponseTemplate.id == template_id))
    t = r.scalar_one_or_none()
    if not t:
        raise HTTPException(status_code=404, detail="Шаблон не найден")
    if t.author_id != str(current_user.id) and current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Можно удалять только свои шаблоны")
    await session.delete(t)
    await session.commit()


@router.post("/templates/{template_id}/use", status_code=204)
async def increment_template_usage(
    template_id: str,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Увеличивает счётчик использования шаблона."""
    _require_staff(current_user)
    r = await session.execute(select(ResponseTemplate).where(ResponseTemplate.id == template_id))
    t = r.scalar_one_or_none()
    if t:
        t.usage_count += 1
        session.add(t)
        await session.commit()


# ----- Macros endpoints -----

@router.get("/macros", response_model=List[MacroRead])
async def list_macros(
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    _require_staff(current_user)
    r = await session.execute(
        select(Macro).where(
            (Macro.author_id == str(current_user.id)) | (Macro.is_shared == True)  # noqa: E712
        ).order_by(Macro.name)
    )
    macros = list(r.scalars())
    return [
        MacroRead(
            id=m.id, name=m.name, icon=m.icon,
            actions=MacroActions(**json.loads(m.actions)),
            author_id=m.author_id, is_shared=m.is_shared, created_at=m.created_at,
        )
        for m in macros
    ]


@router.post("/macros", response_model=MacroRead, status_code=201)
async def create_macro(
    payload: MacroCreate,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    _require_staff(current_user)
    m = Macro(
        name=payload.name,
        icon=payload.icon,
        actions=payload.actions.model_dump_json(),
        is_shared=payload.is_shared,
        author_id=str(current_user.id),
    )
    session.add(m)
    await session.commit()
    await session.refresh(m)
    return MacroRead(
        id=m.id, name=m.name, icon=m.icon,
        actions=payload.actions,
        author_id=m.author_id, is_shared=m.is_shared, created_at=m.created_at,
    )


@router.delete("/macros/{macro_id}", status_code=204)
async def delete_macro(
    macro_id: str,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    _require_staff(current_user)
    r = await session.execute(select(Macro).where(Macro.id == macro_id))
    m = r.scalar_one_or_none()
    if not m:
        raise HTTPException(status_code=404, detail="Макрос не найден")
    if m.author_id != str(current_user.id) and current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Можно удалять только свои макросы")
    await session.delete(m)
    await session.commit()

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from backend.database import get_session

from .dependencies import get_current_user, require_role
from .models import User, UserRole
from .schemas import (
    ForgotPasswordRequest,
    ResetPasswordRequest,
    Token,
    UserCreate,
    UserLogin,
    UserRead,
)
from .utils import (
    create_access_token,
    create_reset_token,
    hash_password,
    hash_reset_token,
    verify_password,
)

from datetime import datetime, timedelta

from pydantic import BaseModel, EmailStr, Field
from typing import Optional

from backend.config import settings as app_settings

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def register(
    payload: UserCreate,
    session: AsyncSession = Depends(get_session),
) -> UserRead:
    """Регистрация нового пользователя.

    Роли support_agent и admin нельзя выбрать при регистрации —
    они назначаются только администратором.
    """
    from .models import UserRole

    SELF_REGISTER_ROLES = {UserRole.RESIDENT, UserRole.PROPERTY_MANAGER}
    if payload.role not in SELF_REGISTER_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Эту роль нельзя выбрать при регистрации",
        )

    # Проверяем уникальность email
    result = await session.execute(select(User).where(User.email == payload.email))
    if result.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Пользователь с таким email уже существует",
        )

    user = User(
        email=payload.email,
        hashed_password=hash_password(payload.password),
        full_name=payload.full_name,
        role=payload.role,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)

    return UserRead.model_validate(user)


@router.post("/login", response_model=Token)
async def login(
    payload: UserLogin,
    session: AsyncSession = Depends(get_session),
) -> Token:
    """Аутентификация пользователя и выдача JWT-токена."""

    result = await session.execute(select(User).where(User.email == payload.email))
    user = result.scalar_one_or_none()

    if user is None or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный email или пароль",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Учётная запись деактивирована",
        )

    access_token = create_access_token(data={"sub": str(user.id)})
    return Token(access_token=access_token)


@router.post("/forgot-password", status_code=status.HTTP_200_OK)
async def forgot_password(
    payload: ForgotPasswordRequest,
    session: AsyncSession = Depends(get_session),
):
    """Запрос на сброс пароля. Отправляет email со ссылкой."""
    result = await session.execute(select(User).where(User.email == payload.email))
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Пользователь с таким email не найден",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Учётная запись деактивирована",
        )

    raw_token, token_hash = create_reset_token()
    user.password_reset_token = token_hash
    user.password_reset_expires_at = datetime.utcnow() + timedelta(
        minutes=app_settings.password_reset_expire_minutes,
    )
    session.add(user)
    await session.commit()

    reset_url = f"{app_settings.app_base_url}/reset-password?token={raw_token}"

    from backend.notifications.email import notify_password_reset

    await notify_password_reset(user.email, reset_url)

    return {"message": "Письмо для сброса пароля отправлено"}


@router.post("/reset-password", status_code=status.HTTP_200_OK)
async def reset_password(
    payload: ResetPasswordRequest,
    session: AsyncSession = Depends(get_session),
):
    """Установка нового пароля по токену из email."""
    token_hash = hash_reset_token(payload.token)

    result = await session.execute(
        select(User).where(User.password_reset_token == token_hash)
    )
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Недействительная ссылка для сброса пароля",
        )

    if user.password_reset_expires_at is None or user.password_reset_expires_at < datetime.utcnow():
        user.password_reset_token = None
        user.password_reset_expires_at = None
        session.add(user)
        await session.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Срок действия ссылки истёк. Запросите сброс пароля повторно",
        )

    user.hashed_password = hash_password(payload.new_password)
    user.password_reset_token = None
    user.password_reset_expires_at = None
    session.add(user)
    await session.commit()

    return {"message": "Пароль успешно изменён"}


@router.get("/me", response_model=UserRead)
async def me(current_user: User = Depends(get_current_user)) -> UserRead:
    """Получение информации о текущем пользователе."""
    return UserRead.model_validate(current_user)


# ---------------------------------------------------------------------------
# Admin endpoints: управление пользователями
# ---------------------------------------------------------------------------


class AdminCreateUser(BaseModel):
    """Создание пользователя администратором — роль любая."""

    email: EmailStr
    password: str = Field(..., min_length=6)
    full_name: str = Field(..., max_length=256)
    role: UserRole = Field(default=UserRole.SUPPORT_AGENT)


class AdminUpdateUser(BaseModel):
    """Обновление пользователя администратором."""

    full_name: Optional[str] = Field(default=None, max_length=256)
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None


class AdminResetPassword(BaseModel):
    """Сброс пароля администратором."""

    new_password: str = Field(..., min_length=6)


@router.get("/users", response_model=list[UserRead])
async def list_users(
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_role(UserRole.ADMIN)),
    role: Optional[str] = None,
    is_active: Optional[bool] = None,
    q: Optional[str] = Query(default=None, description="Поиск по ФИО, email, компании"),
    customer_id: Optional[str] = Query(default=None, description="Фильтр по компании"),
) -> list[UserRead]:
    """Список пользователей с фильтрами по роли, статусу, поиску, компании."""
    from backend.customers.models import Customer

    query = select(User).order_by(User.created_at.desc())

    if role:
        roles = [r.strip() for r in role.split(",") if r.strip()]
        if len(roles) == 1:
            query = query.where(User.role == roles[0])
        elif roles:
            query = query.where(User.role.in_(roles))

    if is_active is not None:
        query = query.where(User.is_active == is_active)

    if customer_id:
        query = query.where(User.customer_id == customer_id)

    # Поиск по ФИО / email
    if q and q.strip():
        pattern = f"%{q.strip()}%"
        # Также ищем по названию компании
        matching_customer_ids = await session.execute(
            select(Customer.id).where(Customer.name.ilike(pattern))
        )
        cids = [r[0] for r in matching_customer_ids.all()]
        if cids:
            query = query.where(
                User.full_name.ilike(pattern) | User.email.ilike(pattern) | User.customer_id.in_(cids)
            )
        else:
            query = query.where(User.full_name.ilike(pattern) | User.email.ilike(pattern))

    result = await session.execute(query)
    users = result.scalars().all()

    # Подтягиваем customer_name
    cust_ids = {u.customer_id for u in users if u.customer_id}
    cust_names: dict[str, str] = {}
    if cust_ids:
        cr = await session.execute(select(Customer).where(Customer.id.in_(cust_ids)))
        for c in cr.scalars():
            cust_names[c.id] = c.name

    items = []
    for u in users:
        data = UserRead.model_validate(u)
        data.customer_name = cust_names.get(u.customer_id or "", None)
        items.append(data)

    return items


@router.post("/users", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def admin_create_user(
    payload: AdminCreateUser,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_role(UserRole.ADMIN)),
) -> UserRead:
    """Создание пользователя администратором (любая роль)."""
    result = await session.execute(select(User).where(User.email == payload.email))
    if result.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Пользователь с таким email уже существует",
        )

    user = User(
        email=payload.email,
        hashed_password=hash_password(payload.password),
        full_name=payload.full_name,
        role=payload.role,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return UserRead.model_validate(user)


@router.patch("/users/{user_id}", response_model=UserRead)
async def admin_update_user(
    user_id: str,
    payload: AdminUpdateUser,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_role(UserRole.ADMIN)),
) -> UserRead:
    """Обновление пользователя (ФИО, роль, активность)."""
    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Пользователь не найден")

    if payload.full_name is not None:
        user.full_name = payload.full_name
    if payload.role is not None:
        user.role = payload.role
    if payload.is_active is not None:
        user.is_active = payload.is_active

    session.add(user)
    await session.commit()
    await session.refresh(user)
    return UserRead.model_validate(user)


@router.post("/users/{user_id}/password", response_model=UserRead)
async def admin_reset_password(
    user_id: str,
    payload: AdminResetPassword,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_role(UserRole.ADMIN)),
) -> UserRead:
    """Сброс пароля пользователя администратором."""
    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Пользователь не найден")

    user.hashed_password = hash_password(payload.new_password)
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return UserRead.model_validate(user)


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def admin_delete_user(
    user_id: str,
    session: AsyncSession = Depends(get_session),
    current_admin: User = Depends(require_role(UserRole.ADMIN)),
):
    """Удаление пользователя (нельзя удалить себя)."""
    if str(current_admin.id) == user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Нельзя удалить самого себя",
        )

    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Пользователь не найден")

    await session.delete(user)
    await session.commit()


# ---------------------------------------------------------------------------
# Telegram account linking
# ---------------------------------------------------------------------------


@router.post("/telegram/link-token")
async def generate_telegram_link_token(
    current_user: User = Depends(get_current_user),
) -> dict:
    """Сгенерировать одноразовую deep-link-ссылку для привязки Telegram-бота."""
    from backend.telegram.services.linking import generate_token

    try:
        return await generate_token(str(current_user.id))
    except ValueError as e:
        if str(e) == "rate_limit":
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Слишком много запросов. Попробуйте позже.",
            )
        raise


@router.delete("/telegram/link")
async def unlink_telegram(
    current_user: User = Depends(get_current_user),
) -> dict:
    """Отвязать Telegram от учётной записи."""
    from backend.telegram.services.linking import unlink_account

    await unlink_account(str(current_user.id))
    return {"ok": True}

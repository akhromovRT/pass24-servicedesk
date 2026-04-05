from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from backend.database import get_session

from .dependencies import get_current_user, require_role
from .models import User, UserRole
from .schemas import Token, UserCreate, UserLogin, UserRead
from .utils import create_access_token, hash_password, verify_password

from pydantic import BaseModel, EmailStr, Field
from typing import Optional

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
) -> list[UserRead]:
    """Список всех пользователей с фильтрами по роли и статусу."""
    query = select(User).order_by(User.created_at.desc())

    if role:
        # Поддержка нескольких ролей через запятую
        roles = [r.strip() for r in role.split(",") if r.strip()]
        if len(roles) == 1:
            query = query.where(User.role == roles[0])
        elif roles:
            query = query.where(User.role.in_(roles))

    if is_active is not None:
        query = query.where(User.is_active == is_active)

    result = await session.execute(query)
    return [UserRead.model_validate(u) for u in result.scalars().all()]


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

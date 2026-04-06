"""RBAC dependencies для модуля проектов внедрения.

Централизованный guard get_project_with_access() исключает дыры в проверках:
- resident → всегда 403
- property_manager → только если project.customer_id == user.id
- support_agent, admin → любой проект
"""

from __future__ import annotations

from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth.dependencies import get_current_user
from backend.auth.models import User, UserRole
from backend.database import get_session
from backend.projects.models import ImplementationProject


PASS24_ROLES = (UserRole.SUPPORT_AGENT, UserRole.ADMIN)


def is_pass24_staff(user: User) -> bool:
    """True если пользователь — сотрудник PASS24 (может управлять всеми проектами)."""
    return user.role in PASS24_ROLES


async def get_project_with_access(
    project_id: str,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ImplementationProject:
    """Вернуть проект с проверкой прав доступа.

    Правила:
    - resident → 403
    - property_manager → 404 если customer_id != user.id (чтобы не раскрывать существование)
    - support_agent, admin → любой проект
    """
    if current_user.role == UserRole.RESIDENT:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Резиденты не имеют доступа к проектам внедрения",
        )

    project = await session.get(ImplementationProject, project_id)
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Проект не найден",
        )

    if current_user.role == UserRole.PROPERTY_MANAGER:
        if project.customer_id != str(current_user.id):
            # Для PM чужой проект = несуществующий (не раскрываем факт)
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Проект не найден",
            )

    return project


async def require_pass24_staff(
    current_user: User = Depends(get_current_user),
) -> User:
    """Разрешает доступ только support_agent и admin."""
    if not is_pass24_staff(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Только для сотрудников PASS24",
        )
    return current_user


async def require_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    """Только для admin."""
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Только администраторы могут выполнять эту операцию",
        )
    return current_user

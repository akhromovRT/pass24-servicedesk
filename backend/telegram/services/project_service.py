"""Проектный сервис для Telegram-бота (PM workspace).

Читает список проектов PM, подробности карточки, pending approvals —
без повторного использования HTTP dependencies. Все запросы включают
фильтр по ``customer_id``, чтобы PM видел только свои проекты.
"""

from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy import func, select

from backend.database import async_session_factory
from backend.projects.models import (
    ApprovalStatus,
    ImplementationProject,
    PhaseStatus,
    ProjectApproval,
    ProjectPhase,
    ProjectRisk,
    RiskStatus,
)

logger = logging.getLogger(__name__)

_MAX_PROJECTS = 20


def _status_value(value) -> str:
    """Coerce enum/str to plain string (modes differ across SQLModel fields)."""
    return getattr(value, "value", value) if value is not None else ""


async def list_user_projects(customer_id: str) -> list[dict]:
    """Список проектов PM, отсортированных по started_at (новые сверху).

    Returns entries: ``{id, code, name, status, current_phase_name,
    started_at, target_end_date, progress_percent}``.

    Прогресс = completed_phases / total_phases × 100. При отсутствии фаз — 0.
    """
    async with async_session_factory() as session:
        stmt = (
            select(ImplementationProject)
            .where(ImplementationProject.customer_id == customer_id)
            .order_by(
                ImplementationProject.actual_start_date.desc().nullslast(),
                ImplementationProject.name,
            )
            .limit(_MAX_PROJECTS)
        )
        projects = list((await session.execute(stmt)).scalars().all())
        if not projects:
            return []

        project_ids = [p.id for p in projects]

        # Считаем фазы на Python, чтобы не тащить диалект-специфичные агрегаты.
        # 20 проектов × ~10 фаз = 200 строк — нагрузка ничтожная.
        phase_rows_stmt = select(
            ProjectPhase.project_id, ProjectPhase.status
        ).where(ProjectPhase.project_id.in_(project_ids))
        phase_rows = (await session.execute(phase_rows_stmt)).all()

        totals: dict[str, int] = {}
        completed: dict[str, int] = {}
        for pid, status in phase_rows:
            totals[pid] = totals.get(pid, 0) + 1
            if _status_value(status) == PhaseStatus.COMPLETED.value:
                completed[pid] = completed.get(pid, 0) + 1

        # current_phase_name по current_phase_id отсутствует в модели —
        # вместо этого показываем первую фазу в статусе IN_PROGRESS (или None).
        current_phase_stmt = (
            select(ProjectPhase.project_id, ProjectPhase.name, ProjectPhase.order_num)
            .where(
                ProjectPhase.project_id.in_(project_ids),
                ProjectPhase.status == PhaseStatus.IN_PROGRESS,
            )
            .order_by(ProjectPhase.order_num)
        )
        current_phase_map: dict[str, str] = {}
        for pid, name, _order in (await session.execute(current_phase_stmt)).all():
            current_phase_map.setdefault(pid, name)

        result = []
        for p in projects:
            total = totals.get(p.id, 0)
            done = completed.get(p.id, 0)
            progress = int(round((done / total) * 100)) if total else 0
            result.append(
                {
                    "id": p.id,
                    "code": p.code,
                    "name": p.name,
                    "status": _status_value(p.status),
                    "current_phase_name": current_phase_map.get(p.id),
                    "started_at": p.actual_start_date,
                    "target_end_date": p.planned_end_date,
                    "progress_percent": progress,
                }
            )
        return result


async def get_project_summary(
    project_id_prefix: str, customer_id: str
) -> Optional[dict]:
    """Подробная карточка проекта PM (с фазами и рисками).

    Фильтрует по ``customer_id`` — ownership check. Возвращает None если проект
    не найден / не принадлежит PM.
    """
    async with async_session_factory() as session:
        proj_stmt = (
            select(ImplementationProject)
            .where(
                ImplementationProject.customer_id == customer_id,
                ImplementationProject.id.startswith(project_id_prefix),
            )
            .limit(1)
        )
        project = (await session.execute(proj_stmt)).scalar_one_or_none()
        if project is None:
            return None

        phases_stmt = (
            select(ProjectPhase)
            .where(ProjectPhase.project_id == project.id)
            .order_by(ProjectPhase.order_num)
        )
        phases = list((await session.execute(phases_stmt)).scalars().all())

        risks_stmt = (
            select(ProjectRisk)
            .where(
                ProjectRisk.project_id == project.id,
                ProjectRisk.status == RiskStatus.OPEN,
            )
            .order_by(ProjectRisk.created_at.desc())
        )
        risks = list((await session.execute(risks_stmt)).scalars().all())

        current_phase = next(
            (p for p in phases if _status_value(p.status) == PhaseStatus.IN_PROGRESS.value),
            None,
        )

        total_phases = len(phases)
        completed_phases = sum(
            1 for p in phases if _status_value(p.status) == PhaseStatus.COMPLETED.value
        )
        progress = int(round((completed_phases / total_phases) * 100)) if total_phases else 0

        return {
            "id": project.id,
            "code": project.code,
            "name": project.name,
            "status": _status_value(project.status),
            "customer_id": project.customer_id,
            "object_name": project.object_name,
            "progress_percent": progress,
            "started_at": project.actual_start_date,
            "target_end_date": project.planned_end_date,
            "phases": [
                {
                    "id": ph.id,
                    "name": ph.name,
                    "status": _status_value(ph.status),
                    "order": ph.order_num,
                    "planned_start": ph.planned_start_date,
                    "planned_end": ph.planned_end_date,
                }
                for ph in phases
            ],
            "risks": [
                {
                    "id": r.id,
                    "title": r.title,
                    "severity": _status_value(r.severity),
                    "description": r.description,
                }
                for r in risks
            ],
            "current_phase": (
                {
                    "id": current_phase.id,
                    "name": current_phase.name,
                }
                if current_phase is not None
                else None
            ),
        }


async def list_pending_approvals(customer_id: str) -> list[dict]:
    """Pending approvals всех проектов PM, старые первыми."""
    async with async_session_factory() as session:
        stmt = (
            select(ProjectApproval, ImplementationProject, ProjectPhase)
            .join(
                ImplementationProject,
                ImplementationProject.id == ProjectApproval.project_id,
            )
            .join(ProjectPhase, ProjectPhase.id == ProjectApproval.phase_id)
            .where(
                ImplementationProject.customer_id == customer_id,
                ProjectApproval.status == ApprovalStatus.PENDING,
            )
            .order_by(ProjectApproval.requested_at)
        )
        rows = (await session.execute(stmt)).all()

    return [
        {
            "approval_id": approval.id,
            "project_id": project.id,
            "project_code": project.code,
            "project_name": project.name,
            "phase_id": phase.id,
            "phase_name": phase.name,
            "requested_at": approval.requested_at,
            "requested_by": approval.requested_by,
        }
        for approval, project, phase in rows
    ]


async def pending_approvals_count(customer_id: str) -> int:
    """Число pending approvals для бейджа в главном меню."""
    async with async_session_factory() as session:
        stmt = (
            select(func.count(ProjectApproval.id))
            .join(
                ImplementationProject,
                ImplementationProject.id == ProjectApproval.project_id,
            )
            .where(
                ImplementationProject.customer_id == customer_id,
                ProjectApproval.status == ApprovalStatus.PENDING,
            )
        )
        return int((await session.execute(stmt)).scalar_one() or 0)


async def resolve_approval_id(
    approval_id_prefix: str, customer_id: str
) -> Optional[str]:
    """Вернуть полный approval.id по первым 16 символам (с проверкой customer)."""
    async with async_session_factory() as session:
        stmt = (
            select(ProjectApproval.id)
            .join(
                ImplementationProject,
                ImplementationProject.id == ProjectApproval.project_id,
            )
            .where(
                ImplementationProject.customer_id == customer_id,
                ProjectApproval.id.startswith(approval_id_prefix),
            )
            .limit(1)
        )
        row = (await session.execute(stmt)).scalar_one_or_none()
        return row

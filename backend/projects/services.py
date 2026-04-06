"""Сервисный слой для модуля проектов: создание из шаблона, генерация кода, пересчёт."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.projects.models import (
    ImplementationProject,
    PhaseStatus,
    ProjectEvent,
    ProjectPhase,
    ProjectTask,
    ProjectType,
    TaskStatus,
)
from backend.projects.templates import TemplateDefinition, get_template


async def generate_project_code(session: AsyncSession) -> str:
    """Сгенерировать последовательный код проекта PRJ-YYYY-NNN.

    Счётчик ведётся по году. Если в этом году ещё нет проектов → 001.
    """
    year = datetime.utcnow().year
    prefix = f"PRJ-{year}-"

    # Ищем максимальный номер в этом году
    result = await session.execute(
        select(ImplementationProject.code).where(
            ImplementationProject.code.like(f"{prefix}%")
        )
    )
    codes = [row[0] for row in result.all()]

    max_seq = 0
    for code in codes:
        try:
            seq = int(code.rsplit("-", 1)[-1])
            if seq > max_seq:
                max_seq = seq
        except (ValueError, IndexError):
            continue

    return f"{prefix}{max_seq + 1:03d}"


def _plan_phase_dates(
    start_date: Optional[date],
    template: TemplateDefinition,
) -> list[tuple[Optional[date], Optional[date]]]:
    """Рассчитать плановые даты каждой фазы, начиная от start_date.

    Если start_date None — возвращает (None, None) для каждой фазы.
    Возвращает список (planned_start, planned_end) по фазам в порядке order.
    """
    if start_date is None:
        return [(None, None) for _ in template.phases]

    results = []
    current = start_date
    for phase in template.phases:
        end = current + timedelta(days=phase.duration_days)
        results.append((current, end))
        current = end
    return results


def _copy_phases_from_template(
    project: ImplementationProject,
    template: TemplateDefinition,
) -> tuple[list[ProjectPhase], list[ProjectTask]]:
    """Создать объекты фаз и задач на основе шаблона.

    Объекты НЕ добавляются в session — это делает вызывающий код.
    Возвращает (phases, tasks) — параллельные списки для session.add_all().
    """
    phase_dates = _plan_phase_dates(project.planned_start_date, template)

    all_phases: list[ProjectPhase] = []
    all_tasks: list[ProjectTask] = []

    for template_phase, (start_d, end_d) in zip(template.phases, phase_dates):
        phase = ProjectPhase(
            project_id=project.id,
            name=template_phase.name,
            description=template_phase.description,
            order_num=template_phase.order,
            weight=template_phase.weight,
            planned_duration_days=template_phase.duration_days,
            planned_start_date=start_d,
            planned_end_date=end_d,
        )
        all_phases.append(phase)

        for i, template_task in enumerate(template_phase.tasks, start=1):
            task = ProjectTask(
                phase_id=phase.id,
                project_id=project.id,
                title=template_task.title,
                description=template_task.description,
                is_milestone=template_task.is_milestone,
                estimated_hours=template_task.estimated_hours,
                order_num=i,
            )
            all_tasks.append(task)

    return all_phases, all_tasks


async def create_project_from_template(
    session: AsyncSession,
    *,
    name: str,
    customer_id: str,
    customer_company: str,
    object_name: str,
    project_type: ProjectType,
    created_by: str,
    object_address: Optional[str] = None,
    contract_number: Optional[str] = None,
    contract_signed_at: Optional[date] = None,
    planned_start_date: Optional[date] = None,
    planned_end_date: Optional[date] = None,
    manager_id: Optional[str] = None,
    notes: Optional[str] = None,
) -> ImplementationProject:
    """Создать проект из шаблона с автоматическим копированием фаз и задач.

    НЕ коммитит транзакцию — это делает вызывающий endpoint.
    """
    template = get_template(project_type)
    code = await generate_project_code(session)

    # Автоматически вычисляем planned_end_date если задан старт и не задан конец
    if planned_start_date and not planned_end_date:
        planned_end_date = planned_start_date + timedelta(days=template.total_duration_days)

    project = ImplementationProject(
        code=code,
        name=name,
        customer_id=customer_id,
        customer_company=customer_company,
        object_name=object_name,
        object_address=object_address,
        project_type=project_type,
        contract_number=contract_number,
        contract_signed_at=contract_signed_at,
        planned_start_date=planned_start_date,
        planned_end_date=planned_end_date,
        manager_id=manager_id,
        notes=notes,
        created_by=created_by,
    )
    session.add(project)

    phases, tasks = _copy_phases_from_template(project, template)
    session.add_all(phases)
    session.add_all(tasks)

    # Событие создания
    session.add(
        ProjectEvent(
            project_id=project.id,
            actor_id=created_by,
            event_type="created",
            description=f"Проект «{name}» создан из шаблона «{template.title}»",
        )
    )

    await session.flush()  # чтобы все ID были доступны
    return project


async def load_project_full(
    session: AsyncSession, project_id: str
) -> Optional[ImplementationProject]:
    """Загрузить проект со всеми связями (phases, tasks, team)."""
    result = await session.execute(
        select(ImplementationProject)
        .where(ImplementationProject.id == project_id)
        .options(
            selectinload(ImplementationProject.phases).selectinload(ProjectPhase.tasks),
            selectinload(ImplementationProject.team),
        )
    )
    return result.scalar_one_or_none()


async def count_project_documents(session: AsyncSession, project_id: str) -> int:
    """Считает количество документов проекта."""
    from backend.projects.models import ProjectDocument
    result = await session.execute(
        select(func.count()).select_from(ProjectDocument).where(
            ProjectDocument.project_id == project_id
        )
    )
    return result.scalar_one()


async def count_open_tasks(session: AsyncSession, project_id: str) -> int:
    """Считает количество открытых задач (TODO + IN_PROGRESS) проекта."""
    result = await session.execute(
        select(func.count())
        .select_from(ProjectTask)
        .where(
            ProjectTask.project_id == project_id,
            ProjectTask.status.in_([TaskStatus.TODO, TaskStatus.IN_PROGRESS]),
        )
    )
    return result.scalar_one()

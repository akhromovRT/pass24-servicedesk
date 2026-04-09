"""FastAPI router для модуля проектов внедрения.

Содержит CRUD-endpoints проектов, transition FSM, список, шаблоны и статистику.
Phases/Tasks/Documents/Comments/Team/Tickets-link реализованы отдельными модулями
(будут добавлены в следующих итерациях).

Важно: в main.py этот router должен регистрироваться ДО tickets_router, чтобы
специфичные маршруты /projects/templates и /projects/stats не перехватывались
паттерном /projects/{id}.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlmodel import select

from backend.auth.dependencies import get_current_user
from backend.auth.models import User, UserRole
from backend.database import get_session
from backend.notifications.projects import (
    notify_customer_welcome,
    notify_milestone_reached,
    notify_phase_completed,
    notify_project_created,
    notify_project_status_changed,
)
from backend.projects.dependencies import (
    get_project_with_access,
    is_pass24_staff,
    require_admin,
    require_pass24_staff,
)
from backend.projects.models import (
    ImplementationProject,
    PhaseStatus,
    ProjectEvent,
    ProjectPhase,
    ProjectStatus,
    ProjectTask,
    ProjectType,
    TaskStatus,
)
from backend.projects.schemas import (
    CustomerCreate,
    CustomerCreated,
    PhaseRead,
    PhaseUpdate,
    ProjectCreate,
    ProjectListItem,
    ProjectListResponse,
    ProjectRead,
    ProjectStats,
    ProjectTransition,
    ProjectUpdate,
    TaskCreate,
    TaskRead,
    TaskUpdate,
    TemplateOut,
    TemplatePhaseOut,
    TemplateTaskOut,
)
from backend.projects.services import (
    count_open_tasks,
    count_project_documents,
    create_project_from_template,
    load_project_full,
)
from backend.projects.templates import PROJECT_TEMPLATES

router = APIRouter(prefix="/projects", tags=["projects"])


# ---------------------------------------------------------------------------
# Templates (GET /projects/templates)
# ---------------------------------------------------------------------------


@router.get("/templates", response_model=List[TemplateOut])
async def list_templates(
    current_user: User = Depends(get_current_user),
) -> List[TemplateOut]:
    """Вернуть все доступные шаблоны проектов (read-only в MVP).

    Доступно всем авторизованным пользователям — даже резидентам,
    поскольку информация некритичная.
    """
    result: List[TemplateOut] = []
    for project_type, template in PROJECT_TEMPLATES.items():
        phases_out = [
            TemplatePhaseOut(
                order=p.order,
                name=p.name,
                description=p.description,
                duration_days=p.duration_days,
                weight=p.weight,
                tasks=[
                    TemplateTaskOut(
                        title=t.title,
                        description=t.description,
                        is_milestone=t.is_milestone,
                        estimated_hours=t.estimated_hours,
                    )
                    for t in p.tasks
                ],
            )
            for p in template.phases
        ]
        result.append(
            TemplateOut(
                project_type=project_type,
                title=template.title,
                description=template.description,
                total_duration_days=template.total_duration_days,
                phases=phases_out,
            )
        )
    return result


# ---------------------------------------------------------------------------
# Create customer (POST /projects/create-customer)
# ---------------------------------------------------------------------------


@router.post("/create-customer", response_model=CustomerCreated, status_code=status.HTTP_201_CREATED)
async def create_customer(
    payload: CustomerCreate,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(require_admin),
) -> CustomerCreated:
    """Создать нового клиента-администратора УК прямо из формы проекта.

    Генерирует временный пароль, создаёт пользователя с ролью property_manager.
    Пароль возвращается в ответе один раз (для показа админу).
    """
    import uuid as uuid_mod

    from backend.auth.utils import hash_password

    email = payload.email.strip().lower()

    # Проверка уникальности
    existing = await session.execute(select(User).where(User.email == email))
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Пользователь с таким email уже существует",
        )

    temp_password = uuid_mod.uuid4().hex[:10]
    user = User(
        email=email,
        hashed_password=hash_password(temp_password),
        full_name=payload.full_name.strip(),
        role=UserRole.PROPERTY_MANAGER,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)

    return CustomerCreated(
        id=str(user.id),
        email=user.email,
        full_name=user.full_name,
        temp_password=temp_password,
    )


# ---------------------------------------------------------------------------
# Stats (GET /projects/stats)
# ---------------------------------------------------------------------------


@router.get("/stats", response_model=ProjectStats)
async def get_projects_stats(
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_pass24_staff),
) -> ProjectStats:
    """Сводная статистика по проектам (только для PASS24)."""
    today = date.today()
    first_of_month = today.replace(day=1)

    # Всего
    total = (await session.execute(
        select(func.count()).select_from(ImplementationProject)
    )).scalar_one()

    # Активные (planning + in_progress)
    active = (await session.execute(
        select(func.count())
        .select_from(ImplementationProject)
        .where(ImplementationProject.status.in_([
            ProjectStatus.PLANNING, ProjectStatus.IN_PROGRESS,
        ]))
    )).scalar_one()

    # Завершено в этом месяце
    completed_this_month = (await session.execute(
        select(func.count())
        .select_from(ImplementationProject)
        .where(
            ImplementationProject.status == ProjectStatus.COMPLETED,
            ImplementationProject.actual_end_date >= first_of_month,
        )
    )).scalar_one()

    # На паузе
    on_hold = (await session.execute(
        select(func.count())
        .select_from(ImplementationProject)
        .where(ImplementationProject.status == ProjectStatus.ON_HOLD)
    )).scalar_one()

    # Просроченные (planned_end_date < today и не completed/cancelled)
    overdue = (await session.execute(
        select(func.count())
        .select_from(ImplementationProject)
        .where(
            ImplementationProject.planned_end_date < today,
            ImplementationProject.status.notin_([
                ProjectStatus.COMPLETED, ProjectStatus.CANCELLED,
            ]),
        )
    )).scalar_one()

    # Breakdown по project_type
    by_type_rows = (await session.execute(
        select(
            ImplementationProject.project_type,
            func.count(),
        ).group_by(ImplementationProject.project_type)
    )).all()
    by_type = {row[0]: row[1] for row in by_type_rows}

    return ProjectStats(
        total=total,
        active=active,
        completed_this_month=completed_this_month,
        on_hold=on_hold,
        overdue=overdue,
        by_type=by_type,
    )


# ---------------------------------------------------------------------------
# CRUD: список и создание
# ---------------------------------------------------------------------------


@router.get("/", response_model=ProjectListResponse)
async def list_projects(
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    project_status: Optional[str] = Query(default=None, alias="status"),
    project_type: Optional[str] = Query(default=None),
    q: Optional[str] = Query(default=None),
    customer_id: Optional[str] = Query(default=None),
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ProjectListResponse:
    """Список проектов с фильтрацией и пагинацией.

    - resident → 403
    - property_manager → только свои проекты (customer_id = user.id)
    - support_agent, admin → все проекты
    """
    if current_user.role == UserRole.RESIDENT:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Резиденты не имеют доступа к проектам внедрения",
        )

    query = select(ImplementationProject)
    count_query = select(func.count()).select_from(ImplementationProject)

    # RBAC: PM видит только свои
    if current_user.role == UserRole.PROPERTY_MANAGER:
        user_id_str = str(current_user.id)
        query = query.where(ImplementationProject.customer_id == user_id_str)
        count_query = count_query.where(ImplementationProject.customer_id == user_id_str)
    elif customer_id:
        # Фильтр по customer_id доступен только PASS24
        query = query.where(ImplementationProject.customer_id == customer_id)
        count_query = count_query.where(ImplementationProject.customer_id == customer_id)

    # Фильтр по статусу (поддерживает CSV: "planning,in_progress")
    if project_status:
        statuses = project_status.split(",")
        query = query.where(ImplementationProject.status.in_(statuses))
        count_query = count_query.where(ImplementationProject.status.in_(statuses))

    # Фильтр по типу проекта
    if project_type:
        types = project_type.split(",")
        query = query.where(ImplementationProject.project_type.in_(types))
        count_query = count_query.where(ImplementationProject.project_type.in_(types))

    # Поиск по name, code, customer_company, object_name
    if q and q.strip():
        pattern = f"%{q.strip()}%"
        search = (
            ImplementationProject.name.ilike(pattern)
            | ImplementationProject.code.ilike(pattern)
            | ImplementationProject.customer_company.ilike(pattern)
            | ImplementationProject.object_name.ilike(pattern)
        )
        query = query.where(search)
        count_query = count_query.where(search)

    # Пагинация и сортировка (новые сверху)
    total_result = await session.execute(count_query)
    total = total_result.scalar_one()

    offset = (page - 1) * per_page
    query = (
        query.order_by(ImplementationProject.updated_at.desc())
        .offset(offset)
        .limit(per_page)
    )

    result = await session.execute(query)
    projects = result.scalars().all()

    return ProjectListResponse(
        items=[ProjectListItem.model_validate(p) for p in projects],
        total=total,
        page=page,
        per_page=per_page,
    )


@router.post("/", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
async def create_project(
    payload: ProjectCreate,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(require_admin),
) -> ProjectRead:
    """Создать проект из шаблона.

    При создании автоматически копируются фазы и задачи из шаблона
    в соответствии с project_type. Рассчитываются плановые даты фаз
    от planned_start_date. Только для admin.
    """
    project = await create_project_from_template(
        session,
        name=payload.name,
        customer_id=payload.customer_id,
        customer_company=payload.customer_company,
        object_name=payload.object_name,
        object_address=payload.object_address,
        project_type=payload.project_type,
        contract_number=payload.contract_number,
        contract_signed_at=payload.contract_signed_at,
        planned_start_date=payload.planned_start_date,
        planned_end_date=payload.planned_end_date,
        manager_id=payload.manager_id,
        notes=payload.notes,
        created_by=str(current_user.id),
    )
    await session.commit()

    # Загружаем полную версию с phases/tasks
    full = await load_project_full(session, project.id)
    doc_count = await count_project_documents(session, project.id)
    open_tasks = await count_open_tasks(session, project.id)

    # Уведомление
    customer_email, manager_email = await _get_notification_recipients(session, project)
    phases_html = _build_phases_html(full) if full else ""

    if payload.send_welcome_email and customer_email and payload.customer_temp_password:
        # Welcome-email для нового клиента (с паролем и инструкциями)
        customer = await session.get(User, payload.customer_id)
        background_tasks.add_task(
            notify_customer_welcome,
            customer_email=customer_email,
            customer_name=customer.full_name if customer else "Клиент",
            temp_password=payload.customer_temp_password,
            project_code=project.code,
            project_name=project.name,
            object_name=project.object_name,
            phases_html=phases_html,
        )
    elif customer_email:
        # Обычное уведомление для существующего клиента (с фазами)
        background_tasks.add_task(
            notify_project_created,
            customer_email=customer_email,
            project_code=project.code,
            project_name=project.name,
            object_name=project.object_name,
            phases_summary=phases_html,
            manager_email=manager_email,
        )

    return _build_project_read(full, doc_count, open_tasks)


# ---------------------------------------------------------------------------
# Вспомогательная функция сборки ProjectRead
# ---------------------------------------------------------------------------


def _build_phases_html(project: ImplementationProject) -> str:
    """Сгенерировать HTML-список фаз для email-уведомлений."""
    if not project.phases:
        return "<p>Фазы будут определены позже.</p>"
    sorted_phases = sorted(project.phases, key=lambda p: p.order_num)
    items = []
    for p in sorted_phases:
        duration = f" ({p.planned_duration_days} дн)" if p.planned_duration_days else ""
        items.append(f"<li><strong>{p.order_num}. {p.name}</strong>{duration}</li>")
    return f'<ol style="padding-left: 20px;">{"".join(items)}</ol>'


async def _get_notification_recipients(
    session: AsyncSession,
    project: ImplementationProject,
) -> tuple[Optional[str], Optional[str]]:
    """Получить email клиента и менеджера проекта. Возвращает (customer_email, manager_email)."""
    customer_email: Optional[str] = None
    manager_email: Optional[str] = None

    if project.customer_id:
        customer = await session.get(User, project.customer_id)
        if customer:
            customer_email = customer.email

    if project.manager_id:
        manager = await session.get(User, project.manager_id)
        if manager:
            manager_email = manager.email

    return customer_email, manager_email


def _build_project_read(
    project: ImplementationProject,
    doc_count: int,
    open_tasks: int,
) -> ProjectRead:
    """Собрать ProjectRead из загруженного проекта + счётчики."""
    data = ProjectRead.model_validate(project)
    data.document_count = doc_count
    data.open_tasks_count = open_tasks
    # Сортируем фазы по order_num и задачи внутри фазы по order_num
    data.phases.sort(key=lambda p: p.order_num)
    for phase in data.phases:
        phase.tasks.sort(key=lambda t: (t.order_num, t.created_at))
    return data


# ---------------------------------------------------------------------------
# CRUD: детали, обновление, transition, удаление
# ---------------------------------------------------------------------------


@router.get("/{project_id}", response_model=ProjectRead)
async def get_project(
    project_id: str,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ProjectRead:
    """Детали проекта с phases, tasks, team. RBAC через get_project_with_access."""
    # RBAC проверка через dependency (404 если не найден / нет доступа)
    _ = await get_project_with_access(project_id, session=session, current_user=current_user)

    # Загружаем с eager-loading для полной детализации
    full = await load_project_full(session, project_id)
    if full is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Проект не найден")

    doc_count = await count_project_documents(session, project_id)
    open_tasks = await count_open_tasks(session, project_id)

    return _build_project_read(full, doc_count, open_tasks)


@router.patch("/{project_id}", response_model=ProjectRead)
async def update_project(
    project_id: str,
    payload: ProjectUpdate,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ProjectRead:
    """Обновить метаданные проекта. Только для support_agent, admin."""
    if not is_pass24_staff(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Только команда PASS24 может редактировать проект",
        )

    project = await get_project_with_access(
        project_id, session=session, current_user=current_user
    )

    update_data = payload.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Нет полей для обновления")

    # Собираем описание изменений для event log
    changes = []
    for field, value in update_data.items():
        old_value = getattr(project, field)
        if old_value != value:
            changes.append(f"{field}: {old_value} → {value}")
            setattr(project, field, value)

    if not changes:
        # Ничего не изменилось
        full = await load_project_full(session, project_id)
        doc_count = await count_project_documents(session, project_id)
        open_tasks = await count_open_tasks(session, project_id)
        return _build_project_read(full, doc_count, open_tasks)

    project.updated_at = datetime.utcnow()
    session.add(project)

    session.add(
        ProjectEvent(
            project_id=project.id,
            actor_id=str(current_user.id),
            event_type="project_updated",
            description="Проект обновлён: " + "; ".join(changes[:3]),
        )
    )
    await session.commit()

    full = await load_project_full(session, project_id)
    doc_count = await count_project_documents(session, project_id)
    open_tasks = await count_open_tasks(session, project_id)
    return _build_project_read(full, doc_count, open_tasks)


@router.post("/{project_id}/transition", response_model=ProjectRead)
async def transition_project(
    project_id: str,
    payload: ProjectTransition,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ProjectRead:
    """FSM-переход статуса проекта. Только для support_agent, admin."""
    if not is_pass24_staff(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Только команда PASS24 может изменять статус проекта",
        )

    project = await get_project_with_access(
        project_id, session=session, current_user=current_user
    )

    try:
        event = project.transition(
            actor_id=str(current_user.id),
            new_status=payload.new_status,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    session.add(project)
    session.add(event)
    await session.commit()

    # Уведомление об изменении статуса
    customer_email, manager_email = await _get_notification_recipients(session, project)
    if customer_email:
        background_tasks.add_task(
            notify_project_status_changed,
            customer_email=customer_email,
            project_code=project.code,
            project_name=project.name,
            new_status=payload.new_status.value,
            changed_by=current_user.full_name,
            manager_email=manager_email,
        )

    full = await load_project_full(session, project_id)
    doc_count = await count_project_documents(session, project_id)
    open_tasks = await count_open_tasks(session, project_id)
    return _build_project_read(full, doc_count, open_tasks)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def delete_project(
    project_id: str,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(require_admin),
) -> None:
    """Soft-delete проекта: устанавливает статус CANCELLED. Только для admin.

    Физического удаления нет — вся история сохраняется.
    """
    project = await get_project_with_access(
        project_id, session=session, current_user=current_user
    )

    if project.status == ProjectStatus.CANCELLED:
        return  # уже отменён — идемпотентно

    if project.status == ProjectStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Нельзя отменить завершённый проект",
        )

    project.status = ProjectStatus.CANCELLED
    project.updated_at = datetime.utcnow()
    session.add(project)
    session.add(
        ProjectEvent(
            project_id=project.id,
            actor_id=str(current_user.id),
            event_type="project_cancelled",
            description="Проект отменён (soft-delete)",
        )
    )
    await session.commit()


# ---------------------------------------------------------------------------
# Phases endpoints
# ---------------------------------------------------------------------------


async def _load_phase_with_tasks(
    session: AsyncSession, phase_id: str
) -> Optional[ProjectPhase]:
    """Загрузить фазу со всеми задачами."""
    result = await session.execute(
        select(ProjectPhase)
        .where(ProjectPhase.id == phase_id)
        .options(selectinload(ProjectPhase.tasks))
    )
    return result.scalar_one_or_none()


async def _recalculate_and_persist_progress(
    session: AsyncSession, project_id: str
) -> ImplementationProject:
    """Пересчитать progress для всех фаз и проекта, сохранить изменения."""
    project = await load_project_full(session, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Проект не найден")

    for phase in project.phases:
        phase.recalculate_progress()
        session.add(phase)

    project.recalculate_progress()
    session.add(project)
    return project


@router.get("/{project_id}/phases", response_model=List[PhaseRead])
async def list_phases(
    project_id: str,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> List[PhaseRead]:
    """Список фаз проекта с вложенными задачами."""
    _ = await get_project_with_access(project_id, session=session, current_user=current_user)

    result = await session.execute(
        select(ProjectPhase)
        .where(ProjectPhase.project_id == project_id)
        .options(selectinload(ProjectPhase.tasks))
        .order_by(ProjectPhase.order_num)
    )
    phases = result.scalars().all()

    phases_out: List[PhaseRead] = []
    for phase in phases:
        read = PhaseRead.model_validate(phase)
        read.tasks.sort(key=lambda t: (t.order_num, t.created_at))
        phases_out.append(read)
    return phases_out


@router.get("/{project_id}/phases/{phase_id}", response_model=PhaseRead)
async def get_phase(
    project_id: str,
    phase_id: str,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> PhaseRead:
    """Детали одной фазы с задачами."""
    _ = await get_project_with_access(project_id, session=session, current_user=current_user)

    phase = await _load_phase_with_tasks(session, phase_id)
    if phase is None or phase.project_id != project_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Фаза не найдена")

    read = PhaseRead.model_validate(phase)
    read.tasks.sort(key=lambda t: (t.order_num, t.created_at))
    return read


@router.patch("/{project_id}/phases/{phase_id}", response_model=PhaseRead)
async def update_phase(
    project_id: str,
    phase_id: str,
    payload: PhaseUpdate,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(require_pass24_staff),
) -> PhaseRead:
    """Обновить метаданные фазы. Только для support_agent, admin."""
    _ = await get_project_with_access(project_id, session=session, current_user=current_user)

    phase = await session.get(ProjectPhase, phase_id)
    if phase is None or phase.project_id != project_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Фаза не найдена")

    update_data = payload.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Нет полей для обновления")

    for field, value in update_data.items():
        setattr(phase, field, value)

    session.add(phase)
    session.add(
        ProjectEvent(
            project_id=project_id,
            actor_id=str(current_user.id),
            event_type="phase_updated",
            description=f"Фаза «{phase.name}» обновлена",
        )
    )

    # Если изменился weight — нужно пересчитать progress проекта
    if "weight" in update_data:
        await _recalculate_and_persist_progress(session, project_id)

    await session.commit()

    phase = await _load_phase_with_tasks(session, phase_id)
    read = PhaseRead.model_validate(phase)
    read.tasks.sort(key=lambda t: (t.order_num, t.created_at))
    return read


@router.post("/{project_id}/phases/{phase_id}/start", response_model=PhaseRead)
async def start_phase(
    project_id: str,
    phase_id: str,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(require_pass24_staff),
) -> PhaseRead:
    """Перевести фазу в IN_PROGRESS."""
    _ = await get_project_with_access(project_id, session=session, current_user=current_user)

    phase = await session.get(ProjectPhase, phase_id)
    if phase is None or phase.project_id != project_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Фаза не найдена")

    try:
        event = phase.start(actor_id=str(current_user.id))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    session.add(phase)
    session.add(event)
    await session.commit()

    phase = await _load_phase_with_tasks(session, phase_id)
    read = PhaseRead.model_validate(phase)
    read.tasks.sort(key=lambda t: (t.order_num, t.created_at))
    return read


@router.post("/{project_id}/phases/{phase_id}/complete", response_model=PhaseRead)
async def complete_phase(
    project_id: str,
    phase_id: str,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(require_pass24_staff),
) -> PhaseRead:
    """Перевести фазу в COMPLETED (ставит progress=100, актуализирует прогресс проекта)."""
    project = await get_project_with_access(
        project_id, session=session, current_user=current_user
    )

    phase = await session.get(ProjectPhase, phase_id)
    if phase is None or phase.project_id != project_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Фаза не найдена")

    try:
        event = phase.complete(actor_id=str(current_user.id))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    session.add(phase)
    session.add(event)

    # Пересчёт progress проекта
    updated_project = await _recalculate_and_persist_progress(session, project_id)
    await session.commit()

    # Уведомление о завершении фазы
    customer_email, manager_email = await _get_notification_recipients(session, updated_project)
    if customer_email:
        background_tasks.add_task(
            notify_phase_completed,
            customer_email=customer_email,
            project_code=updated_project.code,
            project_name=updated_project.name,
            phase_name=phase.name,
            progress_pct=updated_project.progress_pct,
            manager_email=manager_email,
        )

    phase = await _load_phase_with_tasks(session, phase_id)
    read = PhaseRead.model_validate(phase)
    read.tasks.sort(key=lambda t: (t.order_num, t.created_at))
    return read


# ---------------------------------------------------------------------------
# Tasks endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/{project_id}/phases/{phase_id}/tasks",
    response_model=TaskRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_task(
    project_id: str,
    phase_id: str,
    payload: TaskCreate,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(require_pass24_staff),
) -> TaskRead:
    """Добавить задачу в фазу. Только для support_agent, admin."""
    _ = await get_project_with_access(project_id, session=session, current_user=current_user)

    phase = await session.get(ProjectPhase, phase_id)
    if phase is None or phase.project_id != project_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Фаза не найдена")

    task = ProjectTask(
        phase_id=phase_id,
        project_id=project_id,
        title=payload.title,
        description=payload.description,
        priority=payload.priority,
        assignee_id=payload.assignee_id,
        due_date=payload.due_date,
        is_milestone=payload.is_milestone,
        estimated_hours=payload.estimated_hours,
        order_num=payload.order_num,
    )
    session.add(task)
    session.add(
        ProjectEvent(
            project_id=project_id,
            actor_id=str(current_user.id),
            event_type="task_added",
            description=f"Добавлена задача «{payload.title}» в фазу «{phase.name}»",
        )
    )

    # Добавление новой задачи меняет прогресс фазы и проекта
    await _recalculate_and_persist_progress(session, project_id)
    await session.commit()
    await session.refresh(task)

    return TaskRead.model_validate(task)


@router.get("/{project_id}/tasks", response_model=List[TaskRead])
async def list_tasks(
    project_id: str,
    task_status: Optional[str] = Query(default=None, alias="status"),
    assignee_id: Optional[str] = Query(default=None),
    phase_id: Optional[str] = Query(default=None),
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> List[TaskRead]:
    """Список задач проекта с фильтрами."""
    _ = await get_project_with_access(project_id, session=session, current_user=current_user)

    query = select(ProjectTask).where(ProjectTask.project_id == project_id)
    if task_status:
        statuses = task_status.split(",")
        query = query.where(ProjectTask.status.in_(statuses))
    if assignee_id:
        query = query.where(ProjectTask.assignee_id == assignee_id)
    if phase_id:
        query = query.where(ProjectTask.phase_id == phase_id)
    query = query.order_by(ProjectTask.order_num, ProjectTask.created_at)

    result = await session.execute(query)
    tasks = result.scalars().all()
    return [TaskRead.model_validate(t) for t in tasks]


@router.patch("/{project_id}/tasks/{task_id}", response_model=TaskRead)
async def update_task(
    project_id: str,
    task_id: str,
    payload: TaskUpdate,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(require_pass24_staff),
) -> TaskRead:
    """Обновить задачу."""
    _ = await get_project_with_access(project_id, session=session, current_user=current_user)

    task = await session.get(ProjectTask, task_id)
    if task is None or task.project_id != project_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Задача не найдена")

    update_data = payload.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Нет полей для обновления")

    status_changed = "status" in update_data and update_data["status"] != task.status

    for field, value in update_data.items():
        setattr(task, field, value)
    task.updated_at = datetime.utcnow()

    # Если перевод в DONE — заполнить completed_at / completed_by
    if status_changed and task.status == TaskStatus.DONE:
        task.completed_at = datetime.utcnow()
        task.completed_by = str(current_user.id)

    session.add(task)

    # Пересчёт прогресса если изменился статус
    if status_changed:
        await _recalculate_and_persist_progress(session, project_id)

    await session.commit()
    await session.refresh(task)
    return TaskRead.model_validate(task)


@router.post("/{project_id}/tasks/{task_id}/complete", response_model=TaskRead)
async def complete_task(
    project_id: str,
    task_id: str,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(require_pass24_staff),
) -> TaskRead:
    """Отметить задачу как выполненную, пересчитать прогресс."""
    project = await get_project_with_access(
        project_id, session=session, current_user=current_user
    )

    task = await session.get(ProjectTask, task_id)
    if task is None or task.project_id != project_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Задача не найдена")

    was_done = task.status == TaskStatus.DONE
    try:
        task.complete(actor_id=str(current_user.id))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    session.add(task)

    updated_project = project
    if not was_done:  # только если реально изменился статус
        session.add(
            ProjectEvent(
                project_id=project_id,
                actor_id=str(current_user.id),
                event_type="task_completed",
                description=f"Задача «{task.title}» завершена",
            )
        )
        updated_project = await _recalculate_and_persist_progress(session, project_id)

    await session.commit()

    # Уведомление если это milestone
    if not was_done and task.is_milestone:
        customer_email, manager_email = await _get_notification_recipients(
            session, updated_project
        )
        if customer_email:
            background_tasks.add_task(
                notify_milestone_reached,
                customer_email=customer_email,
                project_code=updated_project.code,
                project_name=updated_project.name,
                milestone_title=task.title,
                completed_by=current_user.full_name,
                manager_email=manager_email,
            )

    await session.refresh(task)
    return TaskRead.model_validate(task)


@router.delete("/{project_id}/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def delete_task(
    project_id: str,
    task_id: str,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(require_pass24_staff),
) -> None:
    """Soft-delete задачи: статус CANCELLED."""
    _ = await get_project_with_access(project_id, session=session, current_user=current_user)

    task = await session.get(ProjectTask, task_id)
    if task is None or task.project_id != project_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Задача не найдена")

    if task.status == TaskStatus.CANCELLED:
        return  # идемпотентно

    task.status = TaskStatus.CANCELLED
    task.updated_at = datetime.utcnow()
    session.add(task)
    session.add(
        ProjectEvent(
            project_id=project_id,
            actor_id=str(current_user.id),
            event_type="task_cancelled",
            description=f"Задача «{task.title}» отменена",
        )
    )

    await _recalculate_and_persist_progress(session, project_id)
    await session.commit()


# ---------------------------------------------------------------------------
# Шаблоны проектов: DB-backed CRUD (admin only)
# ---------------------------------------------------------------------------

from pydantic import BaseModel as PydanticBaseModel
from backend.projects.models import ProjectTemplateDB
import json as _json


class TemplateDBCreate(PydanticBaseModel):
    project_type: str
    title: str
    description: Optional[str] = None
    total_duration_days: int = 0
    phases_json: str = "[]"


class TemplateDBUpdate(PydanticBaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    total_duration_days: Optional[int] = None
    phases_json: Optional[str] = None
    is_active: Optional[bool] = None


class TemplateDBRead(PydanticBaseModel):
    id: str
    project_type: str
    title: str
    description: Optional[str] = None
    total_duration_days: int
    phases_json: str
    is_active: bool
    created_at: str
    model_config = {"from_attributes": True}


@router.get("/templates/db", response_model=List[TemplateDBRead])
async def list_db_templates(
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(require_pass24_staff),
):
    """Список шаблонов проектов из БД (для редактора)."""
    result = await session.execute(
        select(ProjectTemplateDB).order_by(ProjectTemplateDB.project_type)
    )
    templates = result.scalars().all()

    # Seed: если в БД пусто — загружаем из Python-констант
    if not templates:
        for pt, tmpl in PROJECT_TEMPLATES.items():
            phases_data = [
                {
                    "order": p.order,
                    "name": p.name,
                    "description": p.description,
                    "duration_days": p.duration_days,
                    "weight": p.weight,
                    "tasks": [
                        {"title": t.title, "description": t.description, "is_milestone": t.is_milestone, "estimated_hours": t.estimated_hours}
                        for t in p.tasks
                    ],
                }
                for p in tmpl.phases
            ]
            db_tmpl = ProjectTemplateDB(
                project_type=pt,
                title=tmpl.title,
                description=tmpl.description,
                total_duration_days=tmpl.total_duration_days,
                phases_json=_json.dumps(phases_data, ensure_ascii=False),
                created_by=str(current_user.id),
            )
            session.add(db_tmpl)
        await session.commit()
        result = await session.execute(
            select(ProjectTemplateDB).order_by(ProjectTemplateDB.project_type)
        )
        templates = result.scalars().all()

    return [TemplateDBRead.model_validate(t) for t in templates]


@router.post("/templates/db", response_model=TemplateDBRead, status_code=status.HTTP_201_CREATED)
async def create_db_template(
    payload: TemplateDBCreate,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(require_admin),
):
    """Создать шаблон проекта."""
    tmpl = ProjectTemplateDB(
        project_type=payload.project_type,
        title=payload.title,
        description=payload.description,
        total_duration_days=payload.total_duration_days,
        phases_json=payload.phases_json,
        created_by=str(current_user.id),
    )
    session.add(tmpl)
    await session.commit()
    await session.refresh(tmpl)
    return TemplateDBRead.model_validate(tmpl)


@router.put("/templates/db/{template_id}", response_model=TemplateDBRead)
async def update_db_template(
    template_id: str,
    payload: TemplateDBUpdate,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(require_admin),
):
    """Обновить шаблон."""
    result = await session.execute(
        select(ProjectTemplateDB).where(ProjectTemplateDB.id == template_id)
    )
    tmpl = result.scalar_one_or_none()
    if not tmpl:
        raise HTTPException(status_code=404, detail="Шаблон не найден")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(tmpl, field, value)
    tmpl.updated_at = datetime.utcnow()
    session.add(tmpl)
    await session.commit()
    await session.refresh(tmpl)
    return TemplateDBRead.model_validate(tmpl)


@router.delete("/templates/db/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_db_template(
    template_id: str,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(require_admin),
):
    """Деактивировать шаблон (soft delete)."""
    result = await session.execute(
        select(ProjectTemplateDB).where(ProjectTemplateDB.id == template_id)
    )
    tmpl = result.scalar_one_or_none()
    if not tmpl:
        raise HTTPException(status_code=404, detail="Шаблон не найден")
    tmpl.is_active = False
    tmpl.updated_at = datetime.utcnow()
    session.add(tmpl)
    await session.commit()


# ---------------------------------------------------------------------------
# Project Analytics (staff only)
# ---------------------------------------------------------------------------


class AnalyticsResponse(PydanticBaseModel):
    total_projects: int
    active_projects: int
    completed_projects: int
    on_hold_projects: int
    avg_duration_days: Optional[float] = None
    on_time_rate: Optional[float] = None
    by_type: dict
    by_status: dict
    open_risks_count: int
    pending_approvals_count: int


@router.get("/analytics", response_model=AnalyticsResponse)
async def get_project_analytics(
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(require_pass24_staff),
):
    """Аналитика по проектам внедрения."""
    from backend.projects.models import ProjectApproval, ProjectRisk

    total = (await session.execute(
        select(func.count()).select_from(ImplementationProject)
    )).scalar_one()

    active = (await session.execute(
        select(func.count()).select_from(ImplementationProject)
        .where(ImplementationProject.status == "in_progress")
    )).scalar_one()

    completed = (await session.execute(
        select(func.count()).select_from(ImplementationProject)
        .where(ImplementationProject.status == "completed")
    )).scalar_one()

    on_hold = (await session.execute(
        select(func.count()).select_from(ImplementationProject)
        .where(ImplementationProject.status == "on_hold")
    )).scalar_one()

    # Средняя длительность завершённых
    avg_duration = None
    completed_list = (await session.execute(
        select(ImplementationProject).where(
            ImplementationProject.status == "completed",
            ImplementationProject.actual_start_date.is_not(None),
            ImplementationProject.actual_end_date.is_not(None),
        )
    )).scalars().all()
    if completed_list:
        durations = [(p.actual_end_date - p.actual_start_date).days for p in completed_list]
        avg_duration = round(sum(durations) / len(durations), 1)

    # On-time rate
    on_time_rate = None
    if completed_list:
        on_time = sum(1 for p in completed_list if p.planned_end_date and p.actual_end_date and p.actual_end_date <= p.planned_end_date)
        on_time_rate = round(on_time / len(completed_list) * 100, 1)

    by_type_result = await session.execute(
        select(ImplementationProject.project_type, func.count()).group_by(ImplementationProject.project_type)
    )
    by_type = {row[0]: row[1] for row in by_type_result.all()}

    by_status_result = await session.execute(
        select(ImplementationProject.status, func.count()).group_by(ImplementationProject.status)
    )
    by_status = {row[0].value if hasattr(row[0], 'value') else row[0]: row[1] for row in by_status_result.all()}

    open_risks = (await session.execute(
        select(func.count()).select_from(ProjectRisk).where(ProjectRisk.status == "open")
    )).scalar_one()

    pending_approvals = (await session.execute(
        select(func.count()).select_from(ProjectApproval).where(ProjectApproval.status == "pending")
    )).scalar_one()

    return AnalyticsResponse(
        total_projects=total,
        active_projects=active,
        completed_projects=completed,
        on_hold_projects=on_hold,
        avg_duration_days=avg_duration,
        on_time_rate=on_time_rate,
        by_type=by_type,
        by_status=by_status,
        open_risks_count=open_risks,
        pending_approvals_count=pending_approvals,
    )

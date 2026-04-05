"""Модели проектов внедрения: Project, Phase, Task, Document, TeamMember, Event, Comment."""

import uuid
from datetime import date, datetime
from enum import Enum
from typing import List, Optional

from sqlmodel import Column, Field, Relationship, SQLModel, String


# ---------------------------------------------------------------------------
# Перечисления
# ---------------------------------------------------------------------------


class ProjectStatus(str, Enum):
    """FSM статуса проекта внедрения."""

    DRAFT = "draft"                # черновик, заполняется PM
    PLANNING = "planning"          # назначена команда, ждём старта
    IN_PROGRESS = "in_progress"    # идут работы
    ON_HOLD = "on_hold"            # пауза (ждём клиента/решения)
    COMPLETED = "completed"        # внедрение закончено
    CANCELLED = "cancelled"        # расторгнут договор


class ProjectType(str, Enum):
    """Тип проекта = выбор шаблона при создании."""

    RESIDENTIAL = "residential"              # ЖК
    COMMERCIAL = "commercial"                # БЦ
    CAMERAS_ONLY = "cameras_only"            # только pass24.auto (камеры)
    LARGE_CONSTRUCTION = "large_construction"  # большая стройка


class PhaseStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    BLOCKED = "blocked"
    SKIPPED = "skipped"


class TaskStatus(str, Enum):
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    CANCELLED = "cancelled"


class TaskPriority(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class DocumentType(str, Enum):
    CONTRACT = "contract"          # договор
    SPECIFICATION = "specification"  # ТЗ, BOM
    ACT = "act"                    # акт выполненных работ
    DIAGRAM = "diagram"            # схема подключения
    PHOTO = "photo"                # фото монтажа
    REPORT = "report"              # отчёт
    OTHER = "other"


class TeamRole(str, Enum):
    PROJECT_MANAGER = "project_manager"
    TECH_LEAD = "tech_lead"
    INSTALLER = "installer"
    INTEGRATOR = "integrator"
    TRAINER = "trainer"


# FSM transitions проекта: откуда → куда допустимо
PROJECT_ALLOWED_TRANSITIONS = {
    ProjectStatus.DRAFT: {ProjectStatus.PLANNING, ProjectStatus.CANCELLED},
    ProjectStatus.PLANNING: {ProjectStatus.IN_PROGRESS, ProjectStatus.CANCELLED},
    ProjectStatus.IN_PROGRESS: {ProjectStatus.ON_HOLD, ProjectStatus.COMPLETED, ProjectStatus.CANCELLED},
    ProjectStatus.ON_HOLD: {ProjectStatus.IN_PROGRESS, ProjectStatus.CANCELLED},
    ProjectStatus.COMPLETED: set(),   # терминальный
    ProjectStatus.CANCELLED: set(),   # терминальный
}


# ---------------------------------------------------------------------------
# Проект внедрения
# ---------------------------------------------------------------------------


class ImplementationProject(SQLModel, table=True):
    """Доменная модель проекта внедрения PASS24."""

    __tablename__ = "implementation_projects"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    code: str = Field(
        sa_column=Column(String(16), unique=True, index=True, nullable=False),
        description="Читаемый код проекта: PRJ-2026-001",
    )
    name: str = Field(max_length=256, index=True)

    # Клиент
    customer_id: str = Field(index=True, description="User.id (property_manager)")
    customer_company: str = Field(max_length=256)

    # Объект
    object_name: str = Field(max_length=256, index=True)
    object_address: Optional[str] = Field(default=None, max_length=512)

    # Тип и статус
    project_type: str = Field(
        default=ProjectType.RESIDENTIAL,
        sa_column=Column(String, index=True, default="residential"),
    )
    status: ProjectStatus = Field(default=ProjectStatus.DRAFT, index=True)

    # Договор
    contract_number: Optional[str] = Field(default=None, max_length=64)
    contract_signed_at: Optional[date] = Field(default=None)

    # Сроки
    planned_start_date: Optional[date] = Field(default=None)
    planned_end_date: Optional[date] = Field(default=None)
    actual_start_date: Optional[date] = Field(default=None)
    actual_end_date: Optional[date] = Field(default=None)

    # Прогресс
    progress_pct: int = Field(default=0, description="0-100, рассчитывается из фаз")

    # Команда и примечания
    manager_id: Optional[str] = Field(default=None, index=True, description="Ответственный support_agent")
    notes: Optional[str] = Field(default=None, max_length=4000)

    # Аудит
    created_by: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    # Связи
    phases: List["ProjectPhase"] = Relationship(back_populates="project")
    documents: List["ProjectDocument"] = Relationship(back_populates="project")
    team: List["ProjectTeamMember"] = Relationship(back_populates="project")
    events: List["ProjectEvent"] = Relationship(back_populates="project")
    comments: List["ProjectComment"] = Relationship(back_populates="project")

    # ------------------------------------------------------------------
    # Бизнес-логика
    # ------------------------------------------------------------------

    def transition(self, actor_id: str, new_status: ProjectStatus) -> "ProjectEvent":
        """FSM переходов статусов проекта."""
        allowed = PROJECT_ALLOWED_TRANSITIONS.get(self.status, set())
        if new_status not in allowed:
            raise ValueError(
                f"Недопустимый переход статуса проекта: {self.status.value} -> {new_status.value}"
            )

        now = datetime.utcnow()
        prev_status = self.status
        self.status = new_status
        self.updated_at = now

        # Автоматические даты при переходах
        if new_status == ProjectStatus.IN_PROGRESS and self.actual_start_date is None:
            self.actual_start_date = now.date()
        if new_status == ProjectStatus.COMPLETED:
            self.actual_end_date = now.date()
            self.progress_pct = 100

        return ProjectEvent(
            project_id=self.id,
            actor_id=actor_id,
            event_type="status_changed",
            description=f"Статус изменён: {prev_status.value} → {new_status.value}",
        )

    def recalculate_progress(self) -> None:
        """Пересчёт progress_pct = sum(phase.progress * phase.weight) / sum(weight).

        Фазы со статусом SKIPPED не учитываются. При пустом списке фаз = 0.
        """
        if not self.phases:
            self.progress_pct = 0
            return

        active_phases = [p for p in self.phases if p.status != PhaseStatus.SKIPPED]
        if not active_phases:
            self.progress_pct = 0
            return

        total_weight = sum(p.weight for p in active_phases)
        if total_weight == 0:
            self.progress_pct = 0
            return

        weighted_sum = sum(p.progress_pct * p.weight for p in active_phases)
        self.progress_pct = round(weighted_sum / total_weight)
        self.updated_at = datetime.utcnow()


# ---------------------------------------------------------------------------
# Фаза проекта
# ---------------------------------------------------------------------------


class ProjectPhase(SQLModel, table=True):
    __tablename__ = "project_phases"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    project_id: str = Field(foreign_key="implementation_projects.id", index=True)

    name: str = Field(max_length=256)
    description: Optional[str] = Field(default=None, max_length=2000)
    order_num: int = Field(default=1, description="Порядок фазы в проекте (1..N)")

    status: PhaseStatus = Field(default=PhaseStatus.PENDING, index=True)
    weight: int = Field(default=1, description="Вес фазы для расчёта прогресса проекта")

    # Сроки
    planned_duration_days: Optional[int] = Field(default=None)
    planned_start_date: Optional[date] = Field(default=None)
    planned_end_date: Optional[date] = Field(default=None)
    actual_start_date: Optional[date] = Field(default=None)
    actual_end_date: Optional[date] = Field(default=None)

    progress_pct: int = Field(default=0, description="0-100, рассчитывается из задач")

    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Связи
    project: Optional["ImplementationProject"] = Relationship(back_populates="phases")
    tasks: List["ProjectTask"] = Relationship(back_populates="phase")

    # ------------------------------------------------------------------
    # Бизнес-логика
    # ------------------------------------------------------------------

    def recalculate_progress(self) -> None:
        """Пересчёт progress_pct фазы на основе задач.

        Формула: done / active * 100, где active = total - cancelled.
        Если все задачи cancelled или задач нет → 0.
        """
        if not self.tasks:
            self.progress_pct = 0
            return

        active_tasks = [t for t in self.tasks if t.status != TaskStatus.CANCELLED]
        if not active_tasks:
            self.progress_pct = 0
            return

        done_count = sum(1 for t in active_tasks if t.status == TaskStatus.DONE)
        self.progress_pct = round(done_count / len(active_tasks) * 100)

    def start(self, actor_id: str) -> "ProjectEvent":
        """Перевод фазы в IN_PROGRESS + проставить actual_start_date."""
        if self.status != PhaseStatus.PENDING:
            raise ValueError(f"Можно стартовать только фазу в статусе PENDING (текущий: {self.status.value})")
        self.status = PhaseStatus.IN_PROGRESS
        self.actual_start_date = datetime.utcnow().date()
        return ProjectEvent(
            project_id=self.project_id,
            actor_id=actor_id,
            event_type="phase_started",
            description=f"Фаза «{self.name}» начата",
        )

    def complete(self, actor_id: str) -> "ProjectEvent":
        """Перевод фазы в COMPLETED + проставить actual_end_date + progress=100."""
        if self.status not in (PhaseStatus.IN_PROGRESS, PhaseStatus.BLOCKED):
            raise ValueError(
                f"Можно завершить только фазу в IN_PROGRESS/BLOCKED (текущий: {self.status.value})"
            )
        self.status = PhaseStatus.COMPLETED
        self.actual_end_date = datetime.utcnow().date()
        self.progress_pct = 100
        return ProjectEvent(
            project_id=self.project_id,
            actor_id=actor_id,
            event_type="phase_completed",
            description=f"Фаза «{self.name}» завершена",
        )


# ---------------------------------------------------------------------------
# Задача в фазе
# ---------------------------------------------------------------------------


class ProjectTask(SQLModel, table=True):
    __tablename__ = "project_tasks"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    phase_id: str = Field(foreign_key="project_phases.id", index=True)
    # денормализация для быстрых фильтров по проекту
    project_id: str = Field(foreign_key="implementation_projects.id", index=True)

    title: str = Field(max_length=256)
    description: Optional[str] = Field(default=None, max_length=2000)

    status: TaskStatus = Field(default=TaskStatus.TODO, index=True)
    priority: TaskPriority = Field(default=TaskPriority.NORMAL)

    assignee_id: Optional[str] = Field(default=None, index=True)
    due_date: Optional[date] = Field(default=None, index=True)

    order_num: int = Field(default=0)
    is_milestone: bool = Field(default=False, description="Ключевая веха → отдельные уведомления")

    estimated_hours: Optional[int] = Field(default=None)
    actual_hours: Optional[int] = Field(default=None)

    completed_at: Optional[datetime] = Field(default=None)
    completed_by: Optional[str] = Field(default=None)

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    # Связи
    phase: Optional["ProjectPhase"] = Relationship(back_populates="tasks")

    # ------------------------------------------------------------------
    # Бизнес-логика
    # ------------------------------------------------------------------

    def complete(self, actor_id: str) -> None:
        """Отметить задачу как выполненную."""
        if self.status == TaskStatus.CANCELLED:
            raise ValueError("Нельзя завершить отменённую задачу")
        if self.status == TaskStatus.DONE:
            return  # идемпотентно
        now = datetime.utcnow()
        self.status = TaskStatus.DONE
        self.completed_at = now
        self.completed_by = actor_id
        self.updated_at = now


# ---------------------------------------------------------------------------
# Документы проекта
# ---------------------------------------------------------------------------


class ProjectDocument(SQLModel, table=True):
    __tablename__ = "project_documents"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    project_id: str = Field(foreign_key="implementation_projects.id", index=True)
    phase_id: Optional[str] = Field(default=None, foreign_key="project_phases.id", index=True)
    task_id: Optional[str] = Field(default=None, foreign_key="project_tasks.id", index=True)

    document_type: str = Field(
        default=DocumentType.OTHER,
        sa_column=Column(String, index=True, default="other"),
    )
    name: str = Field(max_length=256)
    filename: str = Field(max_length=512)
    content_type: str = Field(max_length=128)
    size: int
    storage_path: str = Field(max_length=1024)
    version: int = Field(default=1)

    uploaded_by: str
    created_at: datetime = Field(default_factory=datetime.utcnow)

    project: Optional["ImplementationProject"] = Relationship(back_populates="documents")


# ---------------------------------------------------------------------------
# Участник команды проекта
# ---------------------------------------------------------------------------


class ProjectTeamMember(SQLModel, table=True):
    __tablename__ = "project_team_members"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    project_id: str = Field(foreign_key="implementation_projects.id", index=True)
    user_id: str = Field(index=True)

    team_role: str = Field(
        default=TeamRole.INSTALLER,
        sa_column=Column(String, index=True, default="installer"),
    )
    is_primary: bool = Field(default=False)

    added_by: str
    added_at: datetime = Field(default_factory=datetime.utcnow)

    project: Optional["ImplementationProject"] = Relationship(back_populates="team")


# ---------------------------------------------------------------------------
# Событие проекта (audit log)
# ---------------------------------------------------------------------------


class ProjectEvent(SQLModel, table=True):
    __tablename__ = "project_events"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    project_id: str = Field(foreign_key="implementation_projects.id", index=True)
    actor_id: Optional[str] = Field(default=None)
    event_type: str = Field(max_length=64, index=True)
    description: str = Field(max_length=1000)
    meta_json: Optional[str] = Field(default=None, description="JSON-строка с доп. данными")
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)

    project: Optional["ImplementationProject"] = Relationship(back_populates="events")


# ---------------------------------------------------------------------------
# Комментарии проекта / задачи
# ---------------------------------------------------------------------------


class ProjectComment(SQLModel, table=True):
    __tablename__ = "project_comments"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    project_id: str = Field(foreign_key="implementation_projects.id", index=True)
    task_id: Optional[str] = Field(default=None, foreign_key="project_tasks.id", index=True)

    author_id: str
    author_name: str = Field(default="", max_length=256)
    text: str = Field(max_length=4000)
    is_internal: bool = Field(default=False, description="Видно только команде PASS24")

    created_at: datetime = Field(default_factory=datetime.utcnow)

    project: Optional["ImplementationProject"] = Relationship(back_populates="comments")

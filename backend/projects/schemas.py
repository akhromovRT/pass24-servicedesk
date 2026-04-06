"""Pydantic-схемы для API модуля проектов внедрения."""

from __future__ import annotations

from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel, EmailStr, Field

from backend.projects.models import (
    DocumentType,
    PhaseStatus,
    ProjectStatus,
    ProjectType,
    TaskPriority,
    TaskStatus,
    TeamRole,
)


# ---------------------------------------------------------------------------
# Task schemas
# ---------------------------------------------------------------------------


class TaskRead(BaseModel):
    id: str
    phase_id: str
    project_id: str
    title: str
    description: Optional[str] = None
    status: TaskStatus
    priority: TaskPriority
    assignee_id: Optional[str] = None
    due_date: Optional[date] = None
    order_num: int
    is_milestone: bool
    estimated_hours: Optional[int] = None
    actual_hours: Optional[int] = None
    completed_at: Optional[datetime] = None
    completed_by: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TaskCreate(BaseModel):
    title: str = Field(..., max_length=256)
    description: Optional[str] = Field(default=None, max_length=2000)
    priority: TaskPriority = TaskPriority.NORMAL
    assignee_id: Optional[str] = None
    due_date: Optional[date] = None
    is_milestone: bool = False
    estimated_hours: Optional[int] = Field(default=None, ge=0)
    order_num: int = 0


class TaskUpdate(BaseModel):
    title: Optional[str] = Field(default=None, max_length=256)
    description: Optional[str] = Field(default=None, max_length=2000)
    status: Optional[TaskStatus] = None
    priority: Optional[TaskPriority] = None
    assignee_id: Optional[str] = None
    due_date: Optional[date] = None
    is_milestone: Optional[bool] = None
    estimated_hours: Optional[int] = Field(default=None, ge=0)
    actual_hours: Optional[int] = Field(default=None, ge=0)
    order_num: Optional[int] = None


# ---------------------------------------------------------------------------
# Phase schemas
# ---------------------------------------------------------------------------


class PhaseRead(BaseModel):
    id: str
    project_id: str
    name: str
    description: Optional[str] = None
    order_num: int
    status: PhaseStatus
    weight: int
    planned_duration_days: Optional[int] = None
    planned_start_date: Optional[date] = None
    planned_end_date: Optional[date] = None
    actual_start_date: Optional[date] = None
    actual_end_date: Optional[date] = None
    progress_pct: int
    tasks: List[TaskRead] = []
    created_at: datetime

    model_config = {"from_attributes": True}


class PhaseUpdate(BaseModel):
    name: Optional[str] = Field(default=None, max_length=256)
    description: Optional[str] = Field(default=None, max_length=2000)
    planned_start_date: Optional[date] = None
    planned_end_date: Optional[date] = None
    planned_duration_days: Optional[int] = Field(default=None, ge=0)
    weight: Optional[int] = Field(default=None, ge=1)


# ---------------------------------------------------------------------------
# Document schemas
# ---------------------------------------------------------------------------


class DocumentRead(BaseModel):
    id: str
    project_id: str
    phase_id: Optional[str] = None
    task_id: Optional[str] = None
    document_type: DocumentType
    name: str
    filename: str
    content_type: str
    size: int
    version: int
    uploaded_by: str
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Team schemas
# ---------------------------------------------------------------------------


class TeamMemberRead(BaseModel):
    id: str
    project_id: str
    user_id: str
    user_name: Optional[str] = None
    user_email: Optional[str] = None
    team_role: TeamRole
    is_primary: bool
    added_at: datetime

    model_config = {"from_attributes": True}


class TeamMemberCreate(BaseModel):
    user_id: str
    team_role: TeamRole
    is_primary: bool = False


# ---------------------------------------------------------------------------
# Event schemas
# ---------------------------------------------------------------------------


class EventRead(BaseModel):
    id: str
    project_id: str
    actor_id: Optional[str] = None
    event_type: str
    description: str
    meta_json: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Comment schemas
# ---------------------------------------------------------------------------


class CommentRead(BaseModel):
    id: str
    project_id: str
    task_id: Optional[str] = None
    author_id: str
    author_name: str
    text: str
    is_internal: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class CommentCreate(BaseModel):
    text: str = Field(..., min_length=1, max_length=4000)
    is_internal: bool = False
    task_id: Optional[str] = None


# ---------------------------------------------------------------------------
# Project schemas
# ---------------------------------------------------------------------------


class ProjectCreate(BaseModel):
    name: str = Field(..., max_length=256)
    customer_id: str
    customer_company: str = Field(..., max_length=256)
    object_name: str = Field(..., max_length=256)
    object_address: Optional[str] = Field(default=None, max_length=512)
    project_type: ProjectType = ProjectType.RESIDENTIAL
    contract_number: Optional[str] = Field(default=None, max_length=64)
    contract_signed_at: Optional[date] = None
    planned_start_date: Optional[date] = None
    planned_end_date: Optional[date] = None
    manager_id: Optional[str] = None
    notes: Optional[str] = Field(default=None, max_length=4000)
    send_welcome_email: bool = Field(default=False, description="Отправить welcome-email новому клиенту")
    customer_temp_password: Optional[str] = Field(default=None, description="Пароль для welcome-email (не сохраняется)")


class ProjectUpdate(BaseModel):
    name: Optional[str] = Field(default=None, max_length=256)
    customer_company: Optional[str] = Field(default=None, max_length=256)
    object_name: Optional[str] = Field(default=None, max_length=256)
    object_address: Optional[str] = Field(default=None, max_length=512)
    contract_number: Optional[str] = Field(default=None, max_length=64)
    contract_signed_at: Optional[date] = None
    planned_start_date: Optional[date] = None
    planned_end_date: Optional[date] = None
    manager_id: Optional[str] = None
    notes: Optional[str] = Field(default=None, max_length=4000)


class ProjectTransition(BaseModel):
    new_status: ProjectStatus


class ProjectListItem(BaseModel):
    """Упрощённая схема для списка проектов (без вложенных)."""

    id: str
    code: str
    name: str
    status: ProjectStatus
    project_type: ProjectType
    progress_pct: int
    customer_id: str
    customer_company: str
    object_name: str
    planned_end_date: Optional[date] = None
    manager_id: Optional[str] = None
    updated_at: datetime
    created_at: datetime

    model_config = {"from_attributes": True}


class ProjectRead(BaseModel):
    """Полная схема проекта с вложенными фазами/командой."""

    id: str
    code: str
    name: str
    status: ProjectStatus
    project_type: ProjectType
    progress_pct: int
    customer_id: str
    customer_company: str
    object_name: str
    object_address: Optional[str] = None
    contract_number: Optional[str] = None
    contract_signed_at: Optional[date] = None
    planned_start_date: Optional[date] = None
    planned_end_date: Optional[date] = None
    actual_start_date: Optional[date] = None
    actual_end_date: Optional[date] = None
    manager_id: Optional[str] = None
    notes: Optional[str] = None
    created_by: str
    created_at: datetime
    updated_at: datetime
    phases: List[PhaseRead] = []
    team: List[TeamMemberRead] = []
    document_count: int = 0
    open_tasks_count: int = 0

    model_config = {"from_attributes": True}


class ProjectListResponse(BaseModel):
    items: List[ProjectListItem]
    total: int
    page: int
    per_page: int


# ---------------------------------------------------------------------------
# Template schemas (read-only в MVP)
# ---------------------------------------------------------------------------


class TemplateTaskOut(BaseModel):
    title: str
    description: str
    is_milestone: bool
    estimated_hours: int


class TemplatePhaseOut(BaseModel):
    order: int
    name: str
    description: str
    duration_days: int
    weight: int
    tasks: List[TemplateTaskOut]


class TemplateOut(BaseModel):
    project_type: ProjectType
    title: str
    description: str
    total_duration_days: int
    phases: List[TemplatePhaseOut]


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------


class ProjectStats(BaseModel):
    total: int
    active: int  # PLANNING + IN_PROGRESS
    completed_this_month: int
    on_hold: int
    overdue: int  # planned_end_date < today и не completed
    by_type: dict  # { "residential": 3, "commercial": 2, ... }


# ---------------------------------------------------------------------------
# Ticket-link schemas
# ---------------------------------------------------------------------------


class TicketLinkRequest(BaseModel):
    ticket_id: str
    is_blocker: bool = False


class CustomerCreate(BaseModel):
    """Создание нового клиента-администратора УК прямо из формы проекта."""

    email: EmailStr
    full_name: str = Field(..., min_length=2, max_length=256)
    phone: Optional[str] = Field(default=None, max_length=20)
    company: str = Field(..., min_length=1, max_length=256, description="Название УК")


class CustomerCreated(BaseModel):
    """Ответ после создания клиента."""

    id: str
    email: str
    full_name: str
    temp_password: str  # отображается один раз админу

    model_config = {"from_attributes": True}


class LinkedTicket(BaseModel):
    """Краткая информация о связанном тикете."""

    id: str
    title: str
    status: str
    priority: str
    is_implementation_blocker: bool
    created_at: datetime
    creator_id: str

    model_config = {"from_attributes": True}

import uuid
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, List, Optional

from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    pass


# ---------------------------------------------------------------------------
# Перечисления (строковые значения для PostgreSQL)
# ---------------------------------------------------------------------------


class TicketStatus(str, Enum):
    """Статусы тикета — FSM с определёнными переходами."""

    NEW = "new"
    IN_PROGRESS = "in_progress"
    WAITING_FOR_USER = "waiting_for_user"
    RESOLVED = "resolved"
    CLOSED = "closed"


class TicketPriority(str, Enum):
    """Приоритеты тикета."""

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


# ---------------------------------------------------------------------------
# Таблица тикетов
# ---------------------------------------------------------------------------


class Ticket(SQLModel, table=True):
    """
    Доменная модель тикета PASS24 Service Desk.

    Хранит данные заявки, содержит бизнес-логику авто-приоритезации и FSM переходов.
    """

    __tablename__ = "tickets"

    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        primary_key=True,
    )
    creator_id: str = Field(index=True)
    title: str = Field(default="", max_length=200)
    description: str = Field(default="", max_length=4000)
    category: str = Field(default="general", max_length=64)
    status: TicketStatus = Field(default=TicketStatus.NEW)
    priority: TicketPriority = Field(default=TicketPriority.NORMAL)
    object_id: Optional[str] = Field(default=None)
    access_point_id: Optional[str] = Field(default=None)
    user_role: Optional[str] = Field(default=None, max_length=64)
    occurred_at: Optional[str] = Field(default=None, max_length=128)
    contact: Optional[str] = Field(default=None, max_length=128)
    urgent: bool = Field(default=False)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    # SLA
    first_response_at: Optional[datetime] = Field(default=None)
    resolved_at: Optional[datetime] = Field(default=None)
    sla_response_hours: Optional[int] = Field(default=4)
    sla_resolve_hours: Optional[int] = Field(default=24)

    # Связи (дочерние модели определены ниже)
    events: List["TicketEvent"] = Relationship(back_populates="ticket")
    comments: List["TicketComment"] = Relationship(back_populates="ticket")
    attachments: List["Attachment"] = Relationship(back_populates="ticket")

    # ------------------------------------------------------------------
    # Бизнес-логика
    # ------------------------------------------------------------------

    def assign_priority_based_on_context(self) -> None:
        """
        Простейшая логика авто-приоритезации тикета.

        Анализирует текст заголовка и описания по ключевым словам.
        """
        text = f"{self.title} {self.description}".lower()

        if any(kw in text for kw in ["не могу попасть", "не пускает", "дверь не открылась"]):
            self.priority = TicketPriority.CRITICAL
        elif any(kw in text for kw in ["шлагбаум", "парковка"]):
            self.priority = TicketPriority.HIGH
        elif "уведомлен" in text or "пуш" in text:
            self.priority = TicketPriority.LOW
        else:
            self.priority = TicketPriority.NORMAL

    def transition(self, actor_id: str, new_status: TicketStatus) -> "TicketEvent":
        """
        Управление статусами с бизнес-правилами (FSM).

        Правила:
        - NEW -> IN_PROGRESS / RESOLVED
        - IN_PROGRESS -> WAITING_FOR_USER / RESOLVED
        - WAITING_FOR_USER -> IN_PROGRESS / RESOLVED
        - RESOLVED -> CLOSED / IN_PROGRESS
        - CLOSED — терминальное состояние (переход запрещён)

        Возвращает созданный TicketEvent для последующего сохранения в БД.
        """
        if self.status == TicketStatus.CLOSED:
            raise ValueError("Нельзя менять статус закрытого тикета")

        allowed = {
            TicketStatus.NEW: {TicketStatus.IN_PROGRESS, TicketStatus.RESOLVED},
            TicketStatus.IN_PROGRESS: {TicketStatus.WAITING_FOR_USER, TicketStatus.RESOLVED},
            TicketStatus.WAITING_FOR_USER: {TicketStatus.IN_PROGRESS, TicketStatus.RESOLVED},
            TicketStatus.RESOLVED: {TicketStatus.CLOSED, TicketStatus.IN_PROGRESS},
        }

        current_allowed = allowed.get(self.status, set())
        if new_status not in current_allowed:
            raise ValueError(
                f"Недопустимый переход статуса: {self.status.value} -> {new_status.value}"
            )

        self.status = new_status
        self.updated_at = datetime.utcnow()

        # SLA-таймстампы
        if new_status == TicketStatus.IN_PROGRESS and self.first_response_at is None:
            self.first_response_at = datetime.utcnow()
        if new_status == TicketStatus.RESOLVED:
            self.resolved_at = datetime.utcnow()
        elif new_status == TicketStatus.IN_PROGRESS and self.resolved_at is not None:
            # Переоткрытие — сбросить resolved_at
            self.resolved_at = None

        event = TicketEvent(
            ticket_id=self.id,
            actor_id=actor_id,
            description=f"Статус изменён на {new_status.value}",
        )
        return event


# ---------------------------------------------------------------------------
# Таблица событий тикета (аудит)
# ---------------------------------------------------------------------------


class TicketEvent(SQLModel, table=True):
    """Историческое событие по тикету (для аудита)."""

    __tablename__ = "ticket_events"

    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        primary_key=True,
    )
    ticket_id: str = Field(foreign_key="tickets.id", index=True)
    actor_id: Optional[str] = Field(default=None)
    description: str
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Связь обратно к тикету
    ticket: Optional["Ticket"] = Relationship(back_populates="events")


# ---------------------------------------------------------------------------
# Таблица комментариев
# ---------------------------------------------------------------------------


class TicketComment(SQLModel, table=True):
    """Комментарий к тикету."""

    __tablename__ = "ticket_comments"

    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        primary_key=True,
    )
    ticket_id: str = Field(foreign_key="tickets.id", index=True)
    author_id: str
    author_name: str = Field(default="")
    text: str
    is_internal: bool = Field(default=False)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Связь обратно к тикету
    ticket: Optional["Ticket"] = Relationship(back_populates="comments")


# ---------------------------------------------------------------------------
# Таблица вложений
# ---------------------------------------------------------------------------


class Attachment(SQLModel, table=True):
    """Вложение к тикету (файл)."""

    __tablename__ = "attachments"

    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        primary_key=True,
    )
    ticket_id: str = Field(foreign_key="tickets.id", index=True)
    uploader_id: str
    filename: str = Field(max_length=512)
    content_type: str = Field(max_length=128)
    size: int
    storage_path: str = Field(max_length=1024)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Связь обратно к тикету
    ticket: Optional["Ticket"] = Relationship(back_populates="attachments")

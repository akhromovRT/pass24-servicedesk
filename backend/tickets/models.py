import uuid
from datetime import datetime
from enum import Enum
from typing import List, Optional

from sqlmodel import Column, Field, Relationship, SQLModel, String


# ---------------------------------------------------------------------------
# Перечисления
# ---------------------------------------------------------------------------


class TicketStatus(str, Enum):
    NEW = "new"
    IN_PROGRESS = "in_progress"
    WAITING_FOR_USER = "waiting_for_user"
    RESOLVED = "resolved"
    CLOSED = "closed"


class TicketPriority(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class TicketProduct(str, Enum):
    """Продукт PASS24, к которому относится заявка."""
    PASS24_ONLINE = "pass24_online"
    MOBILE_APP = "mobile_app"
    PASS24_KEY = "pass24_key"
    PASS24_CONTROL = "pass24_control"
    PASS24_AUTO = "pass24_auto"
    EQUIPMENT = "equipment"
    INTEGRATION = "integration"
    OTHER = "other"


class TicketCategory(str, Enum):
    """Категория проблемы (уточняет продукт)."""
    REGISTRATION = "registration"
    PASSES = "passes"
    RECOGNITION = "recognition"
    APP_ISSUES = "app_issues"
    OBJECTS = "objects"
    TRUSTED_PERSONS = "trusted_persons"
    EQUIPMENT_ISSUES = "equipment_issues"
    CONSULTATION = "consultation"
    FEATURE_REQUEST = "feature_request"
    OTHER = "other"


class TicketType(str, Enum):
    """Тип обращения по ITIL — влияет на SLA и процесс."""
    INCIDENT = "incident"            # Нарушение работы сервиса → быстрое восстановление
    PROBLEM = "problem"              # Корневая причина инцидентов → глубокий анализ
    SERVICE_REQUEST = "service_request"  # Стандартный запрос (создать пропуск, настроить)
    CHANGE_REQUEST = "change_request"    # Изменение системы → требует согласования
    QUESTION = "question"            # Консультация / вопрос
    FEATURE_REQUEST = "feature_request"  # Идея / предложение


class TicketImpact(str, Enum):
    """Масштаб воздействия (сколько пользователей затронуто)."""
    HIGH = "high"      # Все пользователи / весь объект
    MEDIUM = "medium"  # Группа пользователей / один подъезд / один КПП
    LOW = "low"        # Один пользователь


class TicketUrgency(str, Enum):
    """Срочность решения."""
    HIGH = "high"      # Немедленно
    MEDIUM = "medium"  # Сегодня
    LOW = "low"        # Может подождать


class AssignmentGroup(str, Enum):
    """Группа распределения — команда, отвечающая за тикет."""
    L1_SUPPORT = "l1_support"         # Первая линия, типовые вопросы
    L2_ENGINEERS = "l2_engineers"     # Инженеры, сложные инциденты
    L3_DEVELOPMENT = "l3_development" # Разработка, код, БД
    INSTALLERS = "installers"         # Монтажники, оборудование
    INTEGRATIONS = "integrations"     # Интеграции с внешними системами
    BILLING = "billing"               # Биллинг, контракты
    UNASSIGNED = "unassigned"         # Не назначена


class TicketSource(str, Enum):
    """Канал поступления заявки."""
    WEB = "web"
    EMAIL = "email"
    TELEGRAM = "telegram"
    API = "api"
    PHONE = "phone"


# SLA по приоритетам (часы): (response, resolve)
SLA_TABLE = {
    TicketPriority.CRITICAL: (1, 4),
    TicketPriority.HIGH: (2, 8),
    TicketPriority.NORMAL: (4, 24),
    TicketPriority.LOW: (8, 48),
}


# ITIL матрица Priority = f(Impact, Urgency)
PRIORITY_MATRIX = {
    (TicketImpact.HIGH, TicketUrgency.HIGH): TicketPriority.CRITICAL,
    (TicketImpact.HIGH, TicketUrgency.MEDIUM): TicketPriority.HIGH,
    (TicketImpact.HIGH, TicketUrgency.LOW): TicketPriority.NORMAL,
    (TicketImpact.MEDIUM, TicketUrgency.HIGH): TicketPriority.HIGH,
    (TicketImpact.MEDIUM, TicketUrgency.MEDIUM): TicketPriority.NORMAL,
    (TicketImpact.MEDIUM, TicketUrgency.LOW): TicketPriority.LOW,
    (TicketImpact.LOW, TicketUrgency.HIGH): TicketPriority.NORMAL,
    (TicketImpact.LOW, TicketUrgency.MEDIUM): TicketPriority.LOW,
    (TicketImpact.LOW, TicketUrgency.LOW): TicketPriority.LOW,
}


# Авто-маршрутизация по product → assignment_group
PRODUCT_TO_GROUP = {
    TicketProduct.PASS24_ONLINE: AssignmentGroup.L1_SUPPORT,
    TicketProduct.MOBILE_APP: AssignmentGroup.L1_SUPPORT,
    TicketProduct.PASS24_KEY: AssignmentGroup.L2_ENGINEERS,
    TicketProduct.PASS24_CONTROL: AssignmentGroup.L2_ENGINEERS,
    TicketProduct.PASS24_AUTO: AssignmentGroup.L2_ENGINEERS,
    TicketProduct.EQUIPMENT: AssignmentGroup.INSTALLERS,
    TicketProduct.INTEGRATION: AssignmentGroup.INTEGRATIONS,
    TicketProduct.OTHER: AssignmentGroup.L1_SUPPORT,
}


# ---------------------------------------------------------------------------
# Таблица тикетов
# ---------------------------------------------------------------------------


class Ticket(SQLModel, table=True):
    """Доменная модель тикета PASS24 Service Desk."""

    __tablename__ = "tickets"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    creator_id: str = Field(index=True)
    assignee_id: Optional[str] = Field(default=None, index=True)
    assignment_group: str = Field(
        default=AssignmentGroup.UNASSIGNED,
        sa_column=Column(String, index=True, default="unassigned"),
    )

    # Основные
    title: str = Field(default="", max_length=200)
    description: str = Field(default="", max_length=4000)

    # 5-осевая классификация
    product: str = Field(default=TicketProduct.PASS24_ONLINE, sa_column=Column(String, index=True, default="pass24_online"))
    category: str = Field(default=TicketCategory.OTHER, sa_column=Column(String, index=True, default="other"))
    ticket_type: str = Field(default=TicketType.INCIDENT, sa_column=Column(String, index=True, default="incident"))
    source: str = Field(default=TicketSource.WEB, sa_column=Column(String, index=True, default="web"))
    status: TicketStatus = Field(default=TicketStatus.NEW)

    # Приоритет по ITIL: impact × urgency → priority
    impact: str = Field(default=TicketImpact.LOW, sa_column=Column(String, index=True, default="low"))
    urgency: str = Field(default=TicketUrgency.MEDIUM, sa_column=Column(String, index=True, default="medium"))
    priority: TicketPriority = Field(default=TicketPriority.NORMAL)

    # Объект
    object_name: Optional[str] = Field(default=None, max_length=256)
    object_address: Optional[str] = Field(default=None, max_length=512)
    access_point: Optional[str] = Field(default=None, max_length=128)

    # Контакт
    contact_name: Optional[str] = Field(default=None, max_length=256)
    contact_email: Optional[str] = Field(default=None, max_length=320)
    contact_phone: Optional[str] = Field(default=None, max_length=20)
    company: Optional[str] = Field(default=None, max_length=256)

    # Техническая информация
    device_type: Optional[str] = Field(default=None, max_length=32)
    app_version: Optional[str] = Field(default=None, max_length=32)
    error_message: Optional[str] = Field(default=None, max_length=500)

    # Флаги
    urgent: bool = Field(default=False)

    # Временные метки
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    # SLA
    first_response_at: Optional[datetime] = Field(default=None)
    resolved_at: Optional[datetime] = Field(default=None)
    sla_response_hours: Optional[int] = Field(default=4)
    sla_resolve_hours: Optional[int] = Field(default=24)
    sla_breached: bool = Field(default=False)
    # SLA pause: когда тикет в WAITING_FOR_USER — часы не тикают
    sla_paused_at: Optional[datetime] = Field(default=None)
    sla_total_pause_seconds: int = Field(default=0)

    # CSAT (Customer Satisfaction)
    satisfaction_rating: Optional[int] = Field(default=None, description="Оценка 1-5")
    satisfaction_comment: Optional[str] = Field(default=None, max_length=2000)
    satisfaction_requested_at: Optional[datetime] = Field(default=None)
    satisfaction_submitted_at: Optional[datetime] = Field(default=None)

    # Связи
    events: List["TicketEvent"] = Relationship(back_populates="ticket")
    comments: List["TicketComment"] = Relationship(back_populates="ticket")
    attachments: List["Attachment"] = Relationship(back_populates="ticket")

    # ------------------------------------------------------------------
    # Бизнес-логика
    # ------------------------------------------------------------------

    def assign_priority_based_on_context(self) -> None:
        """Авто-приоритезация: emergency override + ITIL matrix."""
        text = f"{self.title} {self.description}".lower()

        # Emergency override: клиент заблокирован физически → CRITICAL
        if self.urgent or any(kw in text for kw in [
            "не могу попасть", "не пускает", "дверь не открылась",
            "заблокирован", "не могу войти", "не могу проехать",
        ]):
            self.impact = TicketImpact.HIGH
            self.urgency = TicketUrgency.HIGH
            self.priority = TicketPriority.CRITICAL
        # Проблемы с шлагбаумом/парковкой → HIGH
        elif any(kw in text for kw in ["шлагбаум", "парковка", "ворота"]):
            self.impact = TicketImpact.MEDIUM
            self.urgency = TicketUrgency.HIGH
            self.priority = TicketPriority.HIGH
        # Уведомления/push — LOW
        elif "уведомлен" in text or "пуш" in text:
            self.urgency = TicketUrgency.LOW
            self.priority = TicketPriority.LOW
        # Вопросы / предложения → LOW
        elif self.ticket_type in (TicketType.QUESTION, TicketType.FEATURE_REQUEST):
            self.urgency = TicketUrgency.LOW
            self.priority = TicketPriority.LOW
        else:
            # Дефолт: NORMAL через матрицу (LOW impact, MEDIUM urgency)
            self.priority = PRIORITY_MATRIX.get(
                (TicketImpact(self.impact), TicketUrgency(self.urgency)),
                TicketPriority.NORMAL,
            )
            # Если получилось LOW — поднимаем до NORMAL для общих случаев
            if self.priority == TicketPriority.LOW:
                self.priority = TicketPriority.NORMAL

        # SLA из приоритета
        response_h, resolve_h = SLA_TABLE.get(self.priority, (4, 24))
        self.sla_response_hours = response_h
        self.sla_resolve_hours = resolve_h

    def recalculate_priority(self) -> None:
        """Пересчёт priority из impact + urgency (для ручного изменения)."""
        self.priority = PRIORITY_MATRIX.get(
            (TicketImpact(self.impact), TicketUrgency(self.urgency)),
            TicketPriority.NORMAL,
        )
        response_h, resolve_h = SLA_TABLE.get(self.priority, (4, 24))
        self.sla_response_hours = response_h
        self.sla_resolve_hours = resolve_h

    def auto_assign_group(self) -> None:
        """Авто-назначение assignment_group по product."""
        if self.assignment_group == AssignmentGroup.UNASSIGNED:
            group = PRODUCT_TO_GROUP.get(
                TicketProduct(self.product) if self.product else TicketProduct.OTHER,
                AssignmentGroup.L1_SUPPORT,
            )
            self.assignment_group = group

    def auto_detect_category(self) -> None:
        """Авто-определение category и product по ключевым словам."""
        text = f"{self.title} {self.description}".lower()

        # Product
        if any(kw in text for kw in ["pass24.key", "ble", "bluetooth", "мобильный ключ"]):
            self.product = TicketProduct.PASS24_KEY
        elif any(kw in text for kw in ["pass24.control", "скуд", "контроллер"]):
            self.product = TicketProduct.PASS24_CONTROL
        elif any(kw in text for kw in ["распознавание", "камера", "номер авто", "pass24.auto"]):
            self.product = TicketProduct.PASS24_AUTO
        elif any(kw in text for kw in ["оборудование", "считыватель", "замок"]):
            self.product = TicketProduct.EQUIPMENT
        elif any(kw in text for kw in ["интеграция", "sigur", "trassir", "zkteco"]):
            self.product = TicketProduct.INTEGRATION
        elif any(kw in text for kw in ["приложение", "мобильное", "android", "ios", "app store", "google play"]):
            self.product = TicketProduct.MOBILE_APP

        # Category
        if any(kw in text for kw in ["регистрац", "sms", "код", "пароль", "войти", "вход", "логин"]):
            self.category = TicketCategory.REGISTRATION
        elif any(kw in text for kw in ["пропуск", "qr", "гостевой", "постоянный пропуск"]):
            self.category = TicketCategory.PASSES
        elif any(kw in text for kw in ["распознавание", "номер авто", "камера не считывает"]):
            self.category = TicketCategory.RECOGNITION
        elif any(kw in text for kw in ["вылетает", "зависает", "не загружается", "ошибка приложения"]):
            self.category = TicketCategory.APP_ISSUES
        elif any(kw in text for kw in ["объект", "жк", "бц", "добавить объект"]):
            self.category = TicketCategory.OBJECTS
        elif any(kw in text for kw in ["доверенн", "доверенность"]):
            self.category = TicketCategory.TRUSTED_PERSONS
        elif any(kw in text for kw in ["оборудование", "считыватель", "контроллер"]):
            self.category = TicketCategory.EQUIPMENT_ISSUES
        elif any(kw in text for kw in ["предложен", "идея", "хотелось бы", "было бы здорово"]):
            self.category = TicketCategory.FEATURE_REQUEST

    def transition(self, actor_id: str, new_status: TicketStatus) -> "TicketEvent":
        """FSM переходов статусов."""
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

        now = datetime.utcnow()
        prev_status = self.status
        self.status = new_status
        self.updated_at = now

        # SLA pause: при входе в WAITING_FOR_USER — ставим на паузу
        if new_status == TicketStatus.WAITING_FOR_USER and self.sla_paused_at is None:
            self.sla_paused_at = now
        # При выходе из WAITING_FOR_USER — суммируем паузу и сбрасываем
        if prev_status == TicketStatus.WAITING_FOR_USER and self.sla_paused_at is not None:
            pause_seconds = int((now - self.sla_paused_at).total_seconds())
            self.sla_total_pause_seconds += pause_seconds
            self.sla_paused_at = None

        if new_status == TicketStatus.IN_PROGRESS and self.first_response_at is None:
            self.first_response_at = now
        if new_status == TicketStatus.RESOLVED:
            self.resolved_at = now
            self.satisfaction_requested_at = now
        elif new_status == TicketStatus.IN_PROGRESS and self.resolved_at is not None:
            self.resolved_at = None

        return TicketEvent(
            ticket_id=self.id,
            actor_id=actor_id,
            description=f"Статус изменён на {new_status.value}",
        )


# ---------------------------------------------------------------------------
# Таблица событий тикета (аудит)
# ---------------------------------------------------------------------------


class TicketEvent(SQLModel, table=True):
    __tablename__ = "ticket_events"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    ticket_id: str = Field(foreign_key="tickets.id", index=True)
    actor_id: Optional[str] = Field(default=None)
    description: str
    created_at: datetime = Field(default_factory=datetime.utcnow)

    ticket: Optional["Ticket"] = Relationship(back_populates="events")


# ---------------------------------------------------------------------------
# Таблица комментариев
# ---------------------------------------------------------------------------


class TicketComment(SQLModel, table=True):
    __tablename__ = "ticket_comments"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    ticket_id: str = Field(foreign_key="tickets.id", index=True)
    author_id: str
    author_name: str = Field(default="")
    text: str
    is_internal: bool = Field(default=False)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    ticket: Optional["Ticket"] = Relationship(back_populates="comments")


# ---------------------------------------------------------------------------
# Таблица вложений
# ---------------------------------------------------------------------------


class Attachment(SQLModel, table=True):
    __tablename__ = "attachments"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    ticket_id: str = Field(foreign_key="tickets.id", index=True)
    uploader_id: str
    filename: str = Field(max_length=512)
    content_type: str = Field(max_length=128)
    size: int
    storage_path: str = Field(max_length=1024)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    ticket: Optional["Ticket"] = Relationship(back_populates="attachments")

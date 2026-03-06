from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import List, Optional


class TicketStatus(Enum):
    NEW = auto()
    IN_PROGRESS = auto()
    WAITING_FOR_USER = auto()
    RESOLVED = auto()
    CLOSED = auto()


class TicketPriority(Enum):
    LOW = auto()
    NORMAL = auto()
    HIGH = auto()
    CRITICAL = auto()


@dataclass
class TicketEvent:
    """Историческое событие по тикету (для аудита и тестов)."""

    at: datetime
    actor_id: str
    description: str


@dataclass
class Ticket:
    """
    Упрощённая доменная модель тикета для PASS24 Service Desk.

    Сделана без внешних зависимостей, чтобы использовать прямо в юнит‑тестах.
    """

    id: str
    creator_id: str
    object_id: Optional[str] = None  # ЖК / БЦ
    access_point_id: Optional[str] = None  # дверь / домофон / шлагбаум
    category: str = "general"
    title: str = ""
    description: str = ""
    status: TicketStatus = TicketStatus.NEW
    priority: TicketPriority = TicketPriority.NORMAL
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    events: List[TicketEvent] = field(default_factory=list)

    def _add_event(self, actor_id: str, description: str) -> None:
        self.events.append(
            TicketEvent(
                at=datetime.utcnow(),
                actor_id=actor_id,
                description=description,
            )
        )
        self.updated_at = datetime.utcnow()

    def assign_priority_based_on_context(self) -> None:
        """
        Простейшая логика авто‑приоритезации тикета.

        Её удобно покрывать юнит‑тестами, не поднимая весь backend.
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

    def transition(self, actor_id: str, new_status: TicketStatus) -> None:
        """
        Управление статусами с простыми бизнес‑правилами.

        Правила:
        - NEW → IN_PROGRESS / RESOLVED
        - IN_PROGRESS → WAITING_FOR_USER / RESOLVED
        - WAITING_FOR_USER → IN_PROGRESS / RESOLVED
        - RESOLVED → CLOSED / IN_PROGRESS
        - CLOSED — терминальное состояние (дальше переход запрещён)
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
            raise ValueError(f"Недопустимый переход статуса: {self.status.name} → {new_status.name}")

        self.status = new_status
        self._add_event(actor_id=actor_id, description=f"Статус изменён на {new_status.name}")


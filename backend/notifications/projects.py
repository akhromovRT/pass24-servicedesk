"""Email-уведомления для модуля проектов внедрения.

Отправляем только на ключевые события (не спамим):
- Создание проекта (customer + manager)
- Завершение milestone-фазы (customer + manager)
- Достижение milestone-задачи (customer + manager)
- Изменение статуса проекта (customer + manager)
"""

from __future__ import annotations

import logging

from backend.notifications.email import _send_email

logger = logging.getLogger(__name__)


PROJECT_STATUS_LABELS = {
    "draft": "Черновик",
    "planning": "Планирование",
    "in_progress": "В работе",
    "on_hold": "На паузе",
    "completed": "Завершён",
    "cancelled": "Отменён",
}


async def notify_project_created(
    customer_email: str,
    project_code: str,
    project_name: str,
    object_name: str,
    manager_email: str | None = None,
) -> None:
    """Уведомление о создании проекта внедрения."""
    subject = f"[{project_code}] Создан проект внедрения: {project_name}"
    html = f"""
    <h2>Создан проект внедрения PASS24</h2>
    <p>Здравствуйте!</p>
    <p>Для объекта <strong>{object_name}</strong> создан проект внедрения:</p>
    <ul>
        <li><strong>Код проекта:</strong> {project_code}</li>
        <li><strong>Название:</strong> {project_name}</li>
    </ul>
    <p>
        Отслеживать прогресс внедрения можно в личном кабинете
        <a href="https://support.pass24pro.ru/projects">поддержки PASS24</a>.
    </p>
    <hr>
    <p style="color: #666; font-size: 0.9em;">
        Это автоматическое сообщение от PASS24 Service Desk.
    </p>
    """
    await _send_email(customer_email, subject, html)
    if manager_email:
        await _send_email(manager_email, subject, html)


async def notify_project_status_changed(
    customer_email: str,
    project_code: str,
    project_name: str,
    new_status: str,
    changed_by: str,
    manager_email: str | None = None,
) -> None:
    """Уведомление об изменении статуса проекта."""
    status_label = PROJECT_STATUS_LABELS.get(new_status, new_status)
    subject = f"[{project_code}] Статус проекта: {status_label}"
    html = f"""
    <h2>Изменён статус проекта внедрения</h2>
    <p>Проект <strong>{project_name}</strong> переведён в статус <strong>{status_label}</strong>.</p>
    <p>Кто изменил: {changed_by}</p>
    <p>
        Подробнее — в личном кабинете
        <a href="https://support.pass24pro.ru/projects">поддержки PASS24</a>.
    </p>
    """
    await _send_email(customer_email, subject, html)
    if manager_email:
        await _send_email(manager_email, subject, html)


async def notify_phase_completed(
    customer_email: str,
    project_code: str,
    project_name: str,
    phase_name: str,
    progress_pct: int,
    manager_email: str | None = None,
) -> None:
    """Уведомление о завершении фазы проекта."""
    subject = f"[{project_code}] Завершён этап: {phase_name}"
    html = f"""
    <h2>Завершён этап проекта внедрения</h2>
    <p>
        В проекте <strong>{project_name}</strong> завершён этап
        <strong>«{phase_name}»</strong>.
    </p>
    <p>Общий прогресс проекта: <strong>{progress_pct}%</strong></p>
    <p>
        Подробности — в личном кабинете
        <a href="https://support.pass24pro.ru/projects">поддержки PASS24</a>.
    </p>
    """
    await _send_email(customer_email, subject, html)
    if manager_email:
        await _send_email(manager_email, subject, html)


async def notify_milestone_reached(
    customer_email: str,
    project_code: str,
    project_name: str,
    milestone_title: str,
    completed_by: str,
    manager_email: str | None = None,
) -> None:
    """Уведомление о достижении ключевой вехи проекта (milestone-задача)."""
    subject = f"[{project_code}] Достигнута веха: {milestone_title}"
    html = f"""
    <h2>Достигнута ключевая веха проекта</h2>
    <p>
        В проекте <strong>{project_name}</strong> достигнута веха
        <strong>«{milestone_title}»</strong>.
    </p>
    <p>Выполнил: {completed_by}</p>
    <p>
        Подробности — в личном кабинете
        <a href="https://support.pass24pro.ru/projects">поддержки PASS24</a>.
    </p>
    """
    await _send_email(customer_email, subject, html)
    if manager_email:
        await _send_email(manager_email, subject, html)

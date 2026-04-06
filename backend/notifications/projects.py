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


async def notify_customer_welcome(
    customer_email: str,
    customer_name: str,
    temp_password: str,
    project_code: str,
    project_name: str,
    object_name: str,
    phases_html: str,
) -> None:
    """Welcome-письмо новому клиенту: доступ к порталу, проект, этапы внедрения."""
    subject = f"Добро пожаловать в PASS24 — проект внедрения {project_code}"
    html = f"""
    <div style="font-family: -apple-system, sans-serif; max-width: 600px; margin: 0 auto;">
      <h2 style="color: #1e293b;">Добро пожаловать в PASS24 Service Desk!</h2>
      <p>Здравствуйте, <strong>{customer_name}</strong>!</p>

      <p>Для вашего объекта <strong>«{object_name}»</strong> запущен проект внедрения
      системы контроля доступа PASS24.</p>

      <div style="background: #f8fafc; border-radius: 8px; padding: 16px; margin: 16px 0;">
        <h3 style="margin-top: 0; color: #3b82f6;">Ваш доступ к порталу</h3>
        <p><strong>��ортал:</strong> <a href="https://support.pass24pro.ru">support.pass24pro.ru</a></p>
        <p><strong>Email (логин):</strong> {customer_email}</p>
        <p><strong>Временный пароль:</strong> <code style="background:#e2e8f0; padding:2px 6px; border-radius:3px;">{temp_password}</code></p>
        <p style="color: #ef4444; font-size: 0.9em;">Рекомендуем сменить паро��ь при первом входе.</p>
      </div>

      <h3 style="color: #1e293b;">Что вы можете делать на портале:</h3>
      <ul>
        <li><strong>Проекты внедрения</strong> — отслежи��ать прогресс, этапы, задачи, загружать документы</li>
        <li><strong>Мои заявки</strong> — создавать тикеты по вопросам �� проблемам</li>
        <li><strong>База знаний</strong> — FAQ, инструкции, руководства</li>
      </ul>

      <div style="background: #f0f9ff; border-left: 4px solid #3b82f6; padding: 12px 16px; margin: 16px 0;">
        <h3 style="margin-top: 0; color: #1e40af;">Проект: {project_code} — {project_name}</h3>
        <p style="margin-bottom: 8px;">Этапы внедрения:</p>
        {phases_html}
      </div>

      <p>По всем вопросам обращайтесь через портал или по email
      <a href="mailto:support@pass24online.ru">support@pass24online.ru</a>.</p>

      <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 24px 0;">
      <p style="color: #94a3b8; font-size: 0.85em;">
        Это автоматическое сообщение от PASS24 Service Desk.
      </p>
    </div>
    """
    await _send_email(customer_email, subject, html)


async def notify_project_created(
    customer_email: str,
    project_code: str,
    project_name: str,
    object_name: str,
    phases_summary: str = "",
    manager_email: str | None = None,
) -> None:
    """Уведомление о создании проекта внедрения (для существующего клиента)."""
    subject = f"[{project_code}] Создан проект внедрения: {project_name}"
    html = f"""
    <h2>Создан проект внедрения PASS24</h2>
    <p>Здравствуйте!</p>
    <p>Для объекта <strong>{object_name}</strong> создан проект внедрения:</p>
    <ul>
        <li><strong>Код проекта:</strong> {project_code}</li>
        <li><strong>Название:</strong> {project_name}</li>
    </ul>
    {f'<h3>Этапы внедрения:</h3>{phases_summary}' if phases_summary else ''}
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

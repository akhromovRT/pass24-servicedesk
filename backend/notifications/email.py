from __future__ import annotations

import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import aiosmtplib

from backend.config import settings

logger = logging.getLogger(__name__)

STATUS_LABELS = {
    "new": "Новый",
    "in_progress": "В работе",
    "waiting_for_user": "Ожидает ответа",
    "resolved": "Решён",
    "closed": "Закрыт",
}

PRIORITY_LABELS = {
    "critical": "Критический",
    "high": "Высокий",
    "normal": "Обычный",
    "low": "Низкий",
}


async def _send_email(to: str, subject: str, html_body: str) -> None:
    """Отправка email через SMTP. Ошибки логируются, но не прерывают работу."""
    if not settings.smtp_password:
        logger.warning("SMTP_PASSWORD не задан — email не отправлен: %s", subject)
        return

    msg = MIMEMultipart("alternative")
    msg["From"] = f"PASS24 Service Desk <{settings.smtp_from}>"
    msg["To"] = to
    msg["Subject"] = subject
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    try:
        await aiosmtplib.send(
            msg,
            hostname=settings.smtp_host,
            port=settings.smtp_port,
            username=settings.smtp_user,
            password=settings.smtp_password,
            use_tls=settings.smtp_use_ssl,
        )
        logger.info("Email отправлен: %s -> %s", subject, to)
    except Exception as exc:
        logger.error("Ошибка отправки email: %s — %s", subject, exc)


def ticket_subject_tag(ticket_id: str) -> str:
    """Формирует тег тикета для темы письма: [PASS24-abc12345]."""
    return f"[PASS24-{ticket_id[:8]}]"


async def notify_ticket_created(
    creator_email: str,
    ticket_id: str,
    title: str,
    priority: str,
) -> None:
    """Уведомление о создании тикета."""
    priority_label = PRIORITY_LABELS.get(priority, priority)
    tag = ticket_subject_tag(ticket_id)
    await _send_email(
        to=creator_email,
        subject=f"{tag} Заявка создана: {title}",
        html_body=f"""
        <div style="font-family: -apple-system, Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <div style="background: #0f172a; color: #f8fafc; padding: 16px 24px; border-radius: 8px 8px 0 0;">
                <strong>PASS24 Service Desk</strong>
            </div>
            <div style="padding: 24px; background: #fff; border: 1px solid #e2e8f0; border-top: none; border-radius: 0 0 8px 8px;">
                <h2 style="margin: 0 0 16px; color: #1e293b;">Заявка создана</h2>
                <p style="color: #475569; margin: 0 0 12px;"><strong>Тема:</strong> {title}</p>
                <p style="color: #475569; margin: 0 0 12px;"><strong>Приоритет:</strong> {priority_label}</p>
                <p style="color: #475569; margin: 0 0 12px;"><strong>ID:</strong> {ticket_id[:8]}...</p>
                <p style="color: #64748b; font-size: 14px; margin: 16px 0 0;">
                    Мы получили вашу заявку и приступим к её рассмотрению в ближайшее время.
                </p>
            </div>
        </div>
        """,
    )


async def notify_ticket_status_changed(
    creator_email: str,
    ticket_id: str,
    title: str,
    old_status: str,
    new_status: str,
    actor_name: str,
) -> None:
    """Уведомление о смене статуса тикета."""
    old_label = STATUS_LABELS.get(old_status, old_status)
    new_label = STATUS_LABELS.get(new_status, new_status)
    tag = ticket_subject_tag(ticket_id)
    await _send_email(
        to=creator_email,
        subject=f"{tag} Статус заявки изменён: {title}",
        html_body=f"""
        <div style="font-family: -apple-system, Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <div style="background: #0f172a; color: #f8fafc; padding: 16px 24px; border-radius: 8px 8px 0 0;">
                <strong>PASS24 Service Desk</strong>
            </div>
            <div style="padding: 24px; background: #fff; border: 1px solid #e2e8f0; border-top: none; border-radius: 0 0 8px 8px;">
                <h2 style="margin: 0 0 16px; color: #1e293b;">Статус заявки изменён</h2>
                <p style="color: #475569; margin: 0 0 12px;"><strong>Тема:</strong> {title}</p>
                <p style="color: #475569; margin: 0 0 12px;">
                    <strong>Статус:</strong>
                    <span style="text-decoration: line-through; color: #94a3b8;">{old_label}</span>
                    →
                    <span style="color: #059669; font-weight: 600;">{new_label}</span>
                </p>
                <p style="color: #475569; margin: 0 0 12px;"><strong>Изменил:</strong> {actor_name}</p>
                <p style="color: #64748b; font-size: 14px; margin: 16px 0 0;">
                    Вы можете отслеживать статус заявки в личном кабинете Service Desk.
                </p>
            </div>
        </div>
        """,
    )


async def notify_ticket_comment(
    creator_email: str,
    ticket_id: str,
    title: str,
    comment_text: str,
    author_name: str,
) -> None:
    """Уведомление о новом комментарии к тикету."""
    tag = ticket_subject_tag(ticket_id)
    await _send_email(
        to=creator_email,
        subject=f"{tag} Новый комментарий: {title}",
        html_body=f"""
        <div style="font-family: -apple-system, Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <div style="background: #0f172a; color: #f8fafc; padding: 16px 24px; border-radius: 8px 8px 0 0;">
                <strong>PASS24 Service Desk</strong>
            </div>
            <div style="padding: 24px; background: #fff; border: 1px solid #e2e8f0; border-top: none; border-radius: 0 0 8px 8px;">
                <h2 style="margin: 0 0 16px; color: #1e293b;">Новый комментарий</h2>
                <p style="color: #475569; margin: 0 0 12px;"><strong>Заявка:</strong> {title}</p>
                <p style="color: #475569; margin: 0 0 12px;"><strong>Автор:</strong> {author_name}</p>
                <div style="background: #f8fafc; border-left: 3px solid #3b82f6; padding: 12px 16px; margin: 12px 0; border-radius: 0 4px 4px 0;">
                    <p style="color: #334155; margin: 0; white-space: pre-wrap;">{comment_text}</p>
                </div>
            </div>
        </div>
        """,
    )

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
    "on_hold": "Отложена",
    "engineer_visit": "Выезд инженера",
    "resolved": "Решён",
    "closed": "Закрыт",
}

PRIORITY_LABELS = {
    "critical": "Критический",
    "high": "Высокий",
    "normal": "Обычный",
    "low": "Низкий",
}


# Зарезервированные домены/TLD (RFC 2606, RFC 6761), на которые нельзя
# отправлять реальную почту — они специально не маршрутизируются.
# Использование: любые тест-фикстуры и демо-данные должны жить на этих
# доменах, а приложение молча не отправляет на них SMTP.
_RESERVED_EMAIL_DOMAINS: frozenset[str] = frozenset({
    "example.com",
    "example.net",
    "example.org",
})
_RESERVED_EMAIL_TLDS: tuple[str, ...] = (
    ".example",
    ".invalid",
    ".localhost",
    ".test",
)


def _is_reserved_address(addr: str) -> bool:
    """True, если email относится к зарезервированному (RFC 2606/6761) домену.

    Сравнение регистронезависимо и игнорирует пробелы по краям.
    """
    if not addr or "@" not in addr:
        return False
    domain = addr.rsplit("@", 1)[1].strip().lower().rstrip(".")
    if domain in _RESERVED_EMAIL_DOMAINS:
        return True
    return any(domain == t.lstrip(".") or domain.endswith(t) for t in _RESERVED_EMAIL_TLDS)


async def _send_email(
    to: str,
    subject: str,
    html_body: str,
    *,
    ticket_id: str | None = None,
) -> None:
    """Отправка email через SMTP. Ошибки логируются, но не прерывают работу.

    Если передан ticket_id — добавляет In-Reply-To/References заголовки
    для корректной группировки в email-клиентах.
    """
    if not settings.smtp_password:
        logger.warning("SMTP_PASSWORD не задан — email не отправлен: %s", subject)
        return

    # Guard: зарезервированные домены (RFC 2606/6761) — не шлём, чтобы
    # тест-фикстуры и демо-данные не уходили в реальный SMTP и не
    # возвращались bounce'ами на support@.
    if _is_reserved_address(to):
        logger.info(
            "Email пропущен (зарезервированный домен): %s -> %s",
            subject, to,
        )
        return

    msg = MIMEMultipart("alternative")
    msg["From"] = f"PASS24 Service Desk <{settings.smtp_from}>"
    msg["To"] = to
    msg["Subject"] = subject

    # Email threading headers
    if ticket_id:
        thread_id = f"<ticket-{ticket_id}@pass24servicedesk>"
        msg["Message-ID"] = thread_id
        msg["In-Reply-To"] = thread_id
        msg["References"] = thread_id

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


def _ticket_body_reference(ticket_id: str) -> str:
    """HTML-блок с идентификатором тикета в теле письма для надёжного threading."""
    tag = ticket_id[:8]
    return (
        '<div style="color:#999;font-size:11px;border-top:1px solid #eee;'
        'padding-top:8px;margin-top:20px;">'
        f'--- Не удаляйте эту строку: PASS24-{tag} ---'
        '</div>'
    )


PRODUCT_LABELS = {
    "pass24_online": "PASS24 (веб-портал)",
    "mobile_app": "Мобильное приложение PASS24",
    "pass24_key": "PASS24.Key (BLE-ключи)",
    "pass24_control": "PASS24.control (СКУД)",
    "pass24_auto": "PASS24.auto (распознавание номеров)",
    "equipment": "Оборудование",
    "integration": "Интеграция",
    "other": "Другое",
}

TYPE_LABELS = {
    "incident": "Инцидент (нарушение работы)",
    "problem": "Проблема",
    "service_request": "Стандартный запрос",
    "change_request": "Запрос на изменение",
    "question": "Вопрос / консультация",
    "feature_request": "Предложение",
}


async def notify_ticket_created(
    creator_email: str,
    ticket_id: str,
    title: str,
    priority: str,
    description: str = "",
    product: str = "",
    ticket_type: str = "",
    object_name: str = "",
    access_point: str = "",
    contact_phone: str = "",
    sla_response_hours: int = 4,
    sla_resolve_hours: int = 24,
) -> None:
    """Уведомление о создании тикета с полным контекстом."""
    priority_label = PRIORITY_LABELS.get(priority, priority)
    product_label = PRODUCT_LABELS.get(product, product) if product else ""
    type_label = TYPE_LABELS.get(ticket_type, ticket_type) if ticket_type else ""
    tag = ticket_subject_tag(ticket_id)
    portal_url = "https://support.pass24pro.ru"

    # Цвет приоритета
    priority_color = {
        "critical": "#dc2626",
        "high": "#ea580c",
        "normal": "#2563eb",
        "low": "#64748b",
    }.get(priority, "#2563eb")

    # Блок классификации
    classification_rows = []
    if product_label:
        classification_rows.append(f'<tr><td style="padding:4px 0;color:#64748b;width:40%;">Продукт</td><td style="padding:4px 0;color:#1e293b;font-weight:500;">{product_label}</td></tr>')
    if type_label:
        classification_rows.append(f'<tr><td style="padding:4px 0;color:#64748b;">Тип обращения</td><td style="padding:4px 0;color:#1e293b;font-weight:500;">{type_label}</td></tr>')
    classification_html = f'<table style="width:100%;font-size:14px;border-collapse:collapse;">{"".join(classification_rows)}</table>' if classification_rows else ""

    # Блок объекта
    object_block = ""
    if object_name or access_point:
        object_rows = []
        if object_name:
            object_rows.append(f'<tr><td style="padding:4px 0;color:#64748b;width:40%;">Объект</td><td style="padding:4px 0;color:#1e293b;font-weight:500;">{object_name}</td></tr>')
        if access_point:
            object_rows.append(f'<tr><td style="padding:4px 0;color:#64748b;">Точка доступа</td><td style="padding:4px 0;color:#1e293b;font-weight:500;">{access_point}</td></tr>')
        object_block = f"""
        <div style="margin-top:16px;">
            <div style="font-size:12px;font-weight:700;color:#64748b;text-transform:uppercase;letter-spacing:0.04em;margin-bottom:8px;">Где проблема</div>
            <table style="width:100%;font-size:14px;border-collapse:collapse;">{"".join(object_rows)}</table>
        </div>
        """

    # Блок контакта
    contact_block = ""
    if contact_phone:
        contact_block = f"""
        <div style="margin-top:16px;">
            <div style="font-size:12px;font-weight:700;color:#64748b;text-transform:uppercase;letter-spacing:0.04em;margin-bottom:8px;">Контакт для связи</div>
            <p style="color:#1e293b;font-weight:500;margin:0;font-size:14px;">📞 {contact_phone}</p>
        </div>
        """

    # Описание
    description_block = ""
    if description:
        # Ограничиваем 1000 символов чтобы письмо не было гигантским
        desc_trim = description[:1000] + ('…' if len(description) > 1000 else '')
        description_block = f"""
        <div style="margin-top:16px;">
            <div style="font-size:12px;font-weight:700;color:#64748b;text-transform:uppercase;letter-spacing:0.04em;margin-bottom:8px;">Описание проблемы</div>
            <div style="background:#f8fafc;border-left:3px solid #3b82f6;padding:12px 14px;border-radius:0 6px 6px 0;color:#334155;font-size:14px;line-height:1.6;white-space:pre-wrap;">{desc_trim}</div>
        </div>
        """

    await _send_email(
        to=creator_email,
        subject=f"{tag} Заявка принята: {title}",
        html_body=f"""
        <div style="font-family: -apple-system, BlinkMacSystemFont, Arial, sans-serif; max-width: 640px; margin: 0 auto; background: #f8fafc;">
            <div style="background: linear-gradient(135deg, #0f172a, #1e293b); color: #f8fafc; padding: 18px 24px; border-radius: 10px 10px 0 0;">
                <div style="display:flex;align-items:center;gap:10px;">
                    <div style="background: linear-gradient(135deg, #ef4444, #991b1b); padding: 4px 10px; border-radius: 6px; font-weight: 700; font-size: 12px;">PASS24</div>
                    <strong style="font-size:15px;">Service Desk</strong>
                </div>
            </div>

            <div style="padding: 24px; background: #fff; border: 1px solid #e2e8f0; border-top: none; border-radius: 0 0 10px 10px;">
                <!-- Статус принятия -->
                <div style="background:#ecfdf5;border:1px solid #a7f3d0;border-radius:8px;padding:14px 16px;margin-bottom:20px;display:flex;align-items:center;gap:10px;">
                    <div style="font-size:24px;">✓</div>
                    <div>
                        <div style="color:#065f46;font-weight:600;font-size:15px;">Заявка принята</div>
                        <div style="color:#047857;font-size:13px;">Мы начали работу над вашим обращением</div>
                    </div>
                </div>

                <!-- Тема и ID -->
                <h2 style="margin: 0 0 8px; color: #0f172a; font-size: 18px; line-height: 1.4;">{title}</h2>
                <p style="color:#94a3b8;font-size:13px;margin:0 0 20px;font-family:monospace;">#{ticket_id[:8].upper()}</p>

                <!-- Приоритет карточкой -->
                <div style="display:inline-block;background:{priority_color}15;border:1px solid {priority_color}40;color:{priority_color};padding:8px 14px;border-radius:8px;font-weight:600;font-size:13px;margin-bottom:16px;">
                    ● Приоритет: {priority_label}
                </div>

                {description_block}

                <div style="margin-top:16px;">
                    <div style="font-size:12px;font-weight:700;color:#64748b;text-transform:uppercase;letter-spacing:0.04em;margin-bottom:8px;">Классификация</div>
                    {classification_html}
                </div>

                {object_block}
                {contact_block}

                <!-- SLA -->
                <div style="background:#f8fafc;border-radius:8px;padding:14px 16px;margin-top:20px;">
                    <div style="font-size:12px;font-weight:700;color:#64748b;text-transform:uppercase;letter-spacing:0.04em;margin-bottom:10px;">⏱ Срок реагирования</div>
                    <div style="display:flex;gap:16px;font-size:13px;">
                        <div>
                            <div style="color:#94a3b8;font-size:11px;">Первый ответ</div>
                            <div style="color:#1e293b;font-weight:600;">в течение {sla_response_hours} ч</div>
                        </div>
                        <div>
                            <div style="color:#94a3b8;font-size:11px;">Решение</div>
                            <div style="color:#1e293b;font-weight:600;">в течение {sla_resolve_hours} ч</div>
                        </div>
                    </div>
                </div>

                <!-- Что дальше -->
                <div style="margin-top:20px;padding:14px 16px;background:#eff6ff;border:1px solid #bfdbfe;border-radius:8px;">
                    <div style="color:#1e40af;font-weight:600;font-size:14px;margin-bottom:6px;">Что дальше?</div>
                    <ul style="color:#1e40af;font-size:13px;line-height:1.6;margin:0;padding-left:20px;">
                        <li>Агент поддержки свяжется с вами в течение {sla_response_hours} часов</li>
                        <li>Все обновления будут приходить на этот email</li>
                        <li>Вы можете отвечать на письма — ваш ответ будет добавлен к заявке</li>
                    </ul>
                </div>

                <!-- CTA -->
                <div style="margin-top:20px;text-align:center;">
                    <a href="{portal_url}" style="display:inline-block;background:#0f172a;color:#ffffff;padding:10px 20px;border-radius:8px;text-decoration:none;font-weight:500;font-size:14px;">Открыть портал поддержки</a>
                </div>

                <p style="color: #94a3b8; font-size: 12px; margin: 24px 0 0; text-align:center;">
                    PASS24 Service Desk · support@pass24online.ru
                </p>
                {_ticket_body_reference(ticket_id)}
            </div>
        </div>
        """,
        ticket_id=ticket_id,
    )


async def notify_password_reset(email: str, reset_url: str) -> None:
    """Письмо со ссылкой для сброса пароля."""
    await _send_email(
        to=email,
        subject="Сброс пароля — PASS24 Service Desk",
        html_body=f"""
        <div style="font-family: -apple-system, BlinkMacSystemFont, Arial, sans-serif; max-width: 640px; margin: 0 auto; background: #f8fafc;">
            <div style="background: linear-gradient(135deg, #0f172a, #1e293b); color: #f8fafc; padding: 18px 24px; border-radius: 10px 10px 0 0;">
                <div style="display:flex;align-items:center;gap:10px;">
                    <div style="background: linear-gradient(135deg, #ef4444, #991b1b); padding: 4px 10px; border-radius: 6px; font-weight: 700; font-size: 12px;">PASS24</div>
                    <strong style="font-size:15px;">Service Desk</strong>
                </div>
            </div>

            <div style="padding: 24px; background: #fff; border: 1px solid #e2e8f0; border-top: none; border-radius: 0 0 10px 10px;">
                <h2 style="margin: 0 0 12px; color: #0f172a; font-size: 18px;">Сброс пароля</h2>
                <p style="color: #475569; font-size: 14px; line-height: 1.6; margin: 0 0 20px;">
                    Вы запросили сброс пароля для вашей учётной записи в PASS24 Service Desk.
                    Нажмите кнопку ниже, чтобы создать новый пароль:
                </p>

                <div style="text-align: center; margin: 24px 0;">
                    <a href="{reset_url}" style="display: inline-block; background: #0f172a; color: #ffffff; padding: 12px 32px; border-radius: 8px; text-decoration: none; font-weight: 600; font-size: 15px;">
                        Создать новый пароль
                    </a>
                </div>

                <div style="background: #fefce8; border: 1px solid #fde68a; border-radius: 8px; padding: 12px 16px; margin: 20px 0;">
                    <p style="color: #92400e; font-size: 13px; margin: 0; line-height: 1.5;">
                        Ссылка действительна <strong>1 час</strong>. Если вы не запрашивали сброс пароля, просто проигнорируйте это письмо.
                    </p>
                </div>

                <p style="color: #94a3b8; font-size: 12px; margin: 20px 0 0; line-height: 1.5;">
                    Если кнопка не работает, скопируйте и вставьте эту ссылку в браузер:<br>
                    <a href="{reset_url}" style="color: #3b82f6; word-break: break-all;">{reset_url}</a>
                </p>

                <p style="color: #94a3b8; font-size: 12px; margin: 24px 0 0; text-align: center;">
                    PASS24 Service Desk &middot; support@pass24online.ru
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
    """Уведомление о смене статуса + CSAT запрос при resolved."""
    old_label = STATUS_LABELS.get(old_status, old_status)
    new_label = STATUS_LABELS.get(new_status, new_status)
    tag = ticket_subject_tag(ticket_id)

    # CSAT block при переходе в resolved
    csat_block = ""
    if new_status == "resolved":
        csat_url = "https://support.pass24pro.ru"
        csat_block = f"""
                <div style="background: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 8px; padding: 16px; margin: 16px 0; text-align: center;">
                    <p style="color: #166534; font-weight: 600; margin: 0 0 12px;">Как прошло обслуживание?</p>
                    <p style="color: #166534; font-size: 14px; margin: 0 0 12px;">Оцените качество решения вашей заявки:</p>
                    <div style="font-size: 24px; margin: 8px 0;">
                        <a href="{csat_url}/tickets/{ticket_id}/rate?r=1" style="text-decoration: none; margin: 0 4px;">😞</a>
                        <a href="{csat_url}/tickets/{ticket_id}/rate?r=2" style="text-decoration: none; margin: 0 4px;">😐</a>
                        <a href="{csat_url}/tickets/{ticket_id}/rate?r=3" style="text-decoration: none; margin: 0 4px;">🙂</a>
                        <a href="{csat_url}/tickets/{ticket_id}/rate?r=4" style="text-decoration: none; margin: 0 4px;">😀</a>
                        <a href="{csat_url}/tickets/{ticket_id}/rate?r=5" style="text-decoration: none; margin: 0 4px;">🤩</a>
                    </div>
                    <p style="color: #64748b; font-size: 12px; margin: 8px 0 0;">Ваша оценка поможет нам стать лучше</p>
                </div>
        """

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
                {csat_block}
                <p style="color: #64748b; font-size: 14px; margin: 16px 0 0;">
                    Вы можете отслеживать статус заявки в личном кабинете Service Desk.
                </p>
                {_ticket_body_reference(ticket_id)}
            </div>
        </div>
        """,
        ticket_id=ticket_id,
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
                {_ticket_body_reference(ticket_id)}
            </div>
        </div>
        """,
        ticket_id=ticket_id,
    )

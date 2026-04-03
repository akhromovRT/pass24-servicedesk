"""
Приём входящих email и автоматическое создание тикетов.

Логика:
1. Подключается к IMAP, читает непрочитанные письма
2. Парсит тему и тело → определяет поля тикета
3. Если достаточно информации → создаёт тикет, отвечает подтверждением
4. Если недостаточно → отвечает с запросом уточнений
"""
from __future__ import annotations

import asyncio
import email
import imaplib
import logging
import re
from email.header import decode_header
from email.utils import parseaddr
from typing import Optional

from sqlmodel import select

from backend.config import settings

logger = logging.getLogger(__name__)

# Ключевые слова для определения категории
CATEGORY_KEYWORDS = {
    "access": ["доступ", "дверь", "домофон", "подъезд", "вход", "открыть", "не пускает", "не могу попасть"],
    "gate": ["шлагбаум", "ворота", "парковка", "въезд", "выезд", "барьер"],
    "pass": ["пропуск", "пропуска", "qr", "код", "карта", "ключ"],
    "notifications": ["уведомлен", "пуш", "push", "смс", "sms", "оповещен"],
    "app": ["приложен", "мобильн", "android", "ios", "обновлен", "установ"],
}


def _decode_mime_header(raw: str) -> str:
    """Декодирует MIME-заголовок (Subject, From и т.д.)."""
    parts = decode_header(raw)
    decoded = []
    for part, charset in parts:
        if isinstance(part, bytes):
            decoded.append(part.decode(charset or "utf-8", errors="replace"))
        else:
            decoded.append(part)
    return " ".join(decoded)


def _extract_text_body(msg: email.message.Message) -> str:
    """Извлекает текст из email (text/plain или text/html fallback)."""
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            if content_type == "text/plain":
                payload = part.get_payload(decode=True)
                charset = part.get_content_charset() or "utf-8"
                return payload.decode(charset, errors="replace") if payload else ""
        # Fallback на HTML
        for part in msg.walk():
            if part.get_content_type() == "text/html":
                payload = part.get_payload(decode=True)
                charset = part.get_content_charset() or "utf-8"
                html = payload.decode(charset, errors="replace") if payload else ""
                return re.sub(r"<[^>]+>", " ", html).strip()
    else:
        payload = msg.get_payload(decode=True)
        charset = msg.get_content_charset() or "utf-8"
        return payload.decode(charset, errors="replace") if payload else ""
    return ""


def _detect_category(text: str) -> str:
    """Определяет категорию тикета по ключевым словам."""
    lower = text.lower()
    for category, keywords in CATEGORY_KEYWORDS.items():
        if any(kw in lower for kw in keywords):
            return category
    return "general"


def _clean_body(body: str) -> str:
    """Очистка тела письма от подписей и цитирований."""
    lines = body.split("\n")
    cleaned = []
    for line in lines:
        # Остановиться на строках-разделителях подписей
        if line.strip().startswith("--") and len(line.strip()) <= 5:
            break
        if line.strip().startswith(">"):
            continue
        cleaned.append(line)
    result = "\n".join(cleaned).strip()
    # Ограничить длину
    return result[:4000] if result else ""


def _is_sufficient(subject: str, body: str) -> bool:
    """Проверяет достаточно ли информации для создания тикета."""
    # Нужна тема (или тело > 10 символов) и описание > 20 символов
    has_title = len(subject.strip()) >= 3
    has_description = len(body.strip()) >= 20
    return has_title and has_description


def _fetch_unseen_emails() -> list[dict]:
    """Подключается к IMAP и читает непрочитанные письма (sync)."""
    if not settings.smtp_password:
        return []

    results = []
    try:
        mail = imaplib.IMAP4_SSL(settings.imap_host, settings.imap_port)
        mail.login(settings.smtp_user, settings.smtp_password)
        mail.select("INBOX")

        _, message_nums = mail.search(None, "UNSEEN")
        if not message_nums[0]:
            mail.logout()
            return []

        for num in message_nums[0].split():
            _, msg_data = mail.fetch(num, "(RFC822)")
            if not msg_data or not msg_data[0]:
                continue

            raw_email = msg_data[0][1]
            msg = email.message_from_bytes(raw_email)

            subject = _decode_mime_header(msg.get("Subject", ""))
            from_header = msg.get("From", "")
            _, from_email = parseaddr(from_header)
            from_name = _decode_mime_header(from_header.split("<")[0].strip().strip('"'))
            body = _extract_text_body(msg)
            message_id = msg.get("Message-ID", "")

            # Пропускаем собственные письма (от support@)
            if from_email.lower() == settings.smtp_user.lower():
                continue

            # Пропускаем auto-reply и bounce
            if any(h in (msg.get("Auto-Submitted", "") or "").lower() for h in ["auto-replied", "auto-generated"]):
                continue

            results.append({
                "subject": subject,
                "from_email": from_email,
                "from_name": from_name or from_email.split("@")[0],
                "body": _clean_body(body),
                "message_id": message_id,
            })

        mail.logout()
    except Exception as exc:
        logger.error("Ошибка чтения IMAP: %s", exc)

    return results


async def process_incoming_emails() -> int:
    """
    Обрабатывает входящие email: создаёт тикеты или запрашивает уточнения.
    Возвращает количество обработанных писем.
    """
    from backend.notifications.email import _send_email

    # Читаем почту в отдельном потоке (imaplib — sync)
    emails = await asyncio.to_thread(_fetch_unseen_emails)
    if not emails:
        return 0

    # Lazy import чтобы избежать circular imports
    from backend.database import async_session_factory
    from backend.auth.models import User
    from backend.tickets.models import Ticket, TicketEvent

    processed = 0

    for mail_data in emails:
        from_email = mail_data["from_email"]
        subject = mail_data["subject"]
        body = mail_data["body"]
        from_name = mail_data["from_name"]

        if not _is_sufficient(subject, body):
            # Недостаточно информации → запросить уточнения
            await _send_email(
                to=from_email,
                subject=f"Re: {subject or 'Ваше обращение'} — нужна дополнительная информация",
                html_body=f"""
                <div style="font-family: -apple-system, Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                    <div style="background: #0f172a; color: #f8fafc; padding: 16px 24px; border-radius: 8px 8px 0 0;">
                        <strong>PASS24 Service Desk</strong>
                    </div>
                    <div style="padding: 24px; background: #fff; border: 1px solid #e2e8f0; border-top: none; border-radius: 0 0 8px 8px;">
                        <h2 style="margin: 0 0 16px; color: #1e293b;">Нужна дополнительная информация</h2>
                        <p style="color: #475569;">Здравствуйте, {from_name}!</p>
                        <p style="color: #475569;">Мы получили ваше обращение, но для создания заявки нам нужно больше деталей. Пожалуйста, ответьте на это письмо, указав:</p>
                        <ol style="color: #475569; line-height: 1.8;">
                            <li><strong>Тема обращения</strong> — кратко опишите проблему в теме письма</li>
                            <li><strong>Подробное описание</strong> — что произошло, когда, где</li>
                            <li><strong>Адрес объекта</strong> — ЖК или БЦ, подъезд, этаж</li>
                            <li><strong>Контактный телефон</strong> — для оперативной связи</li>
                        </ol>
                        <p style="color: #64748b; font-size: 14px; margin-top: 16px;">
                            После получения информации заявка будет создана автоматически.
                        </p>
                    </div>
                </div>
                """,
            )
            logger.info("Запрошены уточнения у %s по теме: %s", from_email, subject)
            processed += 1
            continue

        # Достаточно информации → создаём тикет
        category = _detect_category(f"{subject} {body}")
        title = subject.strip() if subject.strip() else body[:100].strip()

        async with async_session_factory() as session:
            # Ищем пользователя по email
            result = await session.execute(
                select(User).where(User.email == from_email)
            )
            user = result.scalar_one_or_none()

            # Если пользователя нет — создаём гостевого
            if not user:
                from backend.auth.utils import hash_password
                import uuid
                user = User(
                    email=from_email,
                    hashed_password=hash_password(uuid.uuid4().hex[:12]),
                    full_name=from_name,
                )
                session.add(user)
                await session.commit()
                await session.refresh(user)
                logger.info("Создан пользователь из email: %s", from_email)

            # Создаём тикет
            ticket = Ticket(
                creator_id=str(user.id),
                title=title[:200],
                description=body[:4000],
                category=category,
                contact=from_email,
            )
            ticket.assign_priority_based_on_context()

            event = TicketEvent(
                ticket_id=ticket.id,
                actor_id=str(user.id),
                description="Тикет создан из email",
            )

            session.add(ticket)
            session.add(event)
            await session.commit()
            await session.refresh(ticket)

            logger.info(
                "Тикет создан из email: %s -> %s (приоритет: %s, категория: %s)",
                from_email, ticket.id[:8], ticket.priority.value, ticket.category,
            )

        # Подтверждение создателю
        from backend.notifications.email import PRIORITY_LABELS
        priority_label = PRIORITY_LABELS.get(
            ticket.priority.value if hasattr(ticket.priority, 'value') else str(ticket.priority),
            "Обычный",
        )
        await _send_email(
            to=from_email,
            subject=f"Re: {title} — заявка создана",
            html_body=f"""
            <div style="font-family: -apple-system, Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                <div style="background: #0f172a; color: #f8fafc; padding: 16px 24px; border-radius: 8px 8px 0 0;">
                    <strong>PASS24 Service Desk</strong>
                </div>
                <div style="padding: 24px; background: #fff; border: 1px solid #e2e8f0; border-top: none; border-radius: 0 0 8px 8px;">
                    <h2 style="margin: 0 0 16px; color: #1e293b;">Заявка принята</h2>
                    <p style="color: #475569;">Здравствуйте, {from_name}!</p>
                    <p style="color: #475569; margin: 12px 0;"><strong>Тема:</strong> {title}</p>
                    <p style="color: #475569; margin: 12px 0;"><strong>Приоритет:</strong> {priority_label}</p>
                    <p style="color: #475569; margin: 12px 0;"><strong>Категория:</strong> {category}</p>
                    <p style="color: #475569; margin: 12px 0;"><strong>ID:</strong> {ticket.id[:8]}...</p>
                    <p style="color: #64748b; font-size: 14px; margin-top: 16px;">
                        Мы приступим к рассмотрению вашей заявки в ближайшее время.
                        Все обновления будут приходить на этот email.
                    </p>
                </div>
            </div>
            """,
        )
        processed += 1

    return processed


async def email_polling_loop() -> None:
    """Бесконечный цикл опроса IMAP для входящих писем."""
    if not settings.smtp_password:
        logger.warning("SMTP_PASSWORD не задан — приём email отключён")
        return

    logger.info(
        "Email polling запущен: %s, интервал %dс",
        settings.imap_host, settings.imap_poll_interval,
    )

    while True:
        try:
            count = await process_incoming_emails()
            if count > 0:
                logger.info("Обработано %d входящих писем", count)
        except Exception as exc:
            logger.error("Ошибка в email polling: %s", exc)

        await asyncio.sleep(settings.imap_poll_interval)

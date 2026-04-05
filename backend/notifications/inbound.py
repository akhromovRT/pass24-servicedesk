"""
Приём входящих email: создание тикетов, ответы → комментарии, вложения, авто-анализ.

Логика:
1. Подключается к IMAP, читает непрочитанные письма
2. Если тема содержит [PASS24-xxxxxxxx] → это ответ на тикет → добавить комментарий + вложения
3. Иначе → новый тикет:
   a. Парсит тему и тело → определяет категорию
   b. Ищет релевантные статьи в базе знаний (FTS)
   c. Если найдены → отправляет ссылки и спрашивает "помогло ли?"
   d. Если нет → создаёт тикет, отвечает подтверждением
"""
from __future__ import annotations

import asyncio
import email
import imaplib
import logging
import re
import uuid
from email.header import decode_header
from email.utils import parseaddr
from pathlib import Path
from typing import Optional

from sqlalchemy import text as sa_text
from sqlmodel import select

from backend.config import settings

logger = logging.getLogger(__name__)

UPLOAD_DIR = Path("/app/data/attachments")

# Ключевые слова для определения категории
CATEGORY_KEYWORDS = {
    "access": ["доступ", "дверь", "домофон", "подъезд", "вход", "открыть", "не пускает", "не могу попасть"],
    "gate": ["шлагбаум", "ворота", "парковка", "въезд", "выезд", "барьер"],
    "pass": ["пропуск", "пропуска", "qr", "код", "карта", "ключ"],
    "notifications": ["уведомлен", "пуш", "push", "смс", "sms", "оповещен"],
    "app": ["приложен", "мобильн", "android", "ios", "обновлен", "установ"],
}

# Паттерн тега тикета в теме: [PASS24-abc12345]
TICKET_TAG_RE = re.compile(r"\[PASS24-([a-f0-9]{8})\]", re.IGNORECASE)


def _decode_mime_header(raw: str) -> str:
    """Декодирует MIME-заголовок."""
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
            if part.get_content_type() == "text/plain":
                payload = part.get_payload(decode=True)
                charset = part.get_content_charset() or "utf-8"
                return payload.decode(charset, errors="replace") if payload else ""
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


def _extract_attachments(msg: email.message.Message) -> list[dict]:
    """Извлекает вложения из email (файлы, не inline-текст)."""
    attachments = []
    if not msg.is_multipart():
        return attachments

    for part in msg.walk():
        content_disposition = str(part.get("Content-Disposition", ""))
        content_type = part.get_content_type()

        # Пропускаем текстовые части
        if content_type in ("text/plain", "text/html") and "attachment" not in content_disposition:
            continue

        filename = part.get_filename()
        if filename:
            filename = _decode_mime_header(filename)
        elif "attachment" in content_disposition:
            ext = content_type.split("/")[-1] if "/" in content_type else "bin"
            filename = f"attachment.{ext}"
        else:
            continue

        payload = part.get_payload(decode=True)
        if not payload:
            continue

        attachments.append({
            "filename": filename,
            "content_type": content_type,
            "data": payload,
            "size": len(payload),
        })

    return attachments


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
        if line.strip().startswith("--") and len(line.strip()) <= 5:
            break
        if line.strip().startswith(">"):
            continue
        cleaned.append(line)
    result = "\n".join(cleaned).strip()
    return result[:4000] if result else ""


def _is_sufficient(subject: str, body: str) -> bool:
    """Проверяет достаточно ли информации для создания тикета."""
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
            attachments = _extract_attachments(msg)

            # Пропускаем собственные письма
            if from_email.lower() == settings.smtp_user.lower():
                continue

            # Пропускаем auto-reply и bounce
            if any(h in (msg.get("Auto-Submitted", "") or "").lower() for h in ["auto-replied", "auto-generated"]):
                continue
            if "mailer-daemon" in from_email.lower() or "postmaster" in from_email.lower():
                continue

            results.append({
                "subject": subject,
                "from_email": from_email,
                "from_name": from_name or from_email.split("@")[0],
                "body": _clean_body(body),
                "attachments": attachments,
            })

        mail.logout()
    except Exception as exc:
        logger.error("Ошибка чтения IMAP: %s", exc)

    return results


async def _save_attachment(ticket_id: str, uploader_id: str, att_data: dict, session) -> None:
    """Сохраняет вложение из email на диск и в БД."""
    from backend.tickets.models import Attachment

    file_id = str(uuid.uuid4())
    ext = Path(att_data["filename"]).suffix or ".bin"
    storage_path = f"{ticket_id}/{file_id}{ext}"
    full_path = UPLOAD_DIR / storage_path
    full_path.parent.mkdir(parents=True, exist_ok=True)
    full_path.write_bytes(att_data["data"])

    attachment = Attachment(
        ticket_id=ticket_id,
        uploader_id=uploader_id,
        filename=att_data["filename"],
        content_type=att_data["content_type"],
        size=att_data["size"],
        storage_path=storage_path,
    )
    session.add(attachment)


async def _search_knowledge_base(query: str, session) -> list[dict]:
    """Ищет релевантные статьи в базе знаний через FTS."""
    from backend.knowledge.models import Article

    fts_condition = sa_text(
        "to_tsvector('russian', coalesce(title, '') || ' ' || coalesce(content, '')) "
        "@@ plainto_tsquery('russian', :query)"
    ).bindparams(query=query)

    result = await session.execute(
        select(Article)
        .where(Article.is_published == True, fts_condition)  # noqa: E712
        .limit(3)
    )
    articles = result.scalars().all()

    if not articles:
        # Fallback ILIKE
        pattern = f"%{query[:50]}%"
        result = await session.execute(
            select(Article)
            .where(
                Article.is_published == True,  # noqa: E712
                Article.title.ilike(pattern) | Article.content.ilike(pattern),
            )
            .limit(3)
        )
        articles = result.scalars().all()

    return [{"title": a.title, "slug": a.slug, "category": a.category} for a in articles]


async def _handle_reply(mail_data: dict, ticket_id_prefix: str) -> bool:
    """Обрабатывает ответ на существующий тикет: комментарий + вложения."""
    from backend.database import async_session_factory
    from backend.auth.models import User
    from backend.tickets.models import Ticket, TicketComment

    async with async_session_factory() as session:
        # Найти тикет по начальным 8 символам id
        result = await session.execute(
            select(Ticket).where(Ticket.id.like(ticket_id_prefix + "%"))
        )
        ticket = result.scalar_one_or_none()
        if not ticket:
            logger.warning("Тикет %s... не найден для ответа от %s", ticket_id_prefix, mail_data["from_email"])
            return False

        # Найти пользователя
        user_result = await session.execute(
            select(User).where(User.email == mail_data["from_email"])
        )
        user = user_result.scalar_one_or_none()
        author_name = user.full_name if user else mail_data["from_name"]
        author_id = str(user.id) if user else "email"

        # Добавить комментарий
        body = mail_data["body"]
        if body.strip():
            comment = TicketComment(
                ticket_id=ticket.id,
                author_id=author_id,
                author_name=author_name,
                text=body,
            )
            session.add(comment)

        # Сохранить вложения
        for att in mail_data.get("attachments", []):
            await _save_attachment(ticket.id, author_id, att, session)

        await session.commit()

        att_count = len(mail_data.get("attachments", []))
        logger.info(
            "Email-ответ → комментарий к тикету %s от %s (%d вложений)",
            ticket.id[:8], mail_data["from_email"], att_count,
        )
        return True


async def _handle_reply_by_subject(mail_data: dict) -> bool:
    """Fallback: ищет тикет по заголовку из Re: темы."""
    from backend.database import async_session_factory
    from backend.auth.models import User
    from backend.tickets.models import Ticket, TicketComment

    subject = mail_data["subject"]
    # Убираем Re:/Fwd: и ищем оригинальный заголовок
    clean = re.sub(r"^(Re|Fwd|FW):\s*", "", subject, flags=re.IGNORECASE).strip()
    # Убираем известные префиксы из наших уведомлений
    for prefix in ["Заявка создана: ", "Новый комментарий: ", "Статус заявки изменён: ",
                    "Заявка принята: ", "Заявка принята — возможно, эти статьи помогут: "]:
        if clean.startswith(prefix):
            clean = clean[len(prefix):]
            break

    if len(clean) < 3:
        return False

    async with async_session_factory() as session:
        # Ищем тикет с таким заголовком от этого пользователя
        user_result = await session.execute(
            select(User).where(User.email == mail_data["from_email"])
        )
        user = user_result.scalar_one_or_none()
        if not user:
            return False

        result = await session.execute(
            select(Ticket)
            .where(Ticket.creator_id == str(user.id), Ticket.title == clean)
            .order_by(Ticket.created_at.desc())
            .limit(1)
        )
        ticket = result.scalar_one_or_none()
        if not ticket:
            return False

        author_name = user.full_name
        body = mail_data["body"]
        if body.strip():
            comment = TicketComment(
                ticket_id=ticket.id,
                author_id=str(user.id),
                author_name=author_name,
                text=body,
            )
            session.add(comment)

        for att in mail_data.get("attachments", []):
            await _save_attachment(ticket.id, str(user.id), att, session)

        await session.commit()

        att_count = len(mail_data.get("attachments", []))
        logger.info(
            "Email-ответ (по теме) → комментарий к тикету %s от %s (%d вложений)",
            ticket.id[:8], mail_data["from_email"], att_count,
        )
        return True


async def _handle_new_ticket(mail_data: dict) -> None:
    """Создаёт новый тикет из email с авто-анализом по базе знаний."""
    from backend.database import async_session_factory
    from backend.auth.models import User
    from backend.auth.utils import hash_password
    from backend.tickets.models import Ticket, TicketEvent
    from backend.notifications.email import _send_email, ticket_subject_tag, PRIORITY_LABELS

    from_email = mail_data["from_email"]
    subject = mail_data["subject"]
    body = mail_data["body"]
    from_name = mail_data["from_name"]

    if not _is_sufficient(subject, body):
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
                    <p style="color: #475569;">Для создания заявки, пожалуйста, ответьте на это письмо, указав:</p>
                    <ol style="color: #475569; line-height: 1.8;">
                        <li><strong>Тема</strong> — кратко опишите проблему</li>
                        <li><strong>Описание</strong> — что произошло, когда, где</li>
                        <li><strong>Адрес объекта</strong> — ЖК или БЦ</li>
                    </ol>
                </div>
            </div>
            """,
        )
        return

    category = _detect_category(f"{subject} {body}")
    title = subject.strip() if subject.strip() else body[:100].strip()

    async with async_session_factory() as session:
        # Пользователь
        result = await session.execute(select(User).where(User.email == from_email))
        user = result.scalar_one_or_none()
        if not user:
            user = User(
                email=from_email,
                hashed_password=hash_password(uuid.uuid4().hex[:12]),
                full_name=from_name,
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)

        # Создаём тикет
        ticket = Ticket(
            creator_id=str(user.id),
            title=title[:200],
            description=body[:4000],
            category=category,
            source="email",
            contact_name=from_name,
            contact_email=from_email,
        )
        ticket.auto_detect_category()
        ticket.assign_priority_based_on_context()
        ticket.auto_assign_group()

        event = TicketEvent(
            ticket_id=ticket.id,
            actor_id=str(user.id),
            description="Тикет создан из email",
        )
        session.add(ticket)
        session.add(event)

        # Сохранить вложения из письма
        for att in mail_data.get("attachments", []):
            await _save_attachment(ticket.id, str(user.id), att, session)

        await session.commit()
        await session.refresh(ticket)

        # Авто-анализ: поиск по базе знаний
        search_query = f"{title} {body[:200]}"
        articles = await _search_knowledge_base(search_query, session)

        tag = ticket_subject_tag(ticket.id)
        priority_label = PRIORITY_LABELS.get(
            ticket.priority.value if hasattr(ticket.priority, 'value') else str(ticket.priority),
            "Обычный",
        )
        att_count = len(mail_data.get("attachments", []))

        if articles:
            # Найдены статьи — отправляем ссылки
            articles_html = ""
            base_url = "https://support.pass24pro.ru"
            for art in articles:
                articles_html += f"""
                <li style="margin: 8px 0;">
                    <a href="{base_url}/knowledge/{art['slug']}" style="color: #2563eb; text-decoration: none; font-weight: 500;">{art['title']}</a>
                </li>
                """

            await _send_email(
                to=from_email,
                subject=f"{tag} Заявка принята — возможно, эти статьи помогут: {title}",
                html_body=f"""
                <div style="font-family: -apple-system, Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                    <div style="background: #0f172a; color: #f8fafc; padding: 16px 24px; border-radius: 8px 8px 0 0;">
                        <strong>PASS24 Service Desk</strong>
                    </div>
                    <div style="padding: 24px; background: #fff; border: 1px solid #e2e8f0; border-top: none; border-radius: 0 0 8px 8px;">
                        <h2 style="margin: 0 0 16px; color: #1e293b;">Заявка принята</h2>
                        <p style="color: #475569;">Здравствуйте, {from_name}!</p>
                        <p style="color: #475569;"><strong>Тема:</strong> {title}</p>
                        <p style="color: #475569;"><strong>Приоритет:</strong> {priority_label}</p>
                        {f'<p style="color: #475569;"><strong>Вложений:</strong> {att_count}</p>' if att_count else ''}

                        <div style="background: #f0f9ff; border: 1px solid #bae6fd; border-radius: 8px; padding: 16px; margin: 16px 0;">
                            <p style="color: #0369a1; font-weight: 600; margin: 0 0 8px;">
                                💡 Возможно, эти статьи помогут решить вашу проблему:
                            </p>
                            <ul style="color: #475569; padding-left: 20px; margin: 0;">{articles_html}</ul>
                        </div>

                        <p style="color: #475569;">
                            Если статьи не помогли — просто <strong>ответьте на это письмо</strong>,
                            подробнее описав проблему, и менеджер техподдержки подключится к вашей заявке.
                        </p>
                        <p style="color: #64748b; font-size: 14px; margin-top: 16px;">
                            ID заявки: {ticket.id[:8]}
                        </p>
                    </div>
                </div>
                """,
            )
        else:
            # Статьи не найдены — обычное подтверждение
            await _send_email(
                to=from_email,
                subject=f"{tag} Заявка принята: {title}",
                html_body=f"""
                <div style="font-family: -apple-system, Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                    <div style="background: #0f172a; color: #f8fafc; padding: 16px 24px; border-radius: 8px 8px 0 0;">
                        <strong>PASS24 Service Desk</strong>
                    </div>
                    <div style="padding: 24px; background: #fff; border: 1px solid #e2e8f0; border-top: none; border-radius: 0 0 8px 8px;">
                        <h2 style="margin: 0 0 16px; color: #1e293b;">Заявка принята</h2>
                        <p style="color: #475569;">Здравствуйте, {from_name}!</p>
                        <p style="color: #475569;"><strong>Тема:</strong> {title}</p>
                        <p style="color: #475569;"><strong>Приоритет:</strong> {priority_label}</p>
                        {f'<p style="color: #475569;"><strong>Вложений:</strong> {att_count}</p>' if att_count else ''}
                        <p style="color: #475569; margin-top: 16px;">
                            Менеджер техподдержки рассмотрит вашу заявку в ближайшее время.
                            Все обновления будут приходить на этот email.
                        </p>
                        <p style="color: #64748b; font-size: 14px; margin-top: 16px;">
                            ID заявки: {ticket.id[:8]}
                        </p>
                    </div>
                </div>
                """,
            )

    logger.info(
        "Тикет из email: %s → %s (приоритет: %s, категория: %s, вложений: %d, статей найдено: %d)",
        from_email, ticket.id[:8], ticket.priority.value, ticket.category,
        att_count, len(articles),
    )


async def process_incoming_emails() -> int:
    """
    Обрабатывает входящие email.
    - Ответы на тикеты → комментарии + вложения
    - Новые письма → тикеты + авто-анализ по базе знаний
    """
    emails = await asyncio.to_thread(_fetch_unseen_emails)
    if not emails:
        return 0

    processed = 0

    for mail_data in emails:
        subject = mail_data["subject"]

        # 1. Ответ с тегом [PASS24-xxxxxxxx]
        tag_match = TICKET_TAG_RE.search(subject)
        if tag_match:
            ticket_id_prefix = tag_match.group(1)
            handled = await _handle_reply(mail_data, ticket_id_prefix)
            if handled:
                processed += 1
                continue

        # 2. Ответ без тега (Re: ...) — поиск тикета по заголовку
        if subject.lower().startswith("re:"):
            handled = await _handle_reply_by_subject(mail_data)
            if handled:
                processed += 1
                continue

        # 3. Новый тикет
        await _handle_new_ticket(mail_data)
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

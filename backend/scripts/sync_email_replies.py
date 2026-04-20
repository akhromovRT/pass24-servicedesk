"""
Синхронизация пропущенных комментариев из email-ответов.

Сканирует INBOX за указанный период, находит ответы на тикеты
(по тегу [PASS24-xxxxxxxx] или по теме Re:...), создаёт
соответствующие комментарии и сохраняет вложения.

Запуск:
  docker exec site-pass24-servicedesk python -m backend.scripts.sync_email_replies --days 10
"""
from __future__ import annotations

import argparse
import asyncio
import email
import imaplib
import logging
import re
import sys
import uuid
from datetime import datetime, timedelta
from email.header import decode_header
from email.utils import parseaddr, parsedate_to_datetime
from pathlib import Path

from sqlmodel import select

from backend.config import settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
logger = logging.getLogger("sync_email")

UPLOAD_DIR = Path("/app/data/attachments")
TICKET_TAG_RE = re.compile(r"\[PASS24-([a-f0-9]{8})\]", re.IGNORECASE)
NOTIFICATION_PREFIXES = [
    "Заявка создана: ",
    "Новый комментарий: ",
    "Статус заявки изменён: ",
    "Заявка принята: ",
    "Заявка принята — возможно, эти статьи помогут: ",
]


def _decode_mime_header(raw: str) -> str:
    parts = decode_header(raw)
    decoded = []
    for part, charset in parts:
        if isinstance(part, bytes):
            decoded.append(part.decode(charset or "utf-8", errors="replace"))
        else:
            decoded.append(part)
    return " ".join(decoded)


def _extract_text_body(msg: email.message.Message) -> str:
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
    attachments = []
    if not msg.is_multipart():
        return attachments
    for part in msg.walk():
        cd = str(part.get("Content-Disposition", ""))
        ct = part.get_content_type()
        if ct in ("text/plain", "text/html") and "attachment" not in cd:
            continue
        filename = part.get_filename()
        if filename:
            filename = _decode_mime_header(filename)
        elif "attachment" in cd:
            ext = ct.split("/")[-1] if "/" in ct else "bin"
            filename = f"attachment.{ext}"
        else:
            continue
        payload = part.get_payload(decode=True)
        if not payload:
            continue
        attachments.append({
            "filename": filename,
            "content_type": ct,
            "data": payload,
            "size": len(payload),
        })
    return attachments


def _clean_body(body: str) -> str:
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


def _strip_subject(subject: str) -> str:
    """Убирает Re:/Fwd: и префиксы уведомлений из темы."""
    s = re.sub(r"^(Re|Fwd|FW):\s*", "", subject, flags=re.IGNORECASE).strip()
    # Убираем тег [PASS24-xxx] если есть
    s = TICKET_TAG_RE.sub("", s).strip()
    for prefix in NOTIFICATION_PREFIXES:
        if s.startswith(prefix):
            s = s[len(prefix):]
            break
    return s.strip()


def fetch_emails_since(days: int) -> list[dict]:
    """Читает все письма (включая SEEN) за N дней."""
    since_date = (datetime.now() - timedelta(days=days)).strftime("%d-%b-%Y")
    results = []
    m = imaplib.IMAP4_SSL(settings.imap_host, settings.imap_port)
    m.login(settings.smtp_user, settings.smtp_password)
    m.select("INBOX", readonly=True)

    _, nums = m.search(None, f'(SINCE "{since_date}")')
    if not nums[0]:
        m.logout()
        return []

    for num in nums[0].split():
        _, data = m.fetch(num, "(RFC822)")
        if not data or not data[0]:
            continue
        raw = data[0][1]
        msg = email.message_from_bytes(raw)

        subject = _decode_mime_header(msg.get("Subject", ""))
        from_hdr = msg.get("From", "")
        _, from_email = parseaddr(from_hdr)
        from_name = _decode_mime_header(from_hdr.split("<")[0].strip().strip('"'))

        # Пропускаем наши же письма и auto-replies
        if from_email.lower() == settings.smtp_user.lower():
            continue
        auto = (msg.get("Auto-Submitted", "") or "").lower()
        if "auto-replied" in auto or "auto-generated" in auto:
            continue
        if "mailer-daemon" in from_email.lower() or "postmaster" in from_email.lower():
            continue

        try:
            date_obj = parsedate_to_datetime(msg.get("Date", ""))
            date_iso = date_obj.replace(tzinfo=None).isoformat()
        except Exception:
            date_iso = ""

        results.append({
            "subject": subject,
            "from_email": from_email,
            "from_name": from_name or from_email.split("@")[0],
            "body": _clean_body(_extract_text_body(msg)),
            "attachments": _extract_attachments(msg),
            "date": date_iso,
            "message_id": msg.get("Message-ID", ""),
        })

    m.logout()
    return results


async def _find_ticket_by_tag(prefix: str):
    from backend.database import async_session_factory
    from backend.tickets.models import Ticket
    async with async_session_factory() as session:
        result = await session.execute(
            select(Ticket).where(Ticket.id.like(prefix + "%"))
        )
        return result.scalar_one_or_none()


async def _find_ticket_by_subject(clean_subject: str, from_email: str):
    from backend.database import async_session_factory
    from backend.auth.models import User
    from backend.tickets.models import Ticket
    async with async_session_factory() as session:
        u = await session.execute(select(User).where(User.email == from_email))
        user = u.scalar_one_or_none()
        if not user:
            return None
        r = await session.execute(
            select(Ticket)
            .where(Ticket.creator_id == str(user.id), Ticket.title == clean_subject)
            .order_by(Ticket.created_at.desc())
            .limit(1)
        )
        return r.scalar_one_or_none()


async def _comment_already_exists(ticket_id: str, body: str, from_email: str) -> bool:
    """Проверяет, не был ли этот комментарий уже добавлен (по тексту + email)."""
    from backend.database import async_session_factory
    from backend.tickets.models import TicketComment
    async with async_session_factory() as session:
        # Первые 100 символов тела как ключ
        key = body[:100].strip()
        if not key:
            return False
        r = await session.execute(
            select(TicketComment).where(TicketComment.ticket_id == ticket_id)
        )
        for c in r.scalars():
            if c.text[:100].strip() == key:
                return True
        return False


async def _save_attachment_for_ticket(ticket_id: str, uploader_id: str, att: dict):
    from backend.database import async_session_factory
    from backend.tickets.models import Attachment
    file_id = str(uuid.uuid4())
    ext = Path(att["filename"]).suffix or ".bin"
    storage_path = f"{ticket_id}/{file_id}{ext}"
    full = UPLOAD_DIR / storage_path
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_bytes(att["data"])

    async with async_session_factory() as session:
        attachment = Attachment(
            ticket_id=ticket_id,
            uploader_id=uploader_id,
            filename=att["filename"],
            content_type=att["content_type"],
            size=att["size"],
            storage_path=storage_path,
        )
        session.add(attachment)
        await session.commit()


async def _add_comment(ticket_id: str, author_id: str, author_name: str, text: str):
    from backend.database import async_session_factory
    from backend.tickets.models import TicketComment
    async with async_session_factory() as session:
        comment = TicketComment(
            ticket_id=ticket_id,
            author_id=author_id,
            author_name=author_name,
            text=text,
            # Backfill-скрипт синхронизирует исторические клиентские ответы из email.
            author_is_staff=False,
        )
        session.add(comment)
        await session.commit()


async def _get_user_info(email_addr: str) -> tuple[str, str]:
    from backend.database import async_session_factory
    from backend.auth.models import User
    async with async_session_factory() as session:
        r = await session.execute(select(User).where(User.email == email_addr))
        user = r.scalar_one_or_none()
        if user:
            return str(user.id), user.full_name
        return "email", email_addr


async def process_emails(emails: list[dict]) -> dict:
    stats = {
        "total": len(emails),
        "replies_by_tag": 0,
        "replies_by_subject": 0,
        "skipped_no_match": 0,
        "skipped_duplicate": 0,
        "added_comments": 0,
        "added_attachments": 0,
    }

    for mail in emails:
        subject = mail["subject"]
        from_email = mail["from_email"]
        body = mail["body"]

        ticket = None
        match_type = None

        # 1. По тегу
        tag = TICKET_TAG_RE.search(subject)
        if tag:
            ticket = await _find_ticket_by_tag(tag.group(1))
            if ticket:
                match_type = "tag"
                stats["replies_by_tag"] += 1

        # 2. По теме (если тега нет или тикет не найден)
        if not ticket and subject.lower().startswith("re:"):
            clean = _strip_subject(subject)
            if clean:
                ticket = await _find_ticket_by_subject(clean, from_email)
                if ticket:
                    match_type = "subject"
                    stats["replies_by_subject"] += 1

        if not ticket:
            stats["skipped_no_match"] += 1
            continue

        # Проверка дубликата
        if body.strip() and await _comment_already_exists(ticket.id, body, from_email):
            stats["skipped_duplicate"] += 1
            logger.info(
                "DUPLICATE: %s (%s) → ticket %s",
                subject[:60], from_email, ticket.id[:8]
            )
            continue

        # Получаем author info
        author_id, author_name = await _get_user_info(from_email)

        # Добавляем комментарий
        if body.strip():
            await _add_comment(ticket.id, author_id, author_name, body)
            stats["added_comments"] += 1

        # Сохраняем вложения
        for att in mail.get("attachments", []):
            await _save_attachment_for_ticket(ticket.id, author_id, att)
            stats["added_attachments"] += 1

        logger.info(
            "ADDED (%s): %s → ticket %s (%d attachments)",
            match_type, from_email, ticket.id[:8], len(mail.get("attachments", []))
        )

    return stats


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=10)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    logger.info("Fetching emails for last %d days...", args.days)
    emails = await asyncio.to_thread(fetch_emails_since, args.days)
    logger.info("Found %d candidate emails (excluding own & auto-replies)", len(emails))

    if args.dry_run:
        for m in emails:
            subj = m["subject"][:80]
            print(f"  {m['date'][:16]} | {m['from_email']:40} | {subj}")
        print(f"\nTotal: {len(emails)}")
        return

    stats = await process_emails(emails)

    print("\n=== Sync Summary ===")
    for k, v in stats.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    asyncio.run(main())

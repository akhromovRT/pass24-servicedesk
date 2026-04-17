"""Telegram-бот для двусторонней переписки по тикетам.

Логика:
  - Первое сообщение → создаётся тикет
  - Последующие сообщения, пока тикет открыт (status != closed) → комментарии
  - Новое сообщение после CLOSED → новый тикет
  - Фото/документы → сохраняются как вложения
  - Комментарии агента → пересылаются в Telegram-чат клиента

Команды:
  /start — приветствие
  /help — инструкция
  /new — принудительно создать новый тикет
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

import httpx
from fastapi import APIRouter, HTTPException, Request
from sqlmodel import select

from backend.config import settings
from backend.database import async_session_factory

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/telegram", tags=["telegram"])

UPLOAD_DIR = Path("/app/data/attachments")
MAX_TG_FILE_SIZE = 20 * 1024 * 1024  # 20 MB (Telegram bot API limit)


# ---------- Telegram API helpers ----------

def _bot_token() -> str:
    return getattr(settings, "telegram_bot_token", None) or ""


async def _tg_send_message(chat_id: int, text: str, parse_mode: str = "HTML") -> None:
    token = _bot_token()
    if not token:
        return
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={"chat_id": chat_id, "text": text, "parse_mode": parse_mode},
            )
            if r.status_code != 200:
                logger.warning("Telegram sendMessage %s: %s", r.status_code, r.text[:200])
    except Exception as exc:
        logger.warning("Telegram send failed: %s", exc)


async def _tg_send_document(chat_id: int, file_path: Path, caption: str = "") -> None:
    """Отправка файла из локальной системы в Telegram."""
    token = _bot_token()
    if not token or not file_path.exists():
        return
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            with open(file_path, "rb") as f:
                r = await client.post(
                    f"https://api.telegram.org/bot{token}/sendDocument",
                    data={"chat_id": chat_id, "caption": caption},
                    files={"document": (file_path.name, f)},
                )
                if r.status_code != 200:
                    logger.warning("Telegram sendDocument %s: %s", r.status_code, r.text[:200])
    except Exception as exc:
        logger.warning("Telegram sendDocument failed: %s", exc)


async def _tg_download_file(file_id: str) -> Optional[tuple[bytes, str]]:
    """Скачивает файл из Telegram. Возвращает (data, filename)."""
    token = _bot_token()
    if not token:
        return None
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            # Получаем file_path
            r = await client.get(f"https://api.telegram.org/bot{token}/getFile", params={"file_id": file_id})
            if r.status_code != 200:
                return None
            data = r.json()
            if not data.get("ok"):
                return None
            file_path = data["result"]["file_path"]
            filename = Path(file_path).name

            # Скачиваем
            file_url = f"https://api.telegram.org/file/bot{token}/{file_path}"
            fr = await client.get(file_url)
            if fr.status_code != 200:
                return None
            return fr.content, filename
    except Exception as exc:
        logger.warning("Telegram download failed: %s", exc)
        return None


# ---------- Attachment saving ----------

async def _save_tg_attachment(
    ticket_id: str, uploader_id: str, file_id: str,
    filename_hint: str, content_type: str, session,
) -> Optional[str]:
    """Скачивает вложение из Telegram, сохраняет в БД + на диск."""
    from backend.tickets.models import Attachment

    downloaded = await _tg_download_file(file_id)
    if not downloaded:
        return None
    data, tg_filename = downloaded
    if len(data) > MAX_TG_FILE_SIZE:
        return None

    filename = filename_hint or tg_filename
    file_id_uuid = str(uuid.uuid4())
    ext = Path(filename).suffix or ".bin"
    storage_path = f"{ticket_id}/{file_id_uuid}{ext}"
    full_path = UPLOAD_DIR / storage_path
    full_path.parent.mkdir(parents=True, exist_ok=True)
    full_path.write_bytes(data)

    attachment = Attachment(
        ticket_id=ticket_id,
        uploader_id=uploader_id,
        filename=filename,
        content_type=content_type,
        size=len(data),
        storage_path=storage_path,
    )
    session.add(attachment)
    return filename


def _extract_media(message: dict) -> Optional[tuple[str, str, str]]:
    """Возвращает (file_id, filename, content_type) для вложения или None."""
    # Photo (массив, берём наибольшее разрешение)
    if photos := message.get("photo"):
        largest = max(photos, key=lambda p: p.get("file_size", 0))
        return (largest["file_id"], f"photo-{largest['file_id'][:8]}.jpg", "image/jpeg")

    # Document
    if doc := message.get("document"):
        return (
            doc["file_id"],
            doc.get("file_name") or f"document-{doc['file_id'][:8]}",
            doc.get("mime_type") or "application/octet-stream",
        )

    # Voice
    if voice := message.get("voice"):
        return (voice["file_id"], f"voice-{voice['file_id'][:8]}.ogg", "audio/ogg")

    # Video
    if video := message.get("video"):
        return (video["file_id"], f"video-{video['file_id'][:8]}.mp4", "video/mp4")

    return None


# ---------- Webhook ----------

@router.post("/webhook/{secret}")
async def telegram_webhook(secret: str, request: Request):
    """Webhook от Telegram: обрабатывает сообщения → тикеты/комментарии."""
    from backend.auth.models import User
    from backend.auth.utils import hash_password
    from backend.tickets.models import Ticket, TicketEvent, TicketComment, TicketSource, TicketStatus

    expected_secret = getattr(settings, "telegram_webhook_secret", "") or ""
    if not expected_secret or secret != expected_secret:
        raise HTTPException(status_code=403, detail="Forbidden")

    data = await request.json()
    message = data.get("message") or data.get("edited_message")
    if not message:
        return {"ok": True}

    chat_id = message.get("chat", {}).get("id")
    from_user = message.get("from", {})
    text = (message.get("text") or message.get("caption") or "").strip()
    media = _extract_media(message)

    if not chat_id:
        return {"ok": True}

    # Команды
    if text == "/start":
        await _tg_send_message(
            chat_id,
            "👋 <b>Привет!</b> Это бот PASS24 Service Desk.\n\n"
            "Напишите сюда суть проблемы — я создам заявку и менеджер свяжется с вами.\n"
            "Можно присылать фото, документы — они тоже будут приложены к заявке.\n\n"
            "<b>Команды:</b>\n"
            "/new — создать новую заявку\n"
            "/help — помощь",
        )
        return {"ok": True}

    if text == "/help":
        await _tg_send_message(
            chat_id,
            "💡 <b>Как это работает:</b>\n\n"
            "• Первое сообщение создаёт заявку\n"
            "• Пока заявка открыта — все сообщения добавляются как комментарии\n"
            "• Ответы менеджера придут сюда же, в этот чат\n"
            "• Фото/файлы сохраняются в заявке\n\n"
            "Используйте /new чтобы начать новую заявку.",
        )
        return {"ok": True}

    force_new = text == "/new"
    if force_new:
        text = ""  # сбрасываем, жду следующее сообщение

    # Без текста и медиа — ничего не делаем
    if not text and not media:
        if force_new:
            await _tg_send_message(chat_id, "✍️ Опишите суть проблемы, я создам новую заявку.")
        return {"ok": True}

    tg_username = from_user.get("username") or f"tg_{chat_id}"
    tg_name = f"{from_user.get('first_name', '')} {from_user.get('last_name', '')}".strip() or tg_username
    email = f"{tg_username}@telegram.pass24.local"

    async with async_session_factory() as session:
        # Находим/создаём пользователя (и сохраняем chat_id)
        r = await session.execute(select(User).where(User.email == email))
        user = r.scalar_one_or_none()
        if not user:
            user = User(
                email=email,
                hashed_password=hash_password(uuid.uuid4().hex[:16]),
                full_name=tg_name,
                telegram_chat_id=chat_id,
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)
        elif user.telegram_chat_id != chat_id:
            user.telegram_chat_id = chat_id
            session.add(user)
            await session.commit()

        # Ищем открытый тикет от этого пользователя
        active_ticket = None
        if not force_new:
            tr = await session.execute(
                select(Ticket)
                .where(
                    Ticket.creator_id == str(user.id),
                    Ticket.source == TicketSource.TELEGRAM,
                    Ticket.status != TicketStatus.CLOSED,
                )
                .order_by(Ticket.created_at.desc())
                .limit(1)
            )
            active_ticket = tr.scalar_one_or_none()

        if active_ticket:
            # Добавляем как комментарий
            if text:
                comment = TicketComment(
                    ticket_id=active_ticket.id,
                    author_id=str(user.id),
                    author_name=tg_name,
                    text=text,
                )
                session.add(comment)
                # Message-driven SLA pause: клиент ответил → reply-флаг снимается.
                active_ticket.on_public_comment_added(is_staff=False, now=datetime.utcnow())

            # Сохраняем вложение
            saved_filename = None
            if media:
                file_id, fname, ctype = media
                saved_filename = await _save_tg_attachment(
                    active_ticket.id, str(user.id), file_id, fname, ctype, session,
                )

            # Клиент ответил → флаг unread + IN_PROGRESS если было WAITING
            active_ticket.has_unread_reply = True
            if active_ticket.status == TicketStatus.WAITING_FOR_USER:
                try:
                    event = active_ticket.transition(
                        actor_id=str(user.id),
                        new_status=TicketStatus.IN_PROGRESS,
                    )
                    session.add(event)
                except (ValueError, Exception):
                    pass
            session.add(active_ticket)
            await session.commit()

            # Подтверждение в чат (тихое)
            if saved_filename:
                await _tg_send_message(
                    chat_id,
                    f"📎 Принято в заявку <b>#{active_ticket.id[:8]}</b>",
                )
            logger.info("Telegram → comment to ticket %s", active_ticket.id[:8])
            return {"ok": True}

        # Создаём новый тикет
        if len(text) < 10 and not media:
            await _tg_send_message(chat_id, "Опишите проблему подробнее (хотя бы несколько предложений).")
            return {"ok": True}

        title = (text[:100] if len(text) > 100 else text) or f"Обращение из Telegram от @{tg_username}"
        desc = text[:4000] if text else "Вложение из Telegram"
        ticket = Ticket(
            creator_id=str(user.id),
            title=title,
            description=desc,
            source=TicketSource.TELEGRAM,
            contact_name=tg_name,
            contact_email=email,
        )
        try:
            ticket.auto_detect_category()
            ticket.assign_priority_based_on_context()
        except Exception:
            pass

        event = TicketEvent(
            ticket_id=ticket.id,
            actor_id=str(user.id),
            description=f"Тикет создан из Telegram (@{tg_username})",
        )
        session.add(ticket)
        session.add(event)
        await session.commit()
        await session.refresh(ticket)

        # Сохраняем вложение
        if media:
            file_id, fname, ctype = media
            await _save_tg_attachment(ticket.id, str(user.id), file_id, fname, ctype, session)
            await session.commit()

    await _tg_send_message(
        chat_id,
        f"✅ <b>Заявка #{ticket.id[:8]} создана!</b>\n\n"
        f"<b>Тема:</b> {title}\n\n"
        f"Менеджер рассмотрит её в ближайшее время.\n"
        f"Продолжайте писать сюда — всё пойдёт в заявку.",
    )
    logger.info("Telegram ticket %s created from @%s", ticket.id[:8], tg_username)
    return {"ok": True}


# ---------- Функция для пересылки комментариев агента в Telegram ----------

async def notify_telegram_comment(
    chat_id: int, ticket_id: str, ticket_title: str,
    comment_text: str, author_name: str,
    attachment_paths: Optional[list[Path]] = None,
) -> None:
    """Отправка комментария агента в Telegram-чат клиента."""
    text = (
        f"💬 <b>Ответ по заявке #{ticket_id[:8]}</b>\n"
        f"<i>{ticket_title}</i>\n\n"
        f"<b>{author_name}:</b>\n{comment_text}"
    )
    await _tg_send_message(chat_id, text)

    if attachment_paths:
        for p in attachment_paths:
            await _tg_send_document(chat_id, p)


async def notify_telegram_status(
    chat_id: int, ticket_id: str, ticket_title: str,
    old_status: str, new_status: str,
) -> None:
    """Уведомление о смене статуса в Telegram."""
    from backend.notifications.email import STATUS_LABELS
    old_label = STATUS_LABELS.get(old_status, old_status)
    new_label = STATUS_LABELS.get(new_status, new_status)
    await _tg_send_message(
        chat_id,
        f"🔄 <b>Заявка #{ticket_id[:8]}</b>\n"
        f"<i>{ticket_title}</i>\n\n"
        f"Статус: {old_label} → <b>{new_label}</b>",
    )

"""Telegram-бот для приёма тикетов через webhook.

Настройка:
  1. Создать бота через @BotFather → получить token
  2. В env: TELEGRAM_BOT_TOKEN, TELEGRAM_WEBHOOK_SECRET (любая строка)
  3. Установить webhook:
     curl -F "url=https://support.pass24pro.ru/telegram/webhook/<secret>" \
          https://api.telegram.org/bot<token>/setWebhook
  4. В чате с ботом отправить сообщение — будет создан тикет
"""
from __future__ import annotations

import logging
import uuid
from typing import Optional

import httpx
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from sqlmodel import select

from backend.config import settings
from backend.database import async_session_factory

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/telegram", tags=["telegram"])


async def _send_telegram_message(chat_id: int, text: str) -> None:
    """Отправка сообщения в Telegram-чат."""
    token = getattr(settings, "telegram_bot_token", None) or ""
    if not token:
        return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(url, json={
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "HTML",
            })
    except Exception as exc:
        logger.warning("Telegram send failed: %s", exc)


@router.post("/webhook/{secret}")
async def telegram_webhook(secret: str, request: Request):
    """Webhook от Telegram. Принимает сообщение → создаёт тикет."""
    from backend.auth.models import User
    from backend.auth.utils import hash_password
    from backend.tickets.models import Ticket, TicketEvent, TicketSource

    expected_secret = getattr(settings, "telegram_webhook_secret", "") or ""
    if not expected_secret or secret != expected_secret:
        raise HTTPException(status_code=403, detail="Forbidden")

    data = await request.json()
    message = data.get("message") or data.get("edited_message")
    if not message:
        return {"ok": True}

    chat = message.get("chat", {})
    chat_id = chat.get("id")
    from_user = message.get("from", {})
    text = (message.get("text") or message.get("caption") or "").strip()

    if not text or not chat_id:
        return {"ok": True}

    # Команда /start
    if text.startswith("/start"):
        await _send_telegram_message(
            chat_id,
            "👋 Привет! Это бот PASS24 Service Desk.\n\n"
            "Напишите сюда суть проблемы — я создам заявку, и менеджер свяжется с вами.\n\n"
            "Все обновления буду присылать в этот чат.",
        )
        return {"ok": True}

    if len(text) < 10:
        await _send_telegram_message(
            chat_id,
            "Пожалуйста, опишите проблему подробнее (хотя бы несколько предложений).",
        )
        return {"ok": True}

    # Создаём пользователя и тикет
    tg_username = from_user.get("username") or f"tg_{chat_id}"
    tg_name = f"{from_user.get('first_name', '')} {from_user.get('last_name', '')}".strip() or tg_username
    email = f"{tg_username}@telegram.pass24.local"

    async with async_session_factory() as session:
        r = await session.execute(select(User).where(User.email == email))
        user = r.scalar_one_or_none()
        if not user:
            user = User(
                email=email,
                hashed_password=hash_password(uuid.uuid4().hex[:16]),
                full_name=tg_name,
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)

        title = text[:100] if len(text) > 100 else text
        ticket = Ticket(
            creator_id=str(user.id),
            title=title,
            description=text[:4000],
            source=TicketSource.TELEGRAM,
            contact_name=tg_name,
            contact_email=email,
        )
        # Авто-классификация
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

    await _send_telegram_message(
        chat_id,
        f"✅ Заявка <b>#{ticket.id[:8]}</b> создана!\n\n"
        f"<b>Тема:</b> {title}\n"
        f"Менеджер рассмотрит её в ближайшее время.\n\n"
        f"Можете продолжать писать сюда — все сообщения будут добавлены к заявке.",
    )
    logger.info("Telegram ticket created: %s from @%s", ticket.id[:8], tg_username)
    return {"ok": True}

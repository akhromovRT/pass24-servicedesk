"""Compat handler for UNLINKED users during the v2 rollout window.

Ports the legacy ghost-user flow from `backend/notifications/telegram.py`
(deleted in Task 14) into the aiogram 3 dispatcher so pre-v2 conversations
keep working. Flow:

  1. Unlinked user sends text or media.
  2. We look up / create a ghost user:
     ``email = f"{tg_username}@telegram.pass24.local"``,
     ``telegram_chat_id = chat_id``, random hashed password.
  3. If the ghost has an active (non-CLOSED) TELEGRAM ticket → add comment +
     attachment + mark ``has_unread_reply`` + transition WAITING→IN_PROGRESS.
     Else create a new ticket via ``ticket_service.create_ticket``.
  4. Reply with a short confirmation that nudges them to link their account.

The module registers a router that runs AFTER the stateful routers and BEFORE
``menu_router`` — but each handler guards with ``if is_linked or not
compat_mode: return`` so real users never have text stolen from them.

The global switch is ``TELEGRAM_COMPAT_MODE`` in ``backend/telegram/config.py``
— flip to False after the 2-week rollout.
"""
from __future__ import annotations

import logging
import uuid as uuid_mod
from datetime import datetime

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.types import Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlmodel import select

from backend.auth.models import User
from backend.auth.utils import hash_password
from backend.database import async_session_factory
from backend.telegram.config import APP_BASE_URL
from backend.telegram.services.ticket_service import (
    add_comment,
    create_ticket,
    extract_tg_attachment_meta,
)
from backend.tickets.models import Ticket, TicketSource, TicketStatus

logger = logging.getLogger(__name__)

router = Router(name="compat")


# --- Ghost user helpers -------------------------------------------------


async def _get_or_create_ghost_user(message: Message) -> User:
    """Look up or create a ghost user for an unlinked Telegram chat.

    Pattern matches the legacy notifier so existing ghost rows stay the same:
    ``email = f"{tg_username}@telegram.pass24.local"``, random hashed password,
    ``telegram_chat_id`` kept in sync with the actual chat id.
    """
    chat_id = message.chat.id
    from_user = message.from_user
    tg_username = (from_user.username if from_user else None) or f"tg_{chat_id}"
    first = (from_user.first_name if from_user else None) or ""
    last = (from_user.last_name if from_user else None) or ""
    tg_name = (f"{first} {last}".strip()) or tg_username
    email = f"{tg_username}@telegram.pass24.local"

    async with async_session_factory() as session:
        result = await session.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
        if user is None:
            user = User(
                email=email,
                hashed_password=hash_password(uuid_mod.uuid4().hex[:16]),
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
            await session.refresh(user)
    return user


async def _find_active_ghost_ticket(user: User) -> Ticket | None:
    """Return the newest non-CLOSED TELEGRAM ticket for the given ghost user, or None."""
    async with async_session_factory() as session:
        result = await session.execute(
            select(Ticket)
            .where(
                Ticket.creator_id == str(user.id),
                Ticket.source == TicketSource.TELEGRAM,
                Ticket.status != TicketStatus.CLOSED.value,
            )
            .order_by(Ticket.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()


def _link_prompt_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="🔗 Привязать аккаунт", url=f"{APP_BASE_URL}/settings#telegram")
    kb.adjust(1)
    return kb.as_markup()


# --- Core compat flow ---------------------------------------------------


async def handle_unlinked_text(message: Message, **data) -> None:
    """Legacy ghost flow entry point for plain text.

    Called from two places:
    - ``menu.py::free_text_fallback`` (text arrives when no FSM state is set)
    - directly by the compat router below when an unlinked user sends media
      with or without caption.

    Guard: caller must have already verified ``compat_mode and not is_linked``.
    """
    text = (message.text or message.caption or "").strip()
    media = extract_tg_attachment_meta(message)
    if not text and not media:
        return

    user = await _get_or_create_ghost_user(message)
    active = await _find_active_ghost_ticket(user)

    try:
        if active is not None:
            # Append as a comment + optional attachment. add_comment handles
            # has_unread_reply, WAITING→IN_PROGRESS, and SLA unpause.
            attachments = [media] if media else []
            comment_text = text or "📎 Вложение из Telegram"
            await add_comment(
                ticket_id=active.id,
                user=user,
                text=comment_text,
                attachments=attachments,
            )
            await message.answer(
                f"📎 Принято в заявку <b>#{active.id[:8]}</b>.\n\n"
                f"💡 Привяжите аккаунт — и получите полноценное меню с историей заявок.",
                parse_mode="HTML",
                reply_markup=_link_prompt_kb(),
            )
            logger.info("compat: comment added to ghost ticket %s", active.id[:8])
            return

        # No active ticket → create a new one. Require at least short text or
        # media; otherwise nudge for more detail (legacy behaviour).
        if not media and len(text) < 10:
            await message.answer(
                "Опишите проблему подробнее (хотя бы несколько предложений) — "
                "и я создам заявку.",
            )
            return

        attachments = [media] if media else []
        ticket = await create_ticket(
            data={
                "description": text or "Вложение из Telegram",
                "product": "other",
                "category": "other",
                "attachments": attachments,
            },
            user=user,
        )
        await message.answer(
            f"✅ <b>Заявка #{ticket.id[:8]} создана!</b>\n\n"
            f"Менеджер рассмотрит её в ближайшее время. Продолжайте писать сюда — "
            f"следующие сообщения попадут в эту же заявку.\n\n"
            f"💡 Привяжите аккаунт, чтобы получить меню с историей заявок, "
            f"поиском по базе знаний и уведомлениями.",
            parse_mode="HTML",
            reply_markup=_link_prompt_kb(),
        )
        logger.info("compat: ghost ticket %s created from chat %s", ticket.id[:8], message.chat.id)
    except Exception as exc:
        logger.exception("compat flow failed: %s", exc)
        # Don't leak internals; give the user a soft fallback.
        await message.answer(
            "⚠ Не удалось обработать сообщение. Попробуйте ещё раз или обратитесь в поддержку.",
        )


# --- Router-level catch for media (router registered before menu_router) -----


@router.message(
    StateFilter(None),
    F.photo | F.document | F.video | F.voice,
)
async def compat_attachment(message: Message, **data) -> None:
    """Catch media from unlinked users when no FSM state is active.

    Linked users should never hit this — if they send media outside a wizard,
    aiogram's routing order means their own routers (e.g. the reply flow) handle
    it first when in an FSM state, and here we explicitly no-op for them so we
    don't interfere with future handlers (menu's F.text catch-all doesn't cover
    media, so this is a safe fallback for unlinked users only).
    """
    if data.get("is_linked") or not data.get("compat_mode"):
        return
    await handle_unlinked_text(message, **data)

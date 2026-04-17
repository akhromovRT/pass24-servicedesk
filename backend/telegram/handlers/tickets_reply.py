from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from backend.telegram.services.ticket_service import (
    add_comment,
    close_ticket,
    extract_tg_attachment_meta,
    resolve_ticket_by_short_id,
)

logger = logging.getLogger(__name__)

router = Router(name="tickets_reply")


class ReplyStates(StatesGroup):
    """Shared state for both the reply (tl:reply) and attachment-only (tl:attach)
    entry points — the prompt copy differs but the state machine is identical."""

    typing = State()


_REPLY_PROMPT = (
    "💬 <b>Ответ в заявку #{short}</b>\n\n"
    "Пришлите сообщение — можно текст и/или вложения. "
    "Когда закончите, нажмите «Отправить»."
)
_ATTACH_PROMPT = (
    "📎 <b>Вложение в заявку #{short}</b>\n\n"
    "Пришлите файл / фото / видео / голосовое. "
    "Можно добавить сопроводительный текст. "
    "Когда закончите, нажмите «Отправить»."
)


# --- Helpers -------------------------------------------------------------


def _build_prompt_kb(short_id: str, *, has_content: bool) -> InlineKeyboardBuilder:
    kb = InlineKeyboardBuilder()
    if has_content:
        kb.button(text="➡ Отправить", callback_data=f"tl:reply_send:{short_id}")
    kb.button(text="✕ Отмена", callback_data=f"tl:open:{short_id}")
    kb.adjust(1)
    return kb


def _prompt_text(short_id: str, *, mode: str, text_len: int, att_count: int) -> str:
    base = (_ATTACH_PROMPT if mode == "attach" else _REPLY_PROMPT).format(short=short_id)
    counters: list[str] = []
    if text_len:
        counters.append(f"Текст: {text_len} симв.")
    if att_count:
        counters.append(f"Вложений: {att_count}")
    if counters:
        base = base + "\n\n" + " · ".join(counters)
    return base


async def _refresh_reply_prompt(message: Message, state: FSMContext) -> None:
    """Edit the stored prompt message in place with updated counters + Send button.

    Silently no-ops when the prompt message id is missing (user dismissed it,
    bot restart, etc.) — losing the button is annoying but not fatal; the user
    can cancel via /start.
    """
    fsm_data = await state.get_data()
    prompt_msg_id = fsm_data.get("reply_prompt_msg_id")
    if not prompt_msg_id:
        return
    short_id = fsm_data.get("reply_ticket_short", "")
    mode = fsm_data.get("reply_mode", "reply")
    text_body = fsm_data.get("reply_text", "") or ""
    attachments = fsm_data.get("reply_attachments", []) or []
    kb = _build_prompt_kb(short_id, has_content=bool(text_body or attachments))
    new_text = _prompt_text(
        short_id,
        mode=mode,
        text_len=len(text_body),
        att_count=len(attachments),
    )

    from backend.telegram import bot as bot_module
    if bot_module.bot is None:
        return
    try:
        await bot_module.bot.edit_message_text(
            chat_id=message.chat.id,
            message_id=prompt_msg_id,
            text=new_text,
            parse_mode="HTML",
            reply_markup=kb.as_markup(),
        )
    except TelegramBadRequest as exc:
        # "message is not modified" happens if counters didn't change visually.
        logger.debug("reply prompt refresh skipped: %s", exc)


async def _start_reply_flow(
    callback: CallbackQuery,
    state: FSMContext,
    *,
    short_id: str,
    ticket_id: str,
    mode: str,
) -> None:
    """Shared setup for both tl:reply: and tl:attach: entries."""
    await state.set_state(ReplyStates.typing)
    await state.update_data(
        reply_ticket_id=ticket_id,
        reply_ticket_short=short_id,
        reply_mode=mode,
        reply_text="",
        reply_attachments=[],
    )
    kb = _build_prompt_kb(short_id, has_content=False)
    text = _prompt_text(short_id, mode=mode, text_len=0, att_count=0)
    if callback.message is None:
        return
    sent = await callback.message.answer(
        text,
        parse_mode="HTML",
        reply_markup=kb.as_markup(),
    )
    if sent is not None and hasattr(sent, "message_id"):
        await state.update_data(reply_prompt_msg_id=sent.message_id)


# --- Reply entry (tl:reply:<short_id>) -----------------------------------


@router.callback_query(F.data.startswith("tl:reply:"))
async def cb_reply_start(callback: CallbackQuery, state: FSMContext, **data) -> None:
    short_id = callback.data.split(":", 2)[2] if callback.data else ""
    user = data.get("user")
    if user is None:
        await callback.answer("Нужна авторизация.", show_alert=True)
        return
    ticket = await resolve_ticket_by_short_id(short_id, str(user.id))
    if ticket is None:
        await callback.answer("Заявка не найдена.", show_alert=True)
        return
    await _start_reply_flow(
        callback, state, short_id=short_id, ticket_id=ticket.id, mode="reply",
    )
    await callback.answer()


# --- Attachment-only entry (tl:attach:<short_id>) ------------------------


@router.callback_query(F.data.startswith("tl:attach:"))
async def cb_attach_start(callback: CallbackQuery, state: FSMContext, **data) -> None:
    short_id = callback.data.split(":", 2)[2] if callback.data else ""
    user = data.get("user")
    if user is None:
        await callback.answer("Нужна авторизация.", show_alert=True)
        return
    ticket = await resolve_ticket_by_short_id(short_id, str(user.id))
    if ticket is None:
        await callback.answer("Заявка не найдена.", show_alert=True)
        return
    await _start_reply_flow(
        callback, state, short_id=short_id, ticket_id=ticket.id, mode="attach",
    )
    await callback.answer()


# --- Accumulating reply content ------------------------------------------


@router.message(ReplyStates.typing, F.text)
async def msg_reply_text(message: Message, state: FSMContext, **data) -> None:
    incoming = (message.text or "").strip()
    if not incoming:
        return
    fsm_data = await state.get_data()
    current = fsm_data.get("reply_text", "") or ""
    merged = f"{current}\n\n{incoming}" if current else incoming
    await state.update_data(reply_text=merged)
    await _refresh_reply_prompt(message, state)


@router.message(
    ReplyStates.typing,
    F.photo | F.document | F.video | F.voice,
)
async def msg_reply_attachment(message: Message, state: FSMContext, **data) -> None:
    attachment = extract_tg_attachment_meta(message)
    if attachment is None:
        return
    fsm_data = await state.get_data()
    atts = list(fsm_data.get("reply_attachments", []) or [])
    atts.append(attachment)
    await state.update_data(reply_attachments=atts)
    await _refresh_reply_prompt(message, state)


# --- Send the accumulated reply ------------------------------------------


@router.callback_query(F.data.startswith("tl:reply_send:"))
async def cb_reply_send(callback: CallbackQuery, state: FSMContext, **data) -> None:
    short_id = callback.data.split(":", 2)[2] if callback.data else ""
    user = data.get("user")
    if user is None:
        await callback.answer("Нужна авторизация.", show_alert=True)
        return
    fsm_data = await state.get_data()
    ticket_id = fsm_data.get("reply_ticket_id")
    if not ticket_id:
        await callback.answer("Сессия истекла. Откройте заявку заново.", show_alert=True)
        await state.clear()
        return

    text_body = fsm_data.get("reply_text", "") or ""
    attachments = fsm_data.get("reply_attachments", []) or []

    try:
        await add_comment(
            ticket_id=ticket_id,
            user=user,
            text=text_body,
            attachments=attachments,
        )
    except ValueError as exc:
        code = str(exc)
        if code == "empty":
            await callback.answer(
                "Добавьте текст или вложение.", show_alert=False,
            )
            return
        logger.warning("add_comment failed (%s): %s", short_id, code)
        await callback.answer(
            "Не удалось добавить комментарий.", show_alert=True,
        )
        return
    except Exception as exc:  # defensive: don't leak tracebacks to chat
        logger.exception("add_comment crashed for ticket=%s: %s", short_id, exc)
        await callback.answer(
            "Не удалось добавить комментарий.", show_alert=True,
        )
        return

    await state.clear()

    kb = InlineKeyboardBuilder()
    kb.button(text="📋 Открыть заявку", callback_data=f"tl:open:{short_id}")
    kb.button(text="🏠 Меню", callback_data="mm:main")
    kb.adjust(2)
    if callback.message is not None:
        try:
            await callback.message.edit_text(
                "✅ Ответ отправлен.",
                reply_markup=kb.as_markup(),
            )
        except TelegramBadRequest as exc:
            logger.debug("reply success edit skipped: %s", exc)
    await callback.answer()


# --- Close ticket flow ---------------------------------------------------


@router.callback_query(F.data.startswith("tl:close:"))
async def cb_close_confirm_prompt(callback: CallbackQuery, **data) -> None:
    """First click on «Закрыть» — show confirmation."""
    short_id = callback.data.split(":", 2)[2] if callback.data else ""
    user = data.get("user")
    if user is None:
        await callback.answer("Нужна авторизация.", show_alert=True)
        return
    ticket = await resolve_ticket_by_short_id(short_id, str(user.id))
    if ticket is None:
        await callback.answer("Заявка не найдена.", show_alert=True)
        return
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Да, закрыть", callback_data=f"tl:close_yes:{short_id}")
    kb.button(text="✕ Нет", callback_data=f"tl:open:{short_id}")
    kb.adjust(2)
    if callback.message is not None:
        try:
            await callback.message.edit_text(
                f"⚠ <b>Закрыть заявку #{short_id}?</b>\n\n"
                "После закрытия статус поменять уже нельзя.",
                parse_mode="HTML",
                reply_markup=kb.as_markup(),
            )
        except TelegramBadRequest as exc:
            logger.debug("close confirm edit skipped: %s", exc)
    await callback.answer()


@router.callback_query(F.data.startswith("tl:close_yes:"))
async def cb_close_execute(callback: CallbackQuery, **data) -> None:
    short_id = callback.data.split(":", 2)[2] if callback.data else ""
    user = data.get("user")
    if user is None:
        await callback.answer("Нужна авторизация.", show_alert=True)
        return
    ticket = await resolve_ticket_by_short_id(short_id, str(user.id))
    if ticket is None:
        await callback.answer("Заявка не найдена.", show_alert=True)
        return
    try:
        await close_ticket(ticket.id, user)
    except ValueError as exc:
        code = str(exc)
        if code == "already_closed":
            await callback.answer("Заявка уже закрыта.", show_alert=False)
        elif code == "not_owner":
            await callback.answer("Это не ваша заявка.", show_alert=True)
        else:
            await callback.answer("Не удалось закрыть заявку.", show_alert=True)
        return
    except Exception as exc:
        logger.exception("close_ticket crashed for ticket=%s: %s", short_id, exc)
        await callback.answer("Не удалось закрыть заявку.", show_alert=True)
        return

    kb = InlineKeyboardBuilder()
    kb.button(text="📋 Открыть заявку", callback_data=f"tl:open:{short_id}")
    kb.button(text="🏠 Меню", callback_data="mm:main")
    kb.adjust(2)
    if callback.message is not None:
        try:
            await callback.message.edit_text(
                f"✅ Заявка #{short_id} закрыта.",
                reply_markup=kb.as_markup(),
            )
        except TelegramBadRequest as exc:
            logger.debug("close success edit skipped: %s", exc)
    await callback.answer("Заявка закрыта.")

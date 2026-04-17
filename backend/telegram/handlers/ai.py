from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from backend.telegram.formatters import escape_html
from backend.telegram.services.ai_service import ask

logger = logging.getLogger(__name__)

router = Router(name="ai")


class AiStates(StatesGroup):
    chatting = State()


_INTRO = (
    "🤖 <b>AI-помощник</b>\n\n"
    "Задайте вопрос — я постараюсь помочь, опираясь на базу знаний."
)

_HISTORY_TURN_LIMIT = 6  # matches ai_service
_ANSWER_DISPLAY_LIMIT = 3500


def _exit_only_kb():
    builder = InlineKeyboardBuilder()
    builder.button(text="⬅ Выйти в меню", callback_data="ai:exit")
    builder.adjust(1)
    return builder.as_markup()


def _answer_kb(sources: list[dict]):
    """Sources (one button per source) + [Создать заявку] + [Выйти]."""
    builder = InlineKeyboardBuilder()
    for i, src in enumerate(sources, start=1):
        title = (src.get("title") or "").strip()
        slug = (src.get("slug") or "").strip()
        if not title or not slug:
            # Skip sources we can't deep-link into the KB view.
            continue
        label = f"📄 {title}"
        if len(label) > 55:
            label = label[:54].rstrip() + "…"
        # Guard slug length (64-byte callback cap).
        cb_slug = slug if len(slug) <= 50 else slug[:48] + "…"
        builder.row(
            InlineKeyboardButton(text=label, callback_data=f"kb:open:{cb_slug}")
        )
    builder.row(
        InlineKeyboardButton(text="📝 Создать заявку", callback_data="ai:mkticket")
    )
    builder.row(
        InlineKeyboardButton(text="⬅ Выйти в меню", callback_data="ai:exit")
    )
    return builder.as_markup()


def _format_answer(result: dict) -> str:
    answer = (result.get("answer") or "").strip()
    if len(answer) > _ANSWER_DISPLAY_LIMIT:
        answer = answer[: _ANSWER_DISPLAY_LIMIT - 1].rstrip() + "…"
    return f"🤖 {escape_html(answer)}"


async def _send_answer(
    chat_target: Message | CallbackQuery,
    result: dict,
) -> None:
    text = _format_answer(result)
    kb = _answer_kb(result.get("sources") or [])
    if isinstance(chat_target, CallbackQuery):
        if chat_target.message:
            try:
                await chat_target.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
            except TelegramBadRequest as exc:
                logger.debug("ai answer edit skipped: %s", exc)
    else:
        await chat_target.answer(text, parse_mode="HTML", reply_markup=kb)


# --- mm:ai entry ---------------------------------------------------------


@router.callback_query(F.data == "mm:ai")
async def cb_ai_entry(callback: CallbackQuery, state: FSMContext, **data) -> None:
    await state.set_state(AiStates.chatting)
    await state.update_data(ai_history=[])
    if callback.message:
        try:
            await callback.message.edit_text(
                _INTRO,
                parse_mode="HTML",
                reply_markup=_exit_only_kb(),
            )
        except TelegramBadRequest as exc:
            logger.debug("ai entry edit skipped: %s", exc)
    await callback.answer()


# --- ft:ai entry (free-text fallback) ------------------------------------


@router.callback_query(F.data == "ft:ai")
async def cb_ft_to_ai(callback: CallbackQuery, state: FSMContext, **data) -> None:
    existing = await state.get_data()
    pending = (existing.get("pending_text") or "").strip()

    await state.set_state(AiStates.chatting)

    if not pending:
        await state.update_data(ai_history=[])
        if callback.message:
            try:
                await callback.message.edit_text(
                    _INTRO,
                    parse_mode="HTML",
                    reply_markup=_exit_only_kb(),
                )
            except TelegramBadRequest as exc:
                logger.debug("ai ft empty edit skipped: %s", exc)
        await callback.answer()
        return

    # Answer the pending text right away.
    await callback.answer("Думаю…", show_alert=False)
    try:
        result = await ask(pending, history=[])
    except Exception as exc:  # ai_service should never raise, but belt + braces
        logger.warning("ai ask failed unexpectedly: %s", exc)
        result = {
            "answer": (
                "🤖 AI-ассистент временно недоступен. Попробуйте позже "
                "или создайте заявку."
            ),
            "sources": [],
        }

    # Seed history with this turn.
    history = [
        {"role": "user", "content": pending},
        {"role": "assistant", "content": result.get("answer") or ""},
    ][-_HISTORY_TURN_LIMIT:]
    await state.update_data(ai_history=history)

    await _send_answer(callback, result)


# --- chatting: free text --------------------------------------------------


@router.message(AiStates.chatting, F.text)
async def msg_ai_chat(message: Message, state: FSMContext, **data) -> None:
    query = (message.text or "").strip()
    if not query:
        return

    # Best-effort typing indicator — ignore if aiogram's API differs.
    try:
        from backend.telegram import bot as bot_module
        if bot_module.bot is not None:
            await bot_module.bot.send_chat_action(chat_id=message.chat.id, action="typing")
    except Exception as exc:
        logger.debug("ai typing indicator skipped: %s", exc)

    existing = await state.get_data()
    history = list(existing.get("ai_history") or [])

    try:
        result = await ask(query, history=history)
    except Exception as exc:
        logger.warning("ai ask failed unexpectedly: %s", exc)
        result = {
            "answer": (
                "🤖 AI-ассистент временно недоступен. Попробуйте позже "
                "или создайте заявку."
            ),
            "sources": [],
        }

    # Append this turn and trim.
    history.append({"role": "user", "content": query})
    history.append({"role": "assistant", "content": result.get("answer") or ""})
    history = history[-_HISTORY_TURN_LIMIT:]
    await state.update_data(ai_history=history)

    await _send_answer(message, result)


# --- ai:exit --------------------------------------------------------------


@router.callback_query(F.data == "ai:exit")
async def cb_ai_exit(callback: CallbackQuery, state: FSMContext, **data) -> None:
    # Lazy import to avoid circular imports with menu.
    from backend.telegram.handlers.menu import show_main_menu
    user = data.get("user")
    await show_main_menu(callback, user, state)


# --- ai:mkticket ----------------------------------------------------------


@router.callback_query(F.data == "ai:mkticket")
async def cb_ai_mkticket(callback: CallbackQuery, state: FSMContext, **data) -> None:
    """Seed the ticket wizard with the last user message from the AI chat."""
    existing = await state.get_data()
    history = existing.get("ai_history") or []

    last_user_text = ""
    for entry in reversed(history):
        if entry.get("role") == "user":
            last_user_text = (entry.get("content") or "").strip()
            break

    description_seed = last_user_text
    if description_seed:
        description_seed += "\n\n(Из AI-чата)"

    from backend.telegram.handlers.tickets_create import (
        CreateTicketStates,
        _PRODUCT_PROMPT,
    )
    from backend.telegram.keyboards.ticket_wizard import product_kb

    await state.set_state(CreateTicketStates.product)
    new_data: dict = {"attachments": []}
    if description_seed:
        new_data["description"] = description_seed
        new_data["pending_text"] = description_seed
    await state.set_data(new_data)

    if callback.message:
        try:
            await callback.message.edit_text(
                _PRODUCT_PROMPT,
                parse_mode="HTML",
                reply_markup=product_kb(),
            )
        except TelegramBadRequest as exc:
            logger.debug("ai mkticket edit skipped: %s", exc)
    await callback.answer()

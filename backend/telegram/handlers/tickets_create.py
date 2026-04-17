from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from backend.telegram.formatters import escape_html
from backend.telegram.keyboards.ticket_wizard import (
    CATEGORY_LABELS,
    PRODUCT_CATEGORIES,
    PRODUCT_LABELS,
    category_kb,
    description_status_kb,
    product_kb,
)

logger = logging.getLogger(__name__)

router = Router(name="tickets_create")


class CreateTicketStates(StatesGroup):
    product = State()
    category = State()
    description = State()
    kb_deflection = State()     # Task 8
    impact_urgency = State()    # Task 8
    confirm = State()           # Task 8


_PRODUCT_PROMPT = "📝 <b>Новая заявка</b>\n\nВыберите продукт:"

_DESCRIPTION_PROMPT = (
    "📝 <b>Опишите проблему</b>\n\n"
    "Что произошло? Когда? Кто затронут? Пришлите текст (можно несколькими "
    "сообщениями) и приложите скриншоты/видео/голос по необходимости.\n\n"
    "Минимум — 10 символов ИЛИ одно вложение."
)


# --- Helpers -------------------------------------------------------------


async def _refresh_description_status(chat_id: int, state: FSMContext) -> None:
    """Refresh the description-prompt keyboard with updated counters.

    Reads FSM data, builds a new ``description_status_kb`` and edits the
    ORIGINAL description-prompt message's reply markup (keeps prompt text
    stable, just toggles counters and the "Далее" button).
    """
    data = await state.get_data()
    prompt_msg_id = data.get("description_prompt_msg_id")
    if not prompt_msg_id:
        return
    description = data.get("description", "") or ""
    attachments = data.get("attachments", []) or []
    kb = description_status_kb(len(description), len(attachments))

    # Lazy import to avoid circular import at module load.
    from backend.telegram import bot as bot_module
    if bot_module.bot is None:
        return
    try:
        await bot_module.bot.edit_message_reply_markup(
            chat_id=chat_id,
            message_id=prompt_msg_id,
            reply_markup=kb,
        )
    except TelegramBadRequest as exc:
        # Telegram raises "message is not modified" if the markup is identical.
        # That's fine — means the counters didn't visibly change.
        logger.debug("description status refresh skipped: %s", exc)


# --- Entry ---------------------------------------------------------------


@router.callback_query(F.data == "mm:tc")
async def cb_start_wizard(
    callback: CallbackQuery,
    state: FSMContext,
    **data,
) -> None:
    """Entry from main menu — show product picker."""
    existing = await state.get_data()
    await state.set_state(CreateTicketStates.product)
    # Preserve pending_text (from free-text fallback / AI chat) if present.
    new_data: dict = {"attachments": []}
    if existing.get("pending_text"):
        new_data["pending_text"] = existing["pending_text"]
    await state.set_data(new_data)

    if callback.message:
        await callback.message.edit_text(
            _PRODUCT_PROMPT,
            parse_mode="HTML",
            reply_markup=product_kb(),
        )
    await callback.answer()


@router.callback_query(F.data == "ft:ticket")
async def cb_free_text_to_ticket(
    callback: CallbackQuery,
    state: FSMContext,
    **data,
) -> None:
    """Entry from free-text fallback — pre-seed description and show product picker."""
    existing = await state.get_data()
    pending_text = (existing.get("pending_text") or "").strip()

    await state.set_state(CreateTicketStates.product)
    new_data: dict = {"attachments": []}
    if pending_text:
        new_data["description"] = pending_text
        # Keep pending_text for backward-compat with AI-chat flow (Task 11).
        new_data["pending_text"] = pending_text
    await state.set_data(new_data)

    if callback.message:
        await callback.message.edit_text(
            _PRODUCT_PROMPT,
            parse_mode="HTML",
            reply_markup=product_kb(),
        )
    await callback.answer()


# --- Product step --------------------------------------------------------


@router.callback_query(CreateTicketStates.product, F.data.startswith("tc:prod:"))
async def cb_pick_product(
    callback: CallbackQuery,
    state: FSMContext,
    **data,
) -> None:
    product = (callback.data or "").split(":", 2)[2] if callback.data else ""
    if product not in PRODUCT_LABELS:
        await callback.answer("Неизвестный продукт", show_alert=False)
        return

    await state.update_data(product=product)
    await state.set_state(CreateTicketStates.category)

    text = f"📝 <b>{escape_html(PRODUCT_LABELS[product])}</b>\n\nКатегория:"
    if callback.message:
        await callback.message.edit_text(
            text,
            parse_mode="HTML",
            reply_markup=category_kb(product),
        )
    await callback.answer()


# --- Category step -------------------------------------------------------


@router.callback_query(CreateTicketStates.category, F.data.startswith("tc:cat:"))
async def cb_pick_category(
    callback: CallbackQuery,
    state: FSMContext,
    **data,
) -> None:
    category = (callback.data or "").split(":", 2)[2] if callback.data else ""
    fsm_data = await state.get_data()
    product = fsm_data.get("product", "")
    allowed = PRODUCT_CATEGORIES.get(product, [])
    if category not in allowed:
        await callback.answer("Недоступная категория", show_alert=False)
        return

    await state.update_data(category=category)
    await state.set_state(CreateTicketStates.description)

    description = fsm_data.get("description", "") or ""
    attachments = fsm_data.get("attachments", []) or []
    kb = description_status_kb(len(description), len(attachments))

    if callback.message:
        edited = await callback.message.edit_text(
            _DESCRIPTION_PROMPT,
            parse_mode="HTML",
            reply_markup=kb,
        )
        # Track the prompt message id so attachment/text handlers can refresh
        # its reply markup instead of spamming the chat.
        if edited is not None and hasattr(edited, "message_id"):
            await state.update_data(description_prompt_msg_id=edited.message_id)
    await callback.answer()


# --- Description step ----------------------------------------------------


@router.message(CreateTicketStates.description, F.text)
async def msg_description_text(
    message: Message,
    state: FSMContext,
    **data,
) -> None:
    fsm_data = await state.get_data()
    existing = fsm_data.get("description", "") or ""
    incoming = (message.text or "").strip()
    if not incoming:
        return
    new_description = f"{existing}\n\n{incoming}" if existing else incoming
    await state.update_data(description=new_description)
    await _refresh_description_status(message.chat.id, state)


@router.message(
    CreateTicketStates.description,
    F.photo | F.document | F.video | F.voice,
)
async def msg_description_attachment(
    message: Message,
    state: FSMContext,
    **data,
) -> None:
    attachment: dict | None = None

    if message.photo:
        photo = message.photo[-1]  # largest size
        file_id = photo.file_id
        attachment = {
            "file_id": file_id,
            "filename": f"photo_{file_id[:8]}.jpg",
            "content_type": "image/jpeg",
            "size": photo.file_size,
        }
    elif message.document:
        doc = message.document
        file_id = doc.file_id
        attachment = {
            "file_id": file_id,
            "filename": doc.file_name or f"doc_{file_id[:8]}",
            "content_type": doc.mime_type or "application/octet-stream",
            "size": doc.file_size,
        }
    elif message.video:
        video = message.video
        file_id = video.file_id
        attachment = {
            "file_id": file_id,
            "filename": f"video_{file_id[:8]}.mp4",
            "content_type": "video/mp4",
            "size": video.file_size,
        }
    elif message.voice:
        voice = message.voice
        file_id = voice.file_id
        attachment = {
            "file_id": file_id,
            "filename": f"voice_{file_id[:8]}.ogg",
            "content_type": "audio/ogg",
            "size": voice.file_size,
        }

    if attachment is None:
        return

    fsm_data = await state.get_data()
    attachments = list(fsm_data.get("attachments", []) or [])
    attachments.append(attachment)
    await state.update_data(attachments=attachments)
    await _refresh_description_status(message.chat.id, state)


# --- Back / cancel -------------------------------------------------------


@router.callback_query(F.data == "tc:back:prod")
async def cb_back_to_product(
    callback: CallbackQuery,
    state: FSMContext,
    **data,
) -> None:
    """Return to product step. Keeps description/attachments for reuse."""
    # Drop product/category selection; keep description + attachments.
    fsm_data = await state.get_data()
    fsm_data.pop("product", None)
    fsm_data.pop("category", None)
    fsm_data.pop("description_prompt_msg_id", None)
    await state.set_data(fsm_data)
    await state.set_state(CreateTicketStates.product)

    if callback.message:
        await callback.message.edit_text(
            _PRODUCT_PROMPT,
            parse_mode="HTML",
            reply_markup=product_kb(),
        )
    await callback.answer()


@router.callback_query(F.data == "tc:back:cat")
async def cb_back_to_category(
    callback: CallbackQuery,
    state: FSMContext,
    **data,
) -> None:
    """Return to category step. Keeps description/attachments for reuse."""
    fsm_data = await state.get_data()
    product = fsm_data.get("product", "")
    if product not in PRODUCT_LABELS:
        # Defensive: if product somehow missing, bounce to product step instead.
        await cb_back_to_product(callback, state, **data)
        return
    fsm_data.pop("category", None)
    fsm_data.pop("description_prompt_msg_id", None)
    await state.set_data(fsm_data)
    await state.set_state(CreateTicketStates.category)

    text = f"📝 <b>{escape_html(PRODUCT_LABELS[product])}</b>\n\nКатегория:"
    if callback.message:
        await callback.message.edit_text(
            text,
            parse_mode="HTML",
            reply_markup=category_kb(product),
        )
    await callback.answer()

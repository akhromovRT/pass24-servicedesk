from __future__ import annotations

import logging
from datetime import datetime

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from backend.telegram.deflection import suggest_articles
from backend.telegram.formatters import PRIORITY_EMOJI, STATUS_EMOJI, escape_html
from backend.telegram.keyboards.ticket_wizard import (
    CATEGORY_LABELS,
    PRODUCT_CATEGORIES,
    PRODUCT_LABELS,
    category_kb,
    confirm_kb,
    description_status_kb,
    impact_urgency_kb,
    product_kb,
)
from backend.telegram.services.kb_service import get_article_by_slug
from backend.telegram.services.ticket_service import create_ticket

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


# =============================================================================
# Task 8 — KB deflection, impact/urgency, confirm, create
# =============================================================================


_IMPACT_URGENCY_PROMPT = (
    "⚖ <b>Масштаб и срочность</b> (необязательно)\n\n"
    "Помогает автоматически определить приоритет."
)

_ARTICLE_CONTENT_LIMIT = 3500


def _deflection_list_kb(articles: list[dict]) -> InlineKeyboardBuilder:
    """Build the list-of-articles keyboard for the deflection step."""
    builder = InlineKeyboardBuilder()
    for i, art in enumerate(articles, start=1):
        title = art.get("title") or ""
        # Trim long titles so the button label stays readable on mobile.
        if len(title) > 50:
            title = title[:49].rstrip() + "…"
        builder.row(
            InlineKeyboardButton(
                text=f"📄 {i}. {title}",
                callback_data=f"tc:defl:view:{art['slug']}",
            )
        )
    builder.row(
        InlineKeyboardButton(
            text="➡ Не помогло, создать заявку",
            callback_data="tc:defl:nope",
        )
    )
    builder.row(
        InlineKeyboardButton(text="⬅ Назад", callback_data="tc:back:desc"),
        InlineKeyboardButton(text="✕ Отмена", callback_data="mm:main"),
    )
    return builder


def _deflection_list_text(articles: list[dict]) -> str:
    lines = ["📚 <b>Возможно, поможет одна из этих статей:</b>", ""]
    for i, art in enumerate(articles, start=1):
        title = escape_html(art.get("title") or "")
        lines.append(f"{i}. {title}")
    return "\n".join(lines)


async def _render_deflection_list(
    callback: CallbackQuery, articles: list[dict]
) -> None:
    if callback.message is None:
        return
    kb = _deflection_list_kb(articles)
    try:
        await callback.message.edit_text(
            _deflection_list_text(articles),
            parse_mode="HTML",
            reply_markup=kb.as_markup(),
        )
    except TelegramBadRequest as exc:
        logger.debug("deflection list edit skipped: %s", exc)


async def _show_impact_urgency(
    callback: CallbackQuery, state: FSMContext
) -> None:
    """Render the impact/urgency picker at state.impact_urgency."""
    await state.set_state(CreateTicketStates.impact_urgency)
    fsm_data = await state.get_data()
    impact = fsm_data.get("impact")
    urgency = fsm_data.get("urgency")
    if callback.message:
        try:
            await callback.message.edit_text(
                _IMPACT_URGENCY_PROMPT,
                parse_mode="HTML",
                reply_markup=impact_urgency_kb(impact, urgency),
            )
        except TelegramBadRequest as exc:
            logger.debug("impact/urgency edit skipped: %s", exc)


def _priority_label_ru(priority: str) -> str:
    return {
        "critical": "CRITICAL",
        "high": "HIGH",
        "normal": "NORMAL",
        "low": "LOW",
    }.get(priority, (priority or "").upper())


async def _show_confirm(callback: CallbackQuery, state: FSMContext) -> None:
    """Render the final confirmation preview."""
    await state.set_state(CreateTicketStates.confirm)
    data = await state.get_data()
    product = data.get("product") or ""
    category = data.get("category") or ""
    description = data.get("description") or ""
    attachments = data.get("attachments") or []
    impact = data.get("impact")
    urgency = data.get("urgency")

    product_label = PRODUCT_LABELS.get(product, product)
    category_label = CATEGORY_LABELS.get(category, category)

    lines: list[str] = [
        "📝 <b>Подтвердите создание заявки</b>",
        "",
        f"<b>Продукт:</b> {escape_html(product_label)}",
        f"<b>Категория:</b> {escape_html(category_label)}",
    ]
    if impact and urgency:
        impact_labels = {"high": "Все/объект", "medium": "Группа", "low": "Только я"}
        urgency_labels = {
            "high": "Немедленно",
            "medium": "Сегодня",
            "low": "Может подождать",
        }
        lines.append(
            f"<b>Масштаб / Срочность:</b> "
            f"{escape_html(impact_labels.get(impact, impact))}"
            f" / {escape_html(urgency_labels.get(urgency, urgency))}"
        )
    if attachments:
        lines.append(f"<b>Вложения:</b> {len(attachments)}")
    lines.append("")
    lines.append("<b>Описание:</b>")
    body = description[:3000]
    suffix = "…" if len(description) > 3000 else ""
    lines.append(f"{escape_html(body)}{suffix}")

    text = "\n".join(lines)
    if callback.message:
        try:
            await callback.message.edit_text(
                text,
                parse_mode="HTML",
                reply_markup=confirm_kb(),
            )
        except TelegramBadRequest as exc:
            logger.debug("confirm edit skipped: %s", exc)


# --- desc_done: KB deflection branch -------------------------------------


@router.callback_query(CreateTicketStates.description, F.data == "tc:desc_done")
async def cb_desc_done(
    callback: CallbackQuery,
    state: FSMContext,
    **data,
) -> None:
    """User clicked [➡ Далее] on the description step."""
    fsm_data = await state.get_data()
    description = (fsm_data.get("description") or "").strip()
    attachments = fsm_data.get("attachments") or []
    if len(description) < 10 and not attachments:
        await callback.answer(
            "Опишите проблему подробнее или прикрепите файл.",
            show_alert=False,
        )
        return

    try:
        articles = await suggest_articles(description)
    except Exception as exc:
        logger.warning("suggest_articles failed: %s", exc)
        articles = []

    if articles:
        await state.set_state(CreateTicketStates.kb_deflection)
        await state.update_data(
            deflection_articles=[
                {"id": a["id"], "slug": a["slug"], "title": a["title"]}
                for a in articles
            ]
        )
        await _render_deflection_list(callback, articles)
        await callback.answer()
        return

    # No articles — skip straight to impact/urgency.
    await _show_impact_urgency(callback, state)
    await callback.answer()


@router.callback_query(
    CreateTicketStates.kb_deflection, F.data.startswith("tc:defl:view:")
)
async def cb_defl_view(
    callback: CallbackQuery,
    state: FSMContext,
    **data,
) -> None:
    slug = (callback.data or "").split(":", 3)[3] if callback.data else ""
    article = await get_article_by_slug(slug)
    if not article:
        await callback.answer("Статья не найдена", show_alert=False)
        return

    title = article.get("title") or ""
    content = article.get("content") or ""
    if len(content) > _ARTICLE_CONTENT_LIMIT:
        content = content[: _ARTICLE_CONTENT_LIMIT - 1].rstrip() + "…"
    text = f"<b>{escape_html(title)}</b>\n\n{escape_html(content)}"

    kb = InlineKeyboardBuilder()
    kb.button(text="👍 Помогло", callback_data=f"tc:defl:helpful:{slug}")
    kb.button(text="👎 Не помогло", callback_data=f"tc:defl:back:{slug}")
    kb.button(text="📝 Всё равно создать заявку", callback_data="tc:defl:nope")
    kb.button(text="⬅ Назад к списку статей", callback_data=f"tc:defl:back:{slug}")
    kb.adjust(2, 1, 1)

    if callback.message:
        try:
            await callback.message.edit_text(
                text,
                parse_mode="HTML",
                reply_markup=kb.as_markup(),
            )
        except TelegramBadRequest as exc:
            logger.debug("article view edit skipped: %s", exc)
    await callback.answer()


@router.callback_query(
    CreateTicketStates.kb_deflection, F.data.startswith("tc:defl:helpful:")
)
async def cb_defl_helpful(
    callback: CallbackQuery,
    state: FSMContext,
    **data,
) -> None:
    """User marked the article as helpful — deflected, do NOT create a ticket."""
    slug = (callback.data or "").split(":", 3)[3] if callback.data else ""
    article = await get_article_by_slug(slug)
    # NOTE: ArticleFeedback recording is skipped to keep Task 8 focused.
    # It needs a session_id (localStorage UUID) the bot doesn't have, and
    # adding a source="telegram" feedback row has uniqueness questions.
    # Flag as follow-up.
    if article:
        await state.update_data(
            deflection_helpful_slug=slug,
            deflection_helpful_article_id=article.get("id"),
        )

    await state.clear()

    kb = InlineKeyboardBuilder()
    kb.button(text="🏠 Меню", callback_data="mm:main")
    kb.adjust(1)
    if callback.message:
        try:
            await callback.message.edit_text(
                "✅ Отлично! Рады, что помогло.",
                parse_mode="HTML",
                reply_markup=kb.as_markup(),
            )
        except TelegramBadRequest as exc:
            logger.debug("helpful edit skipped: %s", exc)
    await callback.answer()


@router.callback_query(
    CreateTicketStates.kb_deflection, F.data.startswith("tc:defl:back:")
)
async def cb_defl_back(
    callback: CallbackQuery,
    state: FSMContext,
    **data,
) -> None:
    """From article view → back to the deflection list."""
    fsm_data = await state.get_data()
    articles = fsm_data.get("deflection_articles") or []
    if not articles:
        # Defensive: no articles stored (shouldn't happen) — skip ahead.
        await _show_impact_urgency(callback, state)
        await callback.answer()
        return
    await _render_deflection_list(callback, articles)
    await callback.answer()


@router.callback_query(F.data == "tc:defl:nope")
async def cb_defl_nope(
    callback: CallbackQuery,
    state: FSMContext,
    **data,
) -> None:
    """User wants to proceed with the ticket regardless — go to impact/urgency."""
    await _show_impact_urgency(callback, state)
    await callback.answer()


# --- Impact/urgency step -------------------------------------------------


@router.callback_query(
    CreateTicketStates.impact_urgency, F.data.startswith("tc:imp:")
)
async def cb_pick_impact(
    callback: CallbackQuery,
    state: FSMContext,
    **data,
) -> None:
    value = (callback.data or "").split(":", 2)[2] if callback.data else ""
    if value not in {"high", "medium", "low"}:
        await callback.answer("Неизвестное значение", show_alert=False)
        return
    await state.update_data(impact=value)
    fsm_data = await state.get_data()
    urgency = fsm_data.get("urgency")
    if callback.message:
        try:
            await callback.message.edit_reply_markup(
                reply_markup=impact_urgency_kb(value, urgency),
            )
        except TelegramBadRequest as exc:
            logger.debug("impact markup edit skipped: %s", exc)
    await callback.answer()


@router.callback_query(
    CreateTicketStates.impact_urgency, F.data.startswith("tc:urg:")
)
async def cb_pick_urgency(
    callback: CallbackQuery,
    state: FSMContext,
    **data,
) -> None:
    value = (callback.data or "").split(":", 2)[2] if callback.data else ""
    if value not in {"high", "medium", "low"}:
        await callback.answer("Неизвестное значение", show_alert=False)
        return
    await state.update_data(urgency=value)
    fsm_data = await state.get_data()
    impact = fsm_data.get("impact")
    if callback.message:
        try:
            await callback.message.edit_reply_markup(
                reply_markup=impact_urgency_kb(impact, value),
            )
        except TelegramBadRequest as exc:
            logger.debug("urgency markup edit skipped: %s", exc)
    await callback.answer()


@router.callback_query(
    CreateTicketStates.impact_urgency, F.data.in_({"tc:iu:skip", "tc:iu:done"})
)
async def cb_impact_urgency_proceed(
    callback: CallbackQuery,
    state: FSMContext,
    **data,
) -> None:
    await _show_confirm(callback, state)
    await callback.answer()


# --- Confirmation step ---------------------------------------------------


@router.callback_query(CreateTicketStates.confirm, F.data == "tc:edit_desc")
async def cb_edit_desc(
    callback: CallbackQuery,
    state: FSMContext,
    **data,
) -> None:
    """Return to description step with current contents preserved."""
    await state.set_state(CreateTicketStates.description)
    fsm_data = await state.get_data()
    description = fsm_data.get("description", "") or ""
    attachments = fsm_data.get("attachments", []) or []
    kb = description_status_kb(len(description), len(attachments))
    if callback.message:
        try:
            edited = await callback.message.edit_text(
                _DESCRIPTION_PROMPT,
                parse_mode="HTML",
                reply_markup=kb,
            )
            if edited is not None and hasattr(edited, "message_id"):
                await state.update_data(description_prompt_msg_id=edited.message_id)
        except TelegramBadRequest as exc:
            logger.debug("edit_desc re-render skipped: %s", exc)
    await callback.answer()


@router.callback_query(CreateTicketStates.confirm, F.data == "tc:confirm")
async def cb_confirm(
    callback: CallbackQuery,
    state: FSMContext,
    **data,
) -> None:
    """Final step — persist the ticket."""
    user = data.get("user")
    if user is None:
        await callback.answer(
            "⚠ Не удалось определить пользователя. Попробуйте ещё раз.",
            show_alert=True,
        )
        return

    await callback.answer("Создаю заявку…", show_alert=False)

    fsm_data = await state.get_data()
    try:
        ticket = await create_ticket(fsm_data, user)
    except Exception as exc:
        logger.exception("create_ticket failed: %s", exc)
        if callback.message:
            try:
                await callback.message.answer(
                    "⚠ Не удалось создать заявку. Попробуйте ещё раз или "
                    "обратитесь на support@pass24.online.",
                    parse_mode="HTML",
                )
            except Exception:
                pass
        # Keep FSM state so the user can retry from confirmation.
        return

    # Build success message.
    short_id = (ticket.id or "")[:8]
    priority_val = (
        ticket.priority.value
        if hasattr(ticket.priority, "value")
        else str(ticket.priority or "")
    )
    status_val = (
        ticket.status.value
        if hasattr(ticket.status, "value")
        else str(ticket.status or "")
    )
    priority_emoji = PRIORITY_EMOJI.get(priority_val, "")
    status_emoji = STATUS_EMOJI.get(status_val, "")
    priority_label = _priority_label_ru(priority_val)

    lines: list[str] = [
        f"✅ Заявка #{short_id} создана",
        f"{priority_emoji} {priority_label} • {status_emoji} Новая".strip(),
    ]

    sla_hours = ticket.sla_response_hours
    created_at = ticket.created_at
    if sla_hours and created_at:
        from datetime import timedelta

        deadline = created_at + timedelta(hours=int(sla_hours))
        now = datetime.utcnow()
        delta = deadline - now
        total_min = int(delta.total_seconds() // 60)
        if total_min > 0:
            hh = total_min // 60
            mm = total_min % 60
            human_delta = f"{hh}ч {mm}м" if hh else f"{mm}м"
            lines.append(
                f"SLA ответа: до {deadline.strftime('%H:%M')} (через {human_delta})"
            )

    kb = InlineKeyboardBuilder()
    kb.button(text="📋 Открыть карточку", callback_data=f"tl:open:{short_id}")
    kb.button(text="🏠 Меню", callback_data="mm:main")
    kb.adjust(1)

    await state.clear()
    if callback.message:
        try:
            await callback.message.edit_text(
                "\n".join(lines),
                parse_mode="HTML",
                reply_markup=kb.as_markup(),
            )
        except TelegramBadRequest as exc:
            logger.debug("success edit skipped: %s", exc)


# --- Back from kb_deflection / impact_urgency → description --------------


@router.callback_query(F.data == "tc:back:desc")
async def cb_back_to_description(
    callback: CallbackQuery,
    state: FSMContext,
    **data,
) -> None:
    """Return to the description step (from kb_deflection or impact_urgency)."""
    await state.set_state(CreateTicketStates.description)
    fsm_data = await state.get_data()
    description = fsm_data.get("description", "") or ""
    attachments = fsm_data.get("attachments", []) or []
    kb = description_status_kb(len(description), len(attachments))
    if callback.message:
        try:
            edited = await callback.message.edit_text(
                _DESCRIPTION_PROMPT,
                parse_mode="HTML",
                reply_markup=kb,
            )
            if edited is not None and hasattr(edited, "message_id"):
                await state.update_data(description_prompt_msg_id=edited.message_id)
        except TelegramBadRequest as exc:
            logger.debug("back:desc re-render skipped: %s", exc)
    await callback.answer()

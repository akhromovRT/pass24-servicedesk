from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder

from backend.telegram.formatters import (
    STATUS_EMOJI,
    escape_html,
    format_ticket_card,
    format_ticket_list_item,
)
from backend.telegram.keyboards.ticket_detail import FILTER_LABELS
from backend.telegram.services.ticket_service import (
    get_ticket_with_comments,
    list_my_tickets,
)

router = Router(name="tickets_list")

_PAGE_SIZE = 5
_COMMENTS_LIMIT = 5


@router.callback_query(F.data == "mm:tl")
async def cb_open_list(callback: CallbackQuery, state: FSMContext, **data) -> None:
    """Entry from main menu — show active tickets, page 1."""
    await state.clear()
    await _render_list(callback, data.get("user"), filter_val="active", page=1)


@router.callback_query(F.data.startswith("tl:filter:"))
async def cb_filter(callback: CallbackQuery, **data) -> None:
    filter_val = callback.data.split(":", 2)[2]
    if filter_val not in FILTER_LABELS:
        await callback.answer()
        return
    await _render_list(callback, data.get("user"), filter_val=filter_val, page=1)


@router.callback_query(F.data.startswith("tl:page:"))
async def cb_page(callback: CallbackQuery, **data) -> None:
    # Format: tl:page:N:filter
    parts = callback.data.split(":", 3)
    if len(parts) < 4:
        await callback.answer()
        return
    try:
        page = int(parts[2])
    except ValueError:
        await callback.answer()
        return
    filter_val = parts[3] or "active"
    await _render_list(callback, data.get("user"), filter_val=filter_val, page=page)


@router.callback_query(F.data.startswith("tl:open:"))
async def cb_open_ticket(callback: CallbackQuery, **data) -> None:
    short_id = callback.data.split(":", 2)[2]
    user = data.get("user")
    if user is None:
        await callback.answer("Нужна авторизация.", show_alert=True)
        return
    result = await get_ticket_with_comments(short_id, str(user.id))
    if result is None:
        await callback.answer("Заявка не найдена.", show_alert=True)
        return
    await _render_ticket_card(callback, result, short_id)


@router.callback_query(F.data.startswith("tl:history:"))
async def cb_history_page(callback: CallbackQuery, **data) -> None:
    # Format: tl:history:<short_id>:<offset>
    parts = callback.data.split(":", 3)
    if len(parts) < 4:
        await callback.answer()
        return
    short_id = parts[2]
    try:
        offset = int(parts[3])
    except ValueError:
        offset = 0
    user = data.get("user")
    if user is None:
        await callback.answer()
        return
    result = await get_ticket_with_comments(
        short_id, str(user.id), comments_limit=_COMMENTS_LIMIT, comments_offset=offset,
    )
    if result is None:
        await callback.answer("Заявка не найдена.", show_alert=True)
        return
    await _render_ticket_card(callback, result, short_id, comments_offset=offset)


# --- helpers ---------------------------------------------------------------

async def _render_list(callback, user, *, filter_val: str, page: int) -> None:
    if user is None:
        await callback.answer("Нужна авторизация.", show_alert=True)
        return
    tickets, total, total_pages = await list_my_tickets(
        str(user.id), filter=filter_val, page=page, per_page=_PAGE_SIZE,
    )
    if total == 0:
        text = (
            f"📋 <b>Мои заявки</b> — {FILTER_LABELS[filter_val]}\n\n"
            "Здесь пока ничего нет."
        )
    else:
        lines = [
            f"📋 <b>Мои заявки</b> — {FILTER_LABELS[filter_val]} "
            f"(всего {total})",
            "",
        ]
        for t in tickets:
            lines.append(format_ticket_list_item(t))
        text = "\n".join(lines)

    kb = InlineKeyboardBuilder()
    # Filter row
    for key, label in FILTER_LABELS.items():
        prefix = "✓ " if key == filter_val else ""
        kb.button(text=f"{prefix}{label}", callback_data=f"tl:filter:{key}")
    kb.adjust(3)

    # Ticket rows — each opens the card
    for t in tickets:
        kb.row()
        kb.button(
            text=f"{STATUS_EMOJI.get(t.status, '')} #{t.id[:8]}",
            callback_data=f"tl:open:{t.id[:8]}",
        )

    # Pagination row (rebuilt inline — merging foreign InlineKeyboardMarkup into
    # an InlineKeyboardBuilder is awkward; see pagination_kb for the canonical
    # shape we mirror here).
    if total_pages > 1:
        kb.row()
        if page > 1:
            kb.button(text="◀ Пред", callback_data=f"tl:page:{page - 1}:{filter_val}")
        kb.button(text=f"Стр {page}/{total_pages}", callback_data="noop")
        if page < total_pages:
            kb.button(text="След ▶", callback_data=f"tl:page:{page + 1}:{filter_val}")

    # Back to menu row
    kb.row()
    kb.button(text="🏠 Меню", callback_data="mm:main")

    if callback.message is not None:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb.as_markup())
    await callback.answer()


async def _render_ticket_card(callback, result: dict, short_id: str, *, comments_offset: int = 0) -> None:
    ticket = result["ticket"]
    comments = result["comments"]
    total_comments = result["total_comments"]

    lines = [format_ticket_card(ticket)]
    if total_comments == 0:
        lines.append("\n<i>Пока нет комментариев.</i>")
    else:
        shown_from = comments_offset + 1
        shown_to = comments_offset + len(comments)
        lines.append(f"\n💬 <b>Комментарии {shown_from}–{shown_to} из {total_comments}</b>\n")
        for c in comments:
            author = escape_html(c.author_name or "—")
            when = c.created_at.strftime("%d.%m %H:%M") if c.created_at else ""
            body = escape_html(c.text or "")[:1500]
            lines.append(f"<b>{author}</b> · <i>{when}</i>\n{body}")

    text = "\n".join(lines)

    # Build keyboard inline (avoid InlineKeyboardMarkup merge headaches).
    # Action callbacks (tl:reply / tl:attach / tl:close / tl:csat) are wired
    # here so Task 10 can bind handlers without changing this keyboard.
    kb = InlineKeyboardBuilder()
    kb.button(text="💬 Ответить", callback_data=f"tl:reply:{short_id}")
    kb.button(text="📎 Вложение", callback_data=f"tl:attach:{short_id}")
    if ticket.status not in {"closed", "resolved"}:
        kb.button(text="✕ Закрыть", callback_data=f"tl:close:{short_id}")
    if ticket.status == "resolved":
        kb.button(text="⭐ Оценить", callback_data=f"tl:csat:{short_id}")
    kb.adjust(2)

    # Pagination for comments if there are more
    next_offset = comments_offset + len(comments)
    if next_offset < total_comments:
        kb.row()
        kb.button(
            text="⬇ Ещё комментарии",
            callback_data=f"tl:history:{short_id}:{next_offset}",
        )
    if comments_offset > 0:
        kb.row()
        kb.button(
            text="⬆ Сначала",
            callback_data=f"tl:history:{short_id}:0",
        )

    kb.row()
    kb.button(text="⬅ К списку", callback_data="mm:tl")
    kb.button(text="🏠 Меню", callback_data="mm:main")

    if callback.message is not None:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb.as_markup())
    await callback.answer()

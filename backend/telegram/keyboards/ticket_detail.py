from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


FILTER_LABELS: dict[str, str] = {
    "active": "🟢 Активные",
    "all": "📋 Все",
    "closed": "⚫ Закрытые",
}


def list_filter_kb(current_filter: str, has_pagination: bool = False) -> InlineKeyboardMarkup:
    """Top row of filter buttons; highlights the current one with ✓."""
    kb = InlineKeyboardBuilder()
    for key, label in FILTER_LABELS.items():
        prefix = "✓ " if key == current_filter else ""
        kb.button(text=f"{prefix}{label}", callback_data=f"tl:filter:{key}")
    kb.adjust(3)
    # Back to menu button
    kb.row(InlineKeyboardButton(text="🏠 Меню", callback_data="mm:main"))
    return kb.as_markup()


def ticket_actions_kb(ticket_id_short: str, status: str) -> InlineKeyboardMarkup:
    """Action buttons for a ticket card.

    - Always: [💬 Ответить] [📎 Вложение]  (reply + attachment are Task 10)
    - If status != closed/resolved: [✕ Закрыть]
    - If status == resolved: [⭐ Оценить]
    - [⬅ К списку] [🏠 Меню]

    Task 10 owns the actual handlers; buttons are emitted here so Task 10
    can bind callbacks without touching this keyboard.
    """
    kb = InlineKeyboardBuilder()
    kb.button(text="💬 Ответить", callback_data=f"tl:reply:{ticket_id_short}")
    kb.button(text="📎 Вложение", callback_data=f"tl:attach:{ticket_id_short}")
    if status not in {"closed", "resolved"}:
        kb.button(text="✕ Закрыть", callback_data=f"tl:close:{ticket_id_short}")
    if status == "resolved":
        kb.button(text="⭐ Оценить", callback_data=f"tl:csat:{ticket_id_short}")
    kb.adjust(2)
    kb.row(
        InlineKeyboardButton(text="⬅ К списку", callback_data="mm:tl"),
        InlineKeyboardButton(text="🏠 Меню", callback_data="mm:main"),
    )
    return kb.as_markup()

from __future__ import annotations

from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


def cancel_kb() -> InlineKeyboardMarkup:
    """Single [✕ Отмена] button returning to main menu."""
    builder = InlineKeyboardBuilder()
    builder.button(text="✕ Отмена", callback_data="mm:main")
    builder.adjust(1)
    return builder.as_markup()


def back_cancel_kb(back_cb: str) -> InlineKeyboardMarkup:
    """[⬅ Назад] + [✕ Отмена] row."""
    builder = InlineKeyboardBuilder()
    builder.button(text="⬅ Назад", callback_data=back_cb)
    builder.button(text="✕ Отмена", callback_data="mm:main")
    builder.adjust(2)
    return builder.as_markup()


def pagination_kb(
    prefix: str,
    page: int,
    total_pages: int,
    filter_val: str = "",
) -> InlineKeyboardMarkup:
    """Pagination row: [◀ Пред] Стр N/M [След ▶].

    Callback pattern: ``{prefix}:page:{N}:{filter_val}``.
    The middle button is a no-op (callback_data='noop').
    Prev button is omitted on page 1; next button is omitted on the last page.
    """
    builder = InlineKeyboardBuilder()
    total_pages = max(total_pages, 1)
    page = max(1, min(page, total_pages))

    row_buttons = 0
    if page > 1:
        builder.button(
            text="◀ Пред",
            callback_data=f"{prefix}:page:{page - 1}:{filter_val}",
        )
        row_buttons += 1

    builder.button(text=f"Стр {page}/{total_pages}", callback_data="noop")
    row_buttons += 1

    if page < total_pages:
        builder.button(
            text="След ▶",
            callback_data=f"{prefix}:page:{page + 1}:{filter_val}",
        )
        row_buttons += 1

    builder.adjust(row_buttons)
    return builder.as_markup()

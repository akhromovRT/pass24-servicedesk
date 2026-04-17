from __future__ import annotations

from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from backend.auth.models import User, UserRole


def main_menu_kb(
    user: User | None,
    *,
    active_tickets: int = 0,
    pending_approvals: int = 0,
) -> InlineKeyboardMarkup:
    """Main menu keyboard shown after /start and as root navigation.

    PMs with a customer_id get an extra 'Мои проекты' row.
    Counters are appended only when greater than zero.
    """
    builder = InlineKeyboardBuilder()

    builder.button(text="📝 Новая заявка", callback_data="mm:tc")

    tickets_label = "📋 Мои заявки"
    if active_tickets > 0:
        tickets_label = f"{tickets_label} • {active_tickets}"
    builder.button(text=tickets_label, callback_data="mm:tl")

    builder.button(text="📚 База знаний", callback_data="mm:kb")
    builder.button(text="🤖 Спросить AI", callback_data="mm:ai")
    builder.button(text="⚙ Настройки", callback_data="mm:st")

    if (
        user is not None
        and user.role == UserRole.PROPERTY_MANAGER
        and user.customer_id
    ):
        projects_label = "🏗 Мои проекты"
        if pending_approvals > 0:
            projects_label = f"{projects_label} • {pending_approvals}⏳"
        builder.button(text=projects_label, callback_data="mm:pr")

    builder.adjust(1)
    return builder.as_markup()

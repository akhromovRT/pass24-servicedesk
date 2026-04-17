from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


PRODUCT_LABELS: dict[str, str] = {
    "pass24_online":  "🏠 PASS24.online",
    "mobile_app":     "📱 Мобильное приложение",
    "pass24_key":     "🔑 PASS24 Key",
    "pass24_control": "📷 Распознавание",
    "pass24_auto":    "🚗 PASS24 Auto",
    "equipment":      "🔌 Оборудование",
    "integration":    "🔗 Интеграции",
    "other":          "❓ Другое",
}

PRODUCT_CATEGORIES: dict[str, list[str]] = {
    "pass24_online":  ["passes", "objects", "trusted_persons", "consultation", "other"],
    "mobile_app":     ["app_issues", "passes", "recognition", "registration", "consultation", "other"],
    "pass24_key":     ["app_issues", "passes", "equipment_issues", "consultation", "other"],
    "pass24_control": ["recognition", "equipment_issues", "consultation", "other"],
    "pass24_auto":    ["recognition", "equipment_issues", "consultation", "other"],
    "equipment":      ["equipment_issues", "consultation", "other"],
    "integration":    ["feature_request", "consultation", "other"],
    "other":          ["consultation", "feature_request", "other"],
}

CATEGORY_LABELS: dict[str, str] = {
    "registration":     "📝 Регистрация",
    "passes":           "🎫 Пропуска",
    "recognition":      "📷 Распознавание",
    "app_issues":       "📱 Проблемы с приложением",
    "objects":          "🏢 Объекты",
    "trusted_persons":  "👥 Доверенные лица",
    "equipment_issues": "🔌 Оборудование",
    "consultation":     "💬 Консультация",
    "feature_request":  "💡 Предложение / идея",
    "other":            "❓ Другое",
}

IMPACT_LABELS: dict[str, str] = {
    "high":   "🌐 Все / весь объект",
    "medium": "👥 Группа",
    "low":    "👤 Только я",
}

URGENCY_LABELS: dict[str, str] = {
    "high":   "🔴 Немедленно",
    "medium": "🟡 Сегодня",
    "low":    "🟢 Может подождать",
}


def product_kb() -> InlineKeyboardMarkup:
    """Product picker — 8 buttons, 2 per row, plus cancel row."""
    builder = InlineKeyboardBuilder()
    for value, label in PRODUCT_LABELS.items():
        builder.button(text=label, callback_data=f"tc:prod:{value}")
    builder.adjust(2, 2, 2, 2)
    builder.row(InlineKeyboardButton(text="✕ Отмена", callback_data="mm:main"))
    return builder.as_markup()


def category_kb(product: str) -> InlineKeyboardMarkup:
    """Category picker filtered by product. One category per row."""
    builder = InlineKeyboardBuilder()
    categories = PRODUCT_CATEGORIES.get(product, [])
    for value in categories:
        label = CATEGORY_LABELS.get(value, value)
        builder.button(text=label, callback_data=f"tc:cat:{value}")
    builder.adjust(*([1] * len(categories)) if categories else [1])
    builder.row(
        InlineKeyboardButton(text="⬅ Назад", callback_data="tc:back:prod"),
        InlineKeyboardButton(text="✕ Отмена", callback_data="mm:main"),
    )
    return builder.as_markup()


def description_status_kb(
    char_count: int,
    attachment_count: int,
    *,
    min_chars: int = 10,
) -> InlineKeyboardMarkup:
    """Description step status: counters row + action row.

    Row 1: status-only buttons (callback_data="noop"): char counter and, when
    attachments > 0, attachment counter.
    Row 2: [➡ Далее] (only when threshold met), plus [⬅ Назад] [✕ Отмена].
    """
    builder = InlineKeyboardBuilder()
    status_buttons: list[InlineKeyboardButton] = [
        InlineKeyboardButton(text=f"📝 {char_count} симв.", callback_data="noop"),
    ]
    if attachment_count > 0:
        status_buttons.append(
            InlineKeyboardButton(
                text=f"📎 {attachment_count} вложений",
                callback_data="noop",
            )
        )
    builder.row(*status_buttons)

    can_proceed = char_count >= min_chars or attachment_count > 0
    action_buttons: list[InlineKeyboardButton] = []
    if can_proceed:
        action_buttons.append(
            InlineKeyboardButton(text="➡ Далее", callback_data="tc:desc_done")
        )
    action_buttons.append(
        InlineKeyboardButton(text="⬅ Назад", callback_data="tc:back:cat")
    )
    action_buttons.append(
        InlineKeyboardButton(text="✕ Отмена", callback_data="mm:main")
    )
    builder.row(*action_buttons)
    return builder.as_markup()


def impact_urgency_kb(
    impact: str | None = None,
    urgency: str | None = None,
) -> InlineKeyboardMarkup:
    """Impact + urgency picker with checkmark on the selected option."""
    builder = InlineKeyboardBuilder()

    impact_row: list[InlineKeyboardButton] = []
    for value, label in IMPACT_LABELS.items():
        prefix = "✓ " if impact == value else ""
        impact_row.append(
            InlineKeyboardButton(
                text=f"{prefix}{label}",
                callback_data=f"tc:imp:{value}",
            )
        )
    builder.row(*impact_row)

    urgency_row: list[InlineKeyboardButton] = []
    for value, label in URGENCY_LABELS.items():
        prefix = "✓ " if urgency == value else ""
        urgency_row.append(
            InlineKeyboardButton(
                text=f"{prefix}{label}",
                callback_data=f"tc:urg:{value}",
            )
        )
    builder.row(*urgency_row)

    action_row: list[InlineKeyboardButton] = [
        InlineKeyboardButton(text="⏭ Пропустить", callback_data="tc:iu:skip"),
    ]
    if impact is not None and urgency is not None:
        action_row.append(
            InlineKeyboardButton(text="➡ Далее", callback_data="tc:iu:done")
        )
    builder.row(*action_row)

    builder.row(
        InlineKeyboardButton(text="⬅ Назад", callback_data="tc:back:desc"),
        InlineKeyboardButton(text="✕ Отмена", callback_data="mm:main"),
    )
    return builder.as_markup()


def confirm_kb() -> InlineKeyboardMarkup:
    """Final confirmation before ticket creation."""
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Отправить", callback_data="tc:confirm")
    builder.button(text="✏ Изменить описание", callback_data="tc:edit_desc")
    builder.button(text="✕ Отмена", callback_data="mm:main")
    builder.adjust(1)
    return builder.as_markup()

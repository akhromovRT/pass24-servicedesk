"""Settings handler — ⚙ Настройки screen in the telegram bot.

Responsibilities:
- Render toggle list for ``telegram_preferences`` (opt-out flags, default True).
- Persist toggle flips on the User row.
- Provide unlink flow with explicit confirmation.

Callback data scheme:
- ``mm:st``           → enter settings screen
- ``st:toggle:<key>`` → flip a preference
- ``st:unlink``       → show confirm dialog
- ``st:unlink_yes``   → perform unlink
"""
from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlmodel import select

from backend.auth.models import User
from backend.database import async_session_factory
from backend.telegram.services.linking import unlink_account

router = Router(name="settings")


NOTIFY_TOGGLES: list[tuple[str, str]] = [
    ("notify_comment", "💬 Ответы по заявкам"),
    ("notify_status", "📊 Изменения статуса"),
    ("notify_sla", "⚠ Предупреждения SLA"),
    ("notify_csat", "⭐ Запросы оценки"),
    ("notify_approval", "✅ Запросы на подтверждение"),
    ("notify_milestone", "🏁 Завершение фаз"),
    ("notify_risk", "🛑 Риски в проектах"),
]


def _build_settings_kb(prefs: dict) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for key, label in NOTIFY_TOGGLES:
        on = bool(prefs.get(key, True))
        kb.button(
            text=f"{'🟢' if on else '⚫'} {label}",
            callback_data=f"st:toggle:{key}",
        )
    kb.adjust(1)
    kb.row()
    kb.button(text="🔗 Отвязать аккаунт", callback_data="st:unlink")
    kb.row()
    kb.button(text="🏠 Меню", callback_data="mm:main")
    return kb.as_markup()


@router.callback_query(F.data == "mm:st")
async def cb_settings(callback: CallbackQuery, **data) -> None:
    user = data.get("user")
    if user is None or callback.message is None:
        await callback.answer()
        return
    prefs = user.telegram_preferences or {}
    linked_at = (
        user.telegram_linked_at.strftime("%d.%m.%Y")
        if user.telegram_linked_at
        else "—"
    )
    text = (
        "⚙ <b>Настройки</b>\n\n"
        f"Email: <code>{user.email}</code>\n"
        f"Привязан: с {linked_at}\n\n"
        "Уведомления:"
    )
    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=_build_settings_kb(prefs),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("st:toggle:"))
async def cb_toggle(callback: CallbackQuery, **data) -> None:
    user = data.get("user")
    if user is None or callback.message is None:
        await callback.answer()
        return
    key = callback.data.split(":", 2)[2]
    valid_keys = {k for k, _ in NOTIFY_TOGGLES}
    if key not in valid_keys:
        await callback.answer()
        return
    async with async_session_factory() as session:
        result = await session.execute(
            select(User).where(User.id == user.id)
        )
        db_user = result.scalar_one_or_none()
        if db_user is None:
            await callback.answer()
            return
        prefs = dict(db_user.telegram_preferences or {})
        prefs[key] = not bool(prefs.get(key, True))
        db_user.telegram_preferences = prefs
        session.add(db_user)
        await session.commit()
    await callback.message.edit_reply_markup(
        reply_markup=_build_settings_kb(prefs)
    )
    await callback.answer()


@router.callback_query(F.data == "st:unlink")
async def cb_unlink_confirm(callback: CallbackQuery, **data) -> None:
    if callback.message is None:
        await callback.answer()
        return
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Да, отвязать", callback_data="st:unlink_yes")
    kb.button(text="✕ Отмена", callback_data="mm:st")
    kb.adjust(2)
    await callback.message.edit_text(
        "⚠ Отвязать Telegram от аккаунта?\n\n"
        "После этого бот перестанет присылать уведомления.",
        parse_mode="HTML",
        reply_markup=kb.as_markup(),
    )
    await callback.answer()


@router.callback_query(F.data == "st:unlink_yes")
async def cb_unlink_do(callback: CallbackQuery, **data) -> None:
    user = data.get("user")
    if user is None or callback.message is None:
        await callback.answer()
        return
    await unlink_account(str(user.id))
    await callback.message.edit_text(
        "👋 До встречи! Привязать снова можно в настройках портала.",
    )
    await callback.answer()

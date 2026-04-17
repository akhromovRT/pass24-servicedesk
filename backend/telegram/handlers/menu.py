from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from backend.auth.models import UserRole
from backend.telegram.keyboards.main_menu import main_menu_kb
from backend.telegram.services.ticket_service import count_active_tickets

router = Router(name="menu")


async def show_main_menu(
    event: Message | CallbackQuery,
    user,
    state: FSMContext | None = None,
) -> None:
    """Show the main menu. Clears FSM state if provided. Edits message when possible."""
    if state is not None:
        await state.clear()
    active = await count_active_tickets(str(user.id)) if user else 0
    pending = 0
    if user and user.role == UserRole.PROPERTY_MANAGER and getattr(user, "customer_id", None):
        # Approvals count service lands in Task 12; stub as 0 for now.
        pending = 0
    text = "🏠 <b>Главное меню</b>\n\nВыберите действие:"
    kb = main_menu_kb(user, active_tickets=active, pending_approvals=pending)
    if isinstance(event, CallbackQuery):
        if event.message:
            await event.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
        await event.answer()
    else:
        await event.answer(text, parse_mode="HTML", reply_markup=kb)


@router.callback_query(F.data == "mm:main")
async def cb_main_menu(callback: CallbackQuery, state: FSMContext, **data) -> None:
    user = data.get("user")
    await show_main_menu(callback, user, state)


@router.callback_query(F.data == "noop")
async def cb_noop(callback: CallbackQuery) -> None:
    """Swallow pagination middle-button callbacks so aiogram does not log 'unhandled callback'."""
    await callback.answer()


@router.message(F.text)
async def free_text_fallback(message: Message, state: FSMContext, **data) -> None:
    """Catch-all for free text when no FSM state is active — offer action choices.

    Registered LAST in register_all_routers — other handlers with FSM state or
    commands take priority (aiogram routes top-down).
    """
    current_state = await state.get_state()
    if current_state is not None:
        # Let other routers handle text inside their FSM states.
        return
    if not data.get("is_linked"):
        # Unlinked users hit /start welcome logic instead; this path guards late arrivals.
        from backend.telegram.handlers.start import _send_welcome_unlinked
        await _send_welcome_unlinked(message)
        return
    # Save the text so Task 7 (ticket wizard) and Task 11 (AI chat) can prefill it.
    await state.update_data(pending_text=message.text or "")
    kb = InlineKeyboardBuilder()
    kb.button(text="📝 Создать заявку", callback_data="ft:ticket")
    kb.button(text="🤖 Спросить AI", callback_data="ft:ai")
    kb.button(text="📚 База знаний", callback_data="ft:kb")
    kb.button(text="🏠 Меню", callback_data="mm:main")
    kb.adjust(1)
    await message.answer(
        "💬 Что сделать с этим текстом?",
        reply_markup=kb.as_markup(),
    )


# Free-text entry points ft:ticket / ft:ai / ft:kb are routed by
# tickets_create, ai, and kb routers respectively.

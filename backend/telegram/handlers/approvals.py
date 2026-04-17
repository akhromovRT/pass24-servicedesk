"""Обработчики утверждения/отклонения фаз (PM-only)."""

from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from backend.auth.models import UserRole
from backend.database import async_session_factory
from backend.projects.services import (
    approve_phase as approve_phase_service,
    reject_phase as reject_phase_service,
)
from backend.telegram.services.project_service import resolve_approval_id

logger = logging.getLogger(__name__)

router = Router(name="approvals")


class ApprovalStates(StatesGroup):
    awaiting_reason = State()


def _is_pm(user) -> bool:
    if user is None:
        return False
    if user.role != UserRole.PROPERTY_MANAGER:
        return False
    return bool(getattr(user, "customer_id", None))


# -- Approve (без подтверждения: одно нажатие — утверждено) -----------------
# Решили не добавлять confirm-шаг для approve: отклик клика быстрее, а
# ошибочные нажатия редки. Для reject подтверждение = текст причины.


@router.callback_query(F.data.startswith("ap:approve:"))
async def cb_approve(callback: CallbackQuery, **data) -> None:
    user = data.get("user")
    if not _is_pm(user):
        await callback.answer("Только для менеджеров объекта.", show_alert=True)
        return
    short_id = callback.data.split(":", 2)[2]

    full_id = await resolve_approval_id(short_id, user.customer_id)
    if full_id is None:
        await callback.answer("Запрос не найден.", show_alert=True)
        return

    async with async_session_factory() as session:
        try:
            result = await approve_phase_service(session, full_id, str(user.id))
            await session.commit()
        except ValueError as exc:
            code = str(exc)
            msg = {
                "not_found": "Запрос не найден.",
                "not_pending": "Запрос уже обработан.",
            }.get(code, f"Не удалось: {code}")
            await callback.answer(msg, show_alert=True)
            return
        except Exception as exc:
            logger.exception("approve_phase failed")
            await callback.answer(f"Ошибка: {exc}", show_alert=True)
            return

    await callback.answer("Утверждено ✅", show_alert=False)

    # Перерисуем список approvals проекта (или общий, если проект не вытащили).
    project = result.get("project")
    if project is not None:
        from backend.telegram.handlers.projects import cb_project_approvals

        # Эмулируем клик по approvals списку проекта: подменяем callback.data,
        # чтобы переиспользовать рендер.
        callback.data = f"pr:approvals:{project.id[:8]}"
        await cb_project_approvals(callback, **data)
    else:
        from backend.telegram.handlers.projects import cb_all_pending

        callback.data = "pr:pending"
        await cb_all_pending(callback, **data)


# -- Reject (с вводом причины) ---------------------------------------------


@router.callback_query(F.data.startswith("ap:reject:"))
async def cb_reject_start(callback: CallbackQuery, state: FSMContext, **data) -> None:
    user = data.get("user")
    if not _is_pm(user):
        await callback.answer("Только для менеджеров объекта.", show_alert=True)
        return
    short_id = callback.data.split(":", 2)[2]

    full_id = await resolve_approval_id(short_id, user.customer_id)
    if full_id is None:
        await callback.answer("Запрос не найден.", show_alert=True)
        return

    await state.set_state(ApprovalStates.awaiting_reason)
    await state.update_data(reject_approval_id=full_id)

    text = (
        "❌ <b>Отклонить фазу</b>\n\n"
        "Пришлите сообщением причину отклонения — её увидит менеджер проекта. "
        "Напишите /cancel чтобы отменить."
    )
    if callback.message is not None:
        await callback.message.edit_text(text, parse_mode="HTML")
    await callback.answer()


@router.message(ApprovalStates.awaiting_reason, F.text == "/cancel")
async def msg_reject_cancel(message: Message, state: FSMContext, **data) -> None:
    await state.clear()
    await message.answer("Отмена. Запрос остался на подтверждении.")


@router.message(ApprovalStates.awaiting_reason, F.text)
async def msg_reject_reason(message: Message, state: FSMContext, **data) -> None:
    user = data.get("user")
    if not _is_pm(user):
        await state.clear()
        return
    sdata = await state.get_data()
    approval_id = sdata.get("reject_approval_id")
    reason = (message.text or "").strip()
    if not approval_id:
        await state.clear()
        await message.answer("Сессия истекла, попробуйте ещё раз.")
        return
    if not reason:
        await message.answer("Укажите причину текстом.")
        return

    async with async_session_factory() as session:
        try:
            await reject_phase_service(session, approval_id, str(user.id), reason)
            await session.commit()
        except ValueError as exc:
            code = str(exc)
            msg = {
                "not_found": "Запрос не найден.",
                "not_pending": "Запрос уже обработан.",
                "empty_reason": "Укажите причину текстом.",
            }.get(code, f"Не удалось: {code}")
            await message.answer(msg)
            if code != "empty_reason":
                await state.clear()
            return
        except Exception as exc:
            logger.exception("reject_phase failed")
            await state.clear()
            await message.answer(f"Ошибка: {exc}")
            return

    await state.clear()
    await message.answer("Фаза отклонена. Комментарий отправлен менеджеру.")

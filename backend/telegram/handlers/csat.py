from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from backend.telegram.services.ticket_service import (
    rate_csat,
    resolve_ticket_by_short_id,
)

logger = logging.getLogger(__name__)

router = Router(name="csat")


class CsatStates(StatesGroup):
    """Only used when rating <= 3 — we prompt for a free-form improvement comment."""

    awaiting_comment = State()


def _result_kb(short_id: str | None) -> InlineKeyboardBuilder:
    kb = InlineKeyboardBuilder()
    if short_id:
        kb.button(text="📋 Заявка", callback_data=f"tl:open:{short_id}")
    kb.button(text="🏠 Меню", callback_data="mm:main")
    kb.adjust(2 if short_id else 1)
    return kb


# --- Entry: show star picker --------------------------------------------


@router.callback_query(F.data.startswith("tl:csat:"))
async def cb_csat_start(callback: CallbackQuery, **data) -> None:
    short_id = callback.data.split(":", 2)[2] if callback.data else ""
    kb = InlineKeyboardBuilder()
    for n in range(1, 6):
        kb.button(text="⭐" * n, callback_data=f"csat:rate:{short_id}:{n}")
    kb.adjust(5)
    kb.row()
    kb.button(text="⬅ Назад", callback_data=f"tl:open:{short_id}")
    if callback.message is not None:
        try:
            await callback.message.edit_text(
                "⭐ <b>Оцените решение</b>\n\nНасколько вы довольны результатом?",
                parse_mode="HTML",
                reply_markup=kb.as_markup(),
            )
        except TelegramBadRequest as exc:
            logger.debug("csat prompt edit skipped: %s", exc)
    await callback.answer()


# --- Rate pick ----------------------------------------------------------


@router.callback_query(F.data.startswith("csat:rate:"))
async def cb_csat_rate(callback: CallbackQuery, state: FSMContext, **data) -> None:
    parts = (callback.data or "").split(":", 3)
    if len(parts) != 4:
        await callback.answer()
        return
    short_id = parts[2]
    try:
        rating = int(parts[3])
    except ValueError:
        await callback.answer()
        return
    user = data.get("user")
    if user is None:
        await callback.answer("Нужна авторизация.", show_alert=True)
        return

    ticket = await resolve_ticket_by_short_id(short_id, str(user.id))
    if ticket is None:
        await callback.answer("Заявка не найдена.", show_alert=True)
        return

    # rating >= 4 — submit immediately, no free-form comment prompt.
    if rating >= 4:
        try:
            await rate_csat(ticket.id, user, rating)
        except ValueError as exc:
            logger.warning("rate_csat failed (%s): %s", short_id, exc)
            await callback.answer("Не удалось сохранить оценку.", show_alert=True)
            return
        except Exception as exc:
            logger.exception("rate_csat crashed for ticket=%s: %s", short_id, exc)
            await callback.answer("Не удалось сохранить оценку.", show_alert=True)
            return

        kb = _result_kb(short_id)
        if callback.message is not None:
            try:
                await callback.message.edit_text(
                    f"✅ Спасибо! Ваша оценка: {'⭐' * rating}",
                    reply_markup=kb.as_markup(),
                )
            except TelegramBadRequest as exc:
                logger.debug("csat result edit skipped: %s", exc)
        await callback.answer()
        return

    # rating <= 3 — ask for improvement comment; persist on text or skip.
    await state.set_state(CsatStates.awaiting_comment)
    await state.update_data(
        csat_ticket_id=ticket.id,
        csat_short_id=short_id,
        csat_rating=rating,
    )
    kb = InlineKeyboardBuilder()
    kb.button(text="⏭ Пропустить", callback_data=f"csat:skip:{short_id}")
    kb.adjust(1)
    if callback.message is not None:
        try:
            await callback.message.edit_text(
                f"{'⭐' * rating}\n\n"
                "Расскажите, что можно улучшить? (или нажмите «Пропустить»)",
                reply_markup=kb.as_markup(),
            )
        except TelegramBadRequest as exc:
            logger.debug("csat comment prompt edit skipped: %s", exc)
    await callback.answer()


# --- Optional free-form comment -----------------------------------------


@router.message(CsatStates.awaiting_comment, F.text)
async def msg_csat_comment(message: Message, state: FSMContext, **data) -> None:
    sdata = await state.get_data()
    user = data.get("user")
    short_id = sdata.get("csat_short_id")
    ticket_id = sdata.get("csat_ticket_id")
    rating = sdata.get("csat_rating")

    if user is None or not ticket_id or not isinstance(rating, int):
        await message.answer("Сессия истекла. Откройте заявку заново.")
        await state.clear()
        return

    try:
        await rate_csat(ticket_id, user, rating, comment=(message.text or "").strip() or None)
    except ValueError as exc:
        logger.warning("rate_csat (with comment) failed for ticket=%s: %s", short_id, exc)
        await message.answer("Не удалось сохранить оценку. Попробуйте позже.")
        await state.clear()
        return
    except Exception as exc:
        logger.exception("rate_csat (with comment) crashed for ticket=%s: %s", short_id, exc)
        await message.answer("Не удалось сохранить оценку. Попробуйте позже.")
        await state.clear()
        return

    await state.clear()
    kb = _result_kb(short_id)
    await message.answer("✅ Спасибо за отзыв!", reply_markup=kb.as_markup())


@router.callback_query(F.data.startswith("csat:skip:"))
async def cb_csat_skip(callback: CallbackQuery, state: FSMContext, **data) -> None:
    sdata = await state.get_data()
    user = data.get("user")
    short_id = sdata.get("csat_short_id") or (
        (callback.data or "").split(":", 2)[2] if callback.data else None
    )
    ticket_id = sdata.get("csat_ticket_id")
    rating = sdata.get("csat_rating")

    if user is None or not ticket_id or not isinstance(rating, int):
        # Session expired or data lost — nothing useful to do, just bail out.
        await state.clear()
        await callback.answer("Сессия истекла.", show_alert=False)
        return

    try:
        await rate_csat(ticket_id, user, rating)
    except Exception as exc:  # skip must always feel fast; only log + continue
        logger.warning("rate_csat (skip) failed for ticket=%s: %s", short_id, exc)

    await state.clear()
    kb = _result_kb(short_id)
    if callback.message is not None:
        try:
            await callback.message.edit_text(
                f"✅ Спасибо! Ваша оценка: {'⭐' * rating}",
                reply_markup=kb.as_markup(),
            )
        except TelegramBadRequest as exc:
            logger.debug("csat skip edit skipped: %s", exc)
    await callback.answer()

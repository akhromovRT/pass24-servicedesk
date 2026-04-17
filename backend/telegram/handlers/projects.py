"""PM workspace в Telegram: список проектов, карточка, фазы/риски/approvals."""

from __future__ import annotations

import logging
from datetime import date, datetime

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from backend.auth.models import UserRole
from backend.telegram.formatters import escape_html
from backend.telegram.keyboards.projects import (
    PHASE_STATUS_EMOJI,
    PHASE_STATUS_LABEL,
    PROJECT_STATUS_EMOJI,
    PROJECT_STATUS_LABEL,
    RISK_SEVERITY_EMOJI,
    approvals_list_kb,
    project_card_kb,
    projects_list_kb,
)
from backend.telegram.services.project_service import (
    get_project_summary,
    list_pending_approvals,
    list_user_projects,
    pending_approvals_count,
)

logger = logging.getLogger(__name__)

router = Router(name="projects")


def _is_pm(user) -> bool:
    if user is None:
        return False
    if user.role != UserRole.PROPERTY_MANAGER:
        return False
    return bool(getattr(user, "customer_id", None))


def _fmt_date(value) -> str:
    if value is None:
        return "—"
    if isinstance(value, (date, datetime)):
        return value.strftime("%d.%m.%Y")
    return str(value)


def _progress_bar(percent: int, width: int = 10) -> str:
    percent = max(0, min(100, int(percent or 0)))
    filled = round(width * percent / 100)
    return "▓" * filled + "░" * (width - filled)


# -- Projects list ----------------------------------------------------------


@router.callback_query(F.data == "mm:pr")
async def cb_projects_list(callback: CallbackQuery, state: FSMContext, **data) -> None:
    user = data.get("user")
    if not _is_pm(user):
        await callback.answer("Только для менеджеров объекта.", show_alert=True)
        return
    await state.clear()
    projects = await list_user_projects(user.customer_id)
    pending = await pending_approvals_count(user.customer_id)

    if not projects:
        text = (
            "🏗 <b>Мои проекты</b>\n\n"
            "Пока нет активных проектов внедрения. "
            "Когда PASS24 создаст проект для вашего объекта, он появится здесь."
        )
    else:
        lines = ["🏗 <b>Мои проекты</b>", ""]
        for p in projects:
            status = p["status"]
            emoji = PROJECT_STATUS_EMOJI.get(status, "📁")
            status_label = PROJECT_STATUS_LABEL.get(status, status)
            code = escape_html(p["code"])
            name = escape_html(p["name"])[:60]
            progress = p["progress_percent"]
            lines.append(
                f"{emoji} <b>{code}</b> — {name}\n"
                f"   <i>{status_label}</i> · прогресс {progress}%"
            )
            lines.append("")
        if pending:
            lines.append(f"⏳ На подтверждении: <b>{pending}</b>")
        text = "\n".join(lines).rstrip()

    kb = projects_list_kb(projects, pending_approvals=pending)
    if callback.message is not None:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    await callback.answer()


# -- Project card -----------------------------------------------------------


@router.callback_query(F.data.startswith("pr:open:"))
async def cb_project_card(callback: CallbackQuery, **data) -> None:
    user = data.get("user")
    if not _is_pm(user):
        await callback.answer("Только для менеджеров объекта.", show_alert=True)
        return
    short_id = callback.data.split(":", 2)[2]
    project = await get_project_summary(short_id, user.customer_id)
    if project is None:
        await callback.answer("Проект не найден.", show_alert=True)
        return

    await _render_project_card(callback, project)


async def _render_project_card(callback: CallbackQuery, project: dict) -> None:
    short_id = project["id"][:8]

    # Счётчик pending approvals для этого проекта.
    approvals = await _approvals_for_project(
        project["customer_id"], project["id"]
    )
    pending = len(approvals)

    status = project["status"]
    emoji = PROJECT_STATUS_EMOJI.get(status, "📁")
    status_label = PROJECT_STATUS_LABEL.get(status, status)
    progress = project["progress_percent"]
    bar = _progress_bar(progress)

    current_phase = project.get("current_phase")
    current_phase_line = "—"
    if current_phase:
        current_phase_line = escape_html(current_phase.get("name") or "—")

    lines = [
        f"{emoji} <b>{escape_html(project['code'])}</b> — {escape_html(project['name'])}",
        "",
        f"<b>Статус:</b> {status_label}",
        f"<b>Объект:</b> {escape_html(project.get('object_name') or '—')}",
        f"<b>Текущая фаза:</b> {current_phase_line}",
        f"<b>Прогресс:</b> {bar} {progress}%",
        f"<b>Старт:</b> {_fmt_date(project.get('started_at'))}  "
        f"<b>План завершения:</b> {_fmt_date(project.get('target_end_date'))}",
    ]

    phases = project.get("phases") or []
    if phases:
        lines.append("")
        lines.append("<b>Фазы:</b>")
        for ph in phases[:8]:
            ph_emoji = PHASE_STATUS_EMOJI.get(ph["status"], "•")
            lines.append(f"  {ph_emoji} {escape_html(ph['name'])}")
        if len(phases) > 8:
            lines.append(f"  …и ещё {len(phases) - 8}")

    risks = project.get("risks") or []
    if risks:
        lines.append("")
        lines.append(f"<b>Активные риски ({len(risks)}):</b>")
        for r in risks[:3]:
            r_emoji = RISK_SEVERITY_EMOJI.get(r["severity"], "⚠")
            lines.append(f"  {r_emoji} {escape_html(r['title'])}")
        if len(risks) > 3:
            lines.append(f"  …и ещё {len(risks) - 3}")

    if pending:
        lines.append("")
        lines.append(f"✅ <b>На подтверждении: {pending}</b>")

    text = "\n".join(lines)
    kb = project_card_kb(short_id, pending_approvals=pending)
    if callback.message is not None:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    await callback.answer()


# -- Detailed phases view --------------------------------------------------


@router.callback_query(F.data.startswith("pr:phases:"))
async def cb_project_phases(callback: CallbackQuery, **data) -> None:
    user = data.get("user")
    if not _is_pm(user):
        await callback.answer()
        return
    short_id = callback.data.split(":", 2)[2]
    project = await get_project_summary(short_id, user.customer_id)
    if project is None:
        await callback.answer("Проект не найден.", show_alert=True)
        return

    phases = project.get("phases") or []
    lines = [
        f"🏗 <b>Фазы проекта {escape_html(project['code'])}</b>",
        "",
    ]
    if not phases:
        lines.append("<i>Фазы ещё не созданы.</i>")
    else:
        for ph in phases:
            ph_emoji = PHASE_STATUS_EMOJI.get(ph["status"], "•")
            ph_label = PHASE_STATUS_LABEL.get(ph["status"], ph["status"])
            planned = (
                f" · {_fmt_date(ph.get('planned_start'))} → {_fmt_date(ph.get('planned_end'))}"
                if ph.get("planned_start") or ph.get("planned_end")
                else ""
            )
            lines.append(
                f"{ph_emoji} <b>{ph['order']}. {escape_html(ph['name'])}</b>\n"
                f"   <i>{ph_label}</i>{planned}"
            )
    text = "\n".join(lines)

    approvals = await _approvals_for_project(user.customer_id, project["id"])
    kb = project_card_kb(short_id, pending_approvals=len(approvals))
    if callback.message is not None:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    await callback.answer()


# -- Detailed risks view ---------------------------------------------------


@router.callback_query(F.data.startswith("pr:risks:"))
async def cb_project_risks(callback: CallbackQuery, **data) -> None:
    user = data.get("user")
    if not _is_pm(user):
        await callback.answer()
        return
    short_id = callback.data.split(":", 2)[2]
    project = await get_project_summary(short_id, user.customer_id)
    if project is None:
        await callback.answer("Проект не найден.", show_alert=True)
        return

    risks = project.get("risks") or []
    lines = [
        f"⚠ <b>Риски проекта {escape_html(project['code'])}</b>",
        "",
    ]
    if not risks:
        lines.append("<i>Активных рисков нет.</i>")
    else:
        for r in risks:
            r_emoji = RISK_SEVERITY_EMOJI.get(r["severity"], "⚠")
            title = escape_html(r.get("title") or "—")
            descr = escape_html((r.get("description") or "")[:200])
            lines.append(f"{r_emoji} <b>{title}</b>")
            if descr:
                lines.append(f"   {descr}")

    text = "\n".join(lines)

    approvals = await _approvals_for_project(user.customer_id, project["id"])
    kb = project_card_kb(short_id, pending_approvals=len(approvals))
    if callback.message is not None:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    await callback.answer()


# -- Approvals filtered by project -----------------------------------------


@router.callback_query(F.data.startswith("pr:approvals:"))
async def cb_project_approvals(callback: CallbackQuery, **data) -> None:
    user = data.get("user")
    if not _is_pm(user):
        await callback.answer()
        return
    short_id = callback.data.split(":", 2)[2]
    project = await get_project_summary(short_id, user.customer_id)
    if project is None:
        await callback.answer("Проект не найден.", show_alert=True)
        return

    approvals = await _approvals_for_project(user.customer_id, project["id"])
    await _render_approvals_list(
        callback,
        approvals,
        header=f"✅ <b>На подтверждении — {escape_html(project['code'])}</b>",
        back_callback=f"pr:open:{short_id}",
    )


@router.callback_query(F.data == "pr:pending")
async def cb_all_pending(callback: CallbackQuery, **data) -> None:
    """Pending approvals по всем проектам PM (из списка проектов)."""
    user = data.get("user")
    if not _is_pm(user):
        await callback.answer()
        return
    approvals = await list_pending_approvals(user.customer_id)
    await _render_approvals_list(
        callback,
        approvals,
        header="✅ <b>На подтверждении</b>",
        back_callback="mm:pr",
    )


# -- Helpers ----------------------------------------------------------------


async def _approvals_for_project(customer_id: str, project_id: str) -> list[dict]:
    all_approvals = await list_pending_approvals(customer_id)
    return [a for a in all_approvals if a["project_id"] == project_id]


async def _render_approvals_list(
    callback: CallbackQuery,
    approvals: list[dict],
    *,
    header: str,
    back_callback: str,
) -> None:
    if not approvals:
        text = f"{header}\n\n<i>Нет запросов на подтверждение.</i>"
    else:
        lines = [header, ""]
        for a in approvals:
            code = escape_html(a.get("project_code") or "")
            phase = escape_html(a.get("phase_name") or "—")
            when = a["requested_at"].strftime("%d.%m.%Y") if a.get("requested_at") else ""
            lines.append(f"• <b>{code}</b> — фаза «{phase}» <i>({when})</i>")
        text = "\n".join(lines)

    kb = approvals_list_kb(approvals, back_callback=back_callback)
    if callback.message is not None:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    await callback.answer()

"""Inline-клавиатуры для PM workspace (проекты + approvals)."""

from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


PROJECT_STATUS_EMOJI: dict[str, str] = {
    "draft": "📝",
    "planning": "📋",
    "in_progress": "🏗",
    "on_hold": "⏸",
    "completed": "✅",
    "cancelled": "❌",
}

PROJECT_STATUS_LABEL: dict[str, str] = {
    "draft": "Черновик",
    "planning": "Планирование",
    "in_progress": "В работе",
    "on_hold": "Пауза",
    "completed": "Завершён",
    "cancelled": "Отменён",
}

PHASE_STATUS_EMOJI: dict[str, str] = {
    "pending": "⏳",
    "in_progress": "🏗",
    "completed": "✅",
    "blocked": "🚫",
    "skipped": "⏭",
}

PHASE_STATUS_LABEL: dict[str, str] = {
    "pending": "Ожидает",
    "in_progress": "В работе",
    "completed": "Завершена",
    "blocked": "Блок",
    "skipped": "Пропущена",
}

RISK_SEVERITY_EMOJI: dict[str, str] = {
    "low": "🟢",
    "medium": "🟡",
    "high": "🟠",
    "critical": "🔴",
}


def _short(project_id: str) -> str:
    return (project_id or "")[:8]


def projects_list_kb(projects: list[dict], *, pending_approvals: int = 0) -> InlineKeyboardMarkup:
    """Кнопка на проект: эмодзи статуса + code. Внизу — pending + меню."""
    kb = InlineKeyboardBuilder()

    for p in projects:
        status = p.get("status") or ""
        emoji = PROJECT_STATUS_EMOJI.get(status, "📁")
        code = p.get("code") or "?"
        short = _short(p.get("id", ""))
        kb.button(text=f"{emoji} {code}", callback_data=f"pr:open:{short}")
    kb.adjust(1)

    if pending_approvals > 0:
        kb.row(
            InlineKeyboardButton(
                text=f"✅ На подтверждении • {pending_approvals}",
                callback_data="pr:pending",
            )
        )

    kb.row(InlineKeyboardButton(text="🏠 Меню", callback_data="mm:main"))
    return kb.as_markup()


def project_card_kb(
    project_id_short: str, *, pending_approvals: int = 0
) -> InlineKeyboardMarkup:
    """[🏗 Фазы] [⚠ Риски] / [✅ На подтверждении (N)] / [⬅ К списку] [🏠 Меню]."""
    kb = InlineKeyboardBuilder()
    kb.button(text="🏗 Фазы", callback_data=f"pr:phases:{project_id_short}")
    kb.button(text="⚠ Риски", callback_data=f"pr:risks:{project_id_short}")
    kb.adjust(2)

    if pending_approvals > 0:
        kb.row(
            InlineKeyboardButton(
                text=f"✅ На подтверждении • {pending_approvals}",
                callback_data=f"pr:approvals:{project_id_short}",
            )
        )

    kb.row(
        InlineKeyboardButton(text="⬅ К списку", callback_data="mm:pr"),
        InlineKeyboardButton(text="🏠 Меню", callback_data="mm:main"),
    )
    return kb.as_markup()


def approvals_list_kb(
    approvals: list[dict], *, back_callback: str = "mm:pr"
) -> InlineKeyboardMarkup:
    """Список approvals: по 2 кнопки (утвердить/отклонить) на каждый."""
    kb = InlineKeyboardBuilder()
    for a in approvals:
        approval_id = a["approval_id"]
        short = approval_id[:16]
        phase_name = (a.get("phase_name") or "?")[:24]
        kb.row(
            InlineKeyboardButton(
                text=f"✅ {phase_name}",
                callback_data=f"ap:approve:{short}",
            ),
            InlineKeyboardButton(
                text="❌",
                callback_data=f"ap:reject:{short}",
            ),
        )
    kb.row(
        InlineKeyboardButton(text="⬅ Назад", callback_data=back_callback),
        InlineKeyboardButton(text="🏠 Меню", callback_data="mm:main"),
    )
    return kb.as_markup()


def approval_confirm_reject_kb(
    approval_short: str, *, project_short: str | None = None
) -> InlineKeyboardMarkup:
    """Во время отмены ввода причины — только «Отмена»."""
    kb = InlineKeyboardBuilder()
    back_cb = f"pr:approvals:{project_short}" if project_short else "mm:pr"
    kb.button(text="✕ Отмена", callback_data=back_cb)
    kb.adjust(1)
    return kb.as_markup()

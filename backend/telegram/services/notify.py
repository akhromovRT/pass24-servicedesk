"""Outbound notification service for Telegram bot v2.

Self-contained: talks to the Telegram Bot API over HTTP directly (no aiogram
``Bot`` singleton) so it can be called from any FastAPI endpoint or background
task without worrying about dispatcher context.

Failure policy:
- ``_tg_send_with_retry`` NEVER raises to the caller.
- 403 (user blocked the bot) → best-effort auto-unlink (clear
  ``User.telegram_chat_id``) and return False.
- 429 (rate-limited) → sleep for ``retry_after`` and retry within the same
  attempt budget.
- Other errors → log + exponential backoff, return False after ``max_attempts``.

Per-user preferences live in ``User.telegram_preferences`` (JSON dict). Missing
keys default to ``True`` (opt-out, not opt-in).
"""
from __future__ import annotations

import asyncio
import html
import logging
from pathlib import Path

import httpx

from backend.config import settings

logger = logging.getLogger(__name__)

_TG_API = (getattr(settings, "telegram_api_base", "") or "https://api.telegram.org").rstrip("/")


# ---------- Low-level send helpers ----------


async def _tg_send_with_retry(
    method: str,
    payload: dict,
    *,
    files: dict | None = None,
    max_attempts: int = 3,
) -> bool:
    """POST to TG Bot API with exponential backoff. Auto-unlinks on 403.

    Returns True on success, False on final failure. Never raises.
    """
    token = getattr(settings, "telegram_bot_token", None) or ""
    if not token:
        return False
    url = f"{_TG_API}/bot{token}/{method}"
    delay = 1.0
    for attempt in range(1, max_attempts + 1):
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                if files:
                    r = await client.post(url, data=payload, files=files)
                else:
                    r = await client.post(url, json=payload)
            if r.status_code == 200:
                return True
            if r.status_code == 403:
                chat_id = payload.get("chat_id")
                if chat_id:
                    try:
                        await _auto_unlink_on_403(int(chat_id))
                    except Exception as exc:  # noqa: BLE001
                        logger.warning("auto-unlink failed for %s: %s", chat_id, exc)
                return False
            if r.status_code == 429:
                try:
                    retry_after = r.json().get("parameters", {}).get("retry_after", delay)
                except Exception:  # noqa: BLE001
                    retry_after = delay
                await asyncio.sleep(max(delay, float(retry_after)))
                continue
            logger.warning("TG %s -> %s: %s", method, r.status_code, r.text[:200])
        except httpx.HTTPError as exc:
            logger.warning("TG %s attempt %s failed: %s", method, attempt, exc)
        except Exception as exc:  # noqa: BLE001 — must never raise
            logger.warning("TG %s attempt %s unexpected error: %s", method, attempt, exc)
        await asyncio.sleep(delay)
        delay *= 2
    return False


async def _tg_send_message(
    chat_id: int,
    text: str,
    *,
    reply_markup: dict | None = None,
    parse_mode: str = "HTML",
    disable_preview: bool = True,
) -> bool:
    payload: dict = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": disable_preview,
    }
    if reply_markup is not None:
        payload["reply_markup"] = reply_markup
    return await _tg_send_with_retry("sendMessage", payload)


async def _tg_send_document(
    chat_id: int,
    file_path: str | Path,
    caption: str = "",
) -> bool:
    p = Path(file_path)
    if not p.exists():
        return False
    try:
        data = p.read_bytes()
    except OSError as exc:
        logger.warning("TG sendDocument: cannot read %s: %s", p, exc)
        return False
    return await _tg_send_with_retry(
        "sendDocument",
        {"chat_id": chat_id, "caption": caption, "parse_mode": "HTML"},
        files={"document": (p.name, data)},
    )


async def _auto_unlink_on_403(chat_id: int) -> None:
    """User blocked the bot — clear their telegram_chat_id so we stop trying."""
    from sqlmodel import select

    from backend.auth.models import User
    from backend.database import async_session_factory

    async with async_session_factory() as session:
        result = await session.execute(
            select(User).where(User.telegram_chat_id == chat_id)
        )
        user = result.scalar_one_or_none()
        if user is not None:
            user.telegram_chat_id = None
            user.telegram_linked_at = None
            session.add(user)
            await session.commit()
            logger.info("Auto-unlinked chat_id=%s after 403.", chat_id)


async def _check_preferences(user, pref_key: str) -> bool:
    """Return True when the given pref is enabled (missing key defaults True)."""
    prefs = getattr(user, "telegram_preferences", None) or {}
    return bool(prefs.get(pref_key, True))


# ---------- Inline keyboard helper ----------


def _ikb(rows: list[list[dict]]) -> dict:
    """Build raw Bot API inline keyboard markup dict."""
    return {"inline_keyboard": rows}


# ---------- Notification payloads ----------


async def notify_telegram_comment(
    chat_id: int,
    ticket_id: str,
    ticket_title: str,
    comment_text: str,
    author_name: str,
    attachment_paths: list[str] | None = None,
    *,
    user=None,
) -> None:
    """Notify user about a new public comment on their ticket."""
    if user is not None and not await _check_preferences(user, "notify_comment"):
        return
    short = (ticket_id or "")[:8]
    text = (
        f"💬 <b>Новый ответ по заявке #{short}</b>\n"
        f"<i>{html.escape((ticket_title or '')[:120])}</i>\n\n"
        f"<b>{html.escape(author_name or '')}:</b>\n"
        f"{html.escape((comment_text or '')[:1500])}"
    )
    markup = _ikb([[
        {"text": "💬 Ответить", "callback_data": f"tl:reply:{short}"},
        {"text": "📋 Открыть", "callback_data": f"tl:open:{short}"},
    ]])
    await _tg_send_message(chat_id, text, reply_markup=markup)
    for p in attachment_paths or []:
        await _tg_send_document(chat_id, p)


async def notify_telegram_status(
    chat_id: int,
    ticket_id: str,
    ticket_title: str,
    old_status: str,
    new_status: str,
    *,
    user=None,
) -> None:
    """Notify on ticket status transition. Adds CSAT inline buttons on resolve."""
    if user is not None and not await _check_preferences(user, "notify_status"):
        return
    short = (ticket_id or "")[:8]
    # Local import to avoid circular imports via formatters -> models.
    from backend.telegram.formatters import STATUS_EMOJI, STATUS_LABEL_RU

    old_label = STATUS_LABEL_RU.get(old_status, old_status)
    new_label = STATUS_LABEL_RU.get(new_status, new_status)
    emoji = STATUS_EMOJI.get(new_status, "")
    prefix = f"{emoji} " if emoji else ""
    text = (
        f"{prefix}<b>Статус заявки #{short}</b>\n"
        f"<i>{html.escape((ticket_title or '')[:120])}</i>\n\n"
        f"{html.escape(str(old_label))} → <b>{html.escape(str(new_label))}</b>"
    )
    buttons: list[list[dict]] = [
        [{"text": "📋 Открыть", "callback_data": f"tl:open:{short}"}]
    ]
    if new_status == "resolved":
        buttons.insert(
            0,
            [
                {"text": "⭐", "callback_data": f"csat:rate:{short}:1"},
                {"text": "⭐⭐", "callback_data": f"csat:rate:{short}:2"},
                {"text": "⭐⭐⭐", "callback_data": f"csat:rate:{short}:3"},
                {"text": "⭐⭐⭐⭐", "callback_data": f"csat:rate:{short}:4"},
                {"text": "⭐⭐⭐⭐⭐", "callback_data": f"csat:rate:{short}:5"},
            ],
        )
    await _tg_send_message(chat_id, text, reply_markup=_ikb(buttons))


async def notify_telegram_sla_warning(
    chat_id: int,
    ticket_id: str,
    ticket_title: str,
    deadline,
    *,
    user=None,
) -> None:
    """SLA breach is imminent — warn the user."""
    if user is not None and not await _check_preferences(user, "notify_sla"):
        return
    short = (ticket_id or "")[:8]
    dt_str = (
        deadline.strftime("%d.%m %H:%M")
        if hasattr(deadline, "strftime")
        else str(deadline)
    )
    text = (
        f"⚠ <b>Скоро дедлайн по заявке #{short}</b>\n"
        f"<i>{html.escape((ticket_title or '')[:120])}</i>\n\n"
        f"До срока: {html.escape(dt_str)}"
    )
    await _tg_send_message(
        chat_id,
        text,
        reply_markup=_ikb(
            [[{"text": "📋 Открыть", "callback_data": f"tl:open:{short}"}]]
        ),
    )


async def notify_telegram_csat_request(
    chat_id: int,
    ticket_id: str,
    ticket_title: str,
    *,
    user=None,
) -> None:
    """Ask user for CSAT rating (explicit request, e.g. 24h after resolve)."""
    if user is not None and not await _check_preferences(user, "notify_csat"):
        return
    short = (ticket_id or "")[:8]
    text = (
        f"⭐ <b>Оцените решение заявки #{short}</b>\n"
        f"<i>{html.escape((ticket_title or '')[:120])}</i>"
    )
    buttons = [[
        {"text": "⭐" * n, "callback_data": f"csat:rate:{short}:{n}"}
        for n in range(1, 6)
    ]]
    await _tg_send_message(chat_id, text, reply_markup=_ikb(buttons))


async def notify_telegram_approval_request(
    chat_id: int,
    approval_id: str,
    project_name: str,
    phase_name: str,
    *,
    user=None,
) -> None:
    """Ask user to approve/reject a project phase."""
    if user is not None and not await _check_preferences(user, "notify_approval"):
        return
    short_ap = (approval_id or "")[:16]
    text = (
        f"✅ <b>Требуется подтверждение фазы</b>\n\n"
        f"Проект: <b>{html.escape(project_name or '')}</b>\n"
        f"Фаза: <b>{html.escape(phase_name or '')}</b>"
    )
    markup = _ikb([[
        {"text": "✅ Утвердить", "callback_data": f"ap:approve:{short_ap}"},
        {"text": "❌ Отклонить", "callback_data": f"ap:reject:{short_ap}"},
    ]])
    await _tg_send_message(chat_id, text, reply_markup=markup)


async def notify_telegram_milestone(
    chat_id: int,
    project_name: str,
    phase_name: str,
    *,
    user=None,
) -> None:
    """Inform the user that a project phase completed."""
    if user is not None and not await _check_preferences(user, "notify_milestone"):
        return
    text = (
        f"🏁 <b>Завершена фаза</b>\n\n"
        f"Проект: <b>{html.escape(project_name or '')}</b>\n"
        f"Фаза: <b>{html.escape(phase_name or '')}</b>"
    )
    await _tg_send_message(chat_id, text)


async def notify_telegram_risk(
    chat_id: int,
    project_name: str,
    risk_description: str,
    severity: str,
    *,
    user=None,
) -> None:
    """Inform the user about a new project risk."""
    if user is not None and not await _check_preferences(user, "notify_risk"):
        return
    sev_emoji = {
        "critical": "🔴",
        "high": "🟠",
        "medium": "🟡",
        "low": "🟢",
    }.get(severity, "⚪")
    text = (
        f"{sev_emoji} <b>Риск в проекте</b>\n\n"
        f"Проект: <b>{html.escape(project_name or '')}</b>\n"
        f"Описание: {html.escape((risk_description or '')[:500])}"
    )
    await _tg_send_message(chat_id, text)


# ---------- PM wrappers: look up the project's PM and route to the right notify ----------


async def _get_linked_pm(project_id: str):
    """Return the linked PM user for a project, or None if not linked / missing."""
    from sqlmodel import select
    from backend.auth.models import User
    from backend.database import async_session_factory
    from backend.projects.models import ImplementationProject

    async with async_session_factory() as session:
        project = await session.get(ImplementationProject, project_id)
        if project is None or not project.customer_id:
            return None
        user = await session.get(User, project.customer_id)
        if user is None or not user.telegram_chat_id:
            return None
        return user


async def notify_pm_approval_request(
    project_id: str,
    approval_id: str,
    project_name: str,
    phase_name: str,
) -> None:
    """Notify the project's PM about a new pending approval via Telegram."""
    try:
        user = await _get_linked_pm(project_id)
        if user is None:
            return
        await notify_telegram_approval_request(
            chat_id=user.telegram_chat_id,
            approval_id=approval_id,
            project_name=project_name,
            phase_name=phase_name,
            user=user,
        )
    except Exception:  # noqa: BLE001 — notifications must never break callers
        logger.exception("notify_pm_approval_request failed for project %s", project_id)


async def notify_pm_milestone(
    project_id: str,
    project_name: str,
    phase_name: str,
) -> None:
    """Notify the PM that a phase was completed."""
    try:
        user = await _get_linked_pm(project_id)
        if user is None:
            return
        await notify_telegram_milestone(
            chat_id=user.telegram_chat_id,
            project_name=project_name,
            phase_name=phase_name,
            user=user,
        )
    except Exception:  # noqa: BLE001
        logger.exception("notify_pm_milestone failed for project %s", project_id)


async def notify_pm_risk(
    project_id: str,
    project_name: str,
    risk_description: str,
    severity: str,
) -> None:
    """Notify the PM about a newly created project risk."""
    try:
        user = await _get_linked_pm(project_id)
        if user is None:
            return
        await notify_telegram_risk(
            chat_id=user.telegram_chat_id,
            project_name=project_name,
            risk_description=risk_description,
            severity=severity,
            user=user,
        )
    except Exception:  # noqa: BLE001
        logger.exception("notify_pm_risk failed for project %s", project_id)

from __future__ import annotations

import html
from typing import Any

from backend.tickets.models import Ticket, TicketPriority, TicketStatus

STATUS_EMOJI: dict[str, str] = {
    TicketStatus.NEW.value: "🔵",
    TicketStatus.IN_PROGRESS.value: "🟡",
    TicketStatus.WAITING_FOR_USER.value: "🟠",
    TicketStatus.ON_HOLD.value: "⏸",
    TicketStatus.ENGINEER_VISIT.value: "🔧",
    TicketStatus.RESOLVED.value: "✅",
    TicketStatus.CLOSED.value: "⚫",
}

PRIORITY_EMOJI: dict[str, str] = {
    TicketPriority.CRITICAL.value: "🔴",
    TicketPriority.HIGH.value: "🟠",
    TicketPriority.NORMAL.value: "🔵",
    TicketPriority.LOW.value: "🟢",
}

STATUS_LABEL_RU: dict[str, str] = {
    TicketStatus.NEW.value: "Новая",
    TicketStatus.IN_PROGRESS.value: "В работе",
    TicketStatus.WAITING_FOR_USER.value: "Ждёт ответа",
    TicketStatus.ON_HOLD.value: "Приостановлена",
    TicketStatus.ENGINEER_VISIT.value: "Визит инженера",
    TicketStatus.RESOLVED.value: "Решена",
    TicketStatus.CLOSED.value: "Закрыта",
}

_LIST_TITLE_LIMIT = 60
_ARTICLE_BODY_LIMIT = 4000


def escape_html(text: str | None) -> str:
    """Escape &, <, > for Telegram HTML parse_mode. Quotes are left as-is."""
    return html.escape(text or "", quote=False)


def _short_id(ticket_id: str) -> str:
    return (ticket_id or "")[:8]


def _status_value(ticket: Ticket) -> str:
    value = ticket.status
    return value.value if hasattr(value, "value") else str(value or "")


def _priority_value(ticket: Ticket) -> str:
    value = ticket.priority
    return value.value if hasattr(value, "value") else str(value or "")


def format_ticket_list_item(ticket: Ticket) -> str:
    """Compact one-liner for ticket lists (e.g. 🔵 #abcd1234 — Title)."""
    status = _status_value(ticket)
    emoji = STATUS_EMOJI.get(status, "")
    title = ticket.title or ""
    if len(title) > _LIST_TITLE_LIMIT:
        title = title[: _LIST_TITLE_LIMIT - 1].rstrip() + "…"
    short_id = _short_id(ticket.id)
    prefix = f"{emoji} " if emoji else ""
    return f"{prefix}#{short_id} — {title}".rstrip(" —")


def format_ticket_card(ticket: Ticket) -> str:
    """Telegram HTML card for a single ticket (parse_mode=HTML)."""
    status = _status_value(ticket)
    priority = _priority_value(ticket)
    status_emoji = STATUS_EMOJI.get(status, "")
    priority_emoji = PRIORITY_EMOJI.get(priority, "")
    status_label = STATUS_LABEL_RU.get(status, status)

    short_id = _short_id(ticket.id)
    title = escape_html(ticket.title or "")
    description = escape_html(ticket.description or "")

    created_at = ticket.created_at.strftime("%d.%m.%Y %H:%M") if ticket.created_at else ""

    lines: list[str] = []
    lines.append(f"<b>Заявка #{short_id}</b>")
    status_line_parts = [
        part for part in (status_emoji, status_label, priority_emoji) if part
    ]
    if status_line_parts:
        lines.append(" ".join(status_line_parts))
    lines.append("")
    lines.append(f"<b>{title}</b>")
    if description:
        lines.append("")
        lines.append(description)
    if created_at:
        lines.append("")
        lines.append(f"Создана: {created_at}")
    return "\n".join(lines)


def format_article_preview(article: Any) -> str:
    """Knowledge base article preview: bold title + body trimmed to ~4000 chars."""
    title = _attr(article, "title", "") or ""
    body = _attr(article, "body", "") or _attr(article, "content", "") or ""
    title_html = escape_html(str(title))
    body_text = str(body)
    if len(body_text) > _ARTICLE_BODY_LIMIT:
        body_text = body_text[: _ARTICLE_BODY_LIMIT - 1].rstrip() + "…"
    body_html = escape_html(body_text)
    return f"<b>{title_html}</b>\n\n{body_html}"


def format_project_card(project: Any) -> str:
    """Short project card — name, type, and current phase if available.

    Accepts dict or ORM instance; missing fields are rendered as em-dashes.
    Progress bar is intentionally omitted until project service exposes it.
    """
    name = _attr(project, "name", "") or "—"
    ptype = _attr(project, "type", "") or _attr(project, "project_type", "") or "—"
    current_phase = (
        _attr(project, "current_phase", "")
        or _attr(project, "phase", "")
        or _attr(project, "current_phase_name", "")
        or "—"
    )

    lines = [
        f"<b>{escape_html(str(name))}</b>",
        f"Тип: {escape_html(str(ptype))}",
        f"Текущая фаза: {escape_html(str(current_phase))}",
    ]
    return "\n".join(lines)


def _attr(obj: Any, key: str, default: Any = None) -> Any:
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)

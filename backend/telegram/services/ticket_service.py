from __future__ import annotations

import logging
import uuid as uuid_mod
from pathlib import Path

import httpx
from sqlmodel import func, select

from backend.auth.models import User
from backend.config import settings
from backend.database import async_session_factory
from backend.tickets.models import (
    Attachment,
    Ticket,
    TicketEvent,
    TicketSource,
    TicketStatus,
)
from backend.tickets.templates import TicketArticleLink

logger = logging.getLogger(__name__)

# Match storage convention of legacy backend/notifications/telegram.py.
# Task 13 removes the legacy module; this constant becomes the canonical path.
_UPLOAD_DIR = Path("/app/data/attachments")
_MAX_TG_FILE_SIZE = 20 * 1024 * 1024  # 20 MB — Telegram bot API hard limit.


async def count_active_tickets(user_id: str) -> int:
    """Count tickets where creator_id=user_id and status != closed."""
    async with async_session_factory() as session:
        result = await session.execute(
            select(func.count(Ticket.id)).where(
                Ticket.creator_id == user_id,
                Ticket.status != TicketStatus.CLOSED.value,
            )
        )
        return int(result.scalar_one() or 0)


# --- Telegram file download + attachment save ---------------------------


async def _download_tg_file(file_id: str) -> tuple[bytes, str] | None:
    """Download a file from Telegram by file_id. Returns (bytes, filename) or None."""
    token = getattr(settings, "telegram_bot_token", None) or ""
    if not token:
        return None
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.get(
                f"https://api.telegram.org/bot{token}/getFile",
                params={"file_id": file_id},
            )
            if r.status_code != 200:
                return None
            payload = r.json()
            if not payload.get("ok"):
                return None
            file_path = payload["result"]["file_path"]
            filename = Path(file_path).name

            fr = await client.get(f"https://api.telegram.org/file/bot{token}/{file_path}")
            if fr.status_code != 200:
                return None
            return fr.content, filename
    except Exception as exc:
        logger.warning("telegram download failed for file_id=%s: %s", file_id, exc)
        return None


def _save_attachment_to_disk(ticket_id: str, filename_hint: str, data: bytes) -> str:
    """Write bytes under {UPLOAD_DIR}/{ticket_id}/{uuid}{ext}. Returns storage_path."""
    file_id_uuid = str(uuid_mod.uuid4())
    ext = Path(filename_hint).suffix or ".bin"
    storage_path = f"{ticket_id}/{file_id_uuid}{ext}"
    full_path = _UPLOAD_DIR / storage_path
    full_path.parent.mkdir(parents=True, exist_ok=True)
    full_path.write_bytes(data)
    return storage_path


# --- Ticket creation ----------------------------------------------------


async def create_ticket(data: dict, user: User) -> Ticket:
    """Create a ticket from wizard state data.

    Steps:
      1. Build Ticket with product/category/description and TELEGRAM source.
      2. Apply impact/urgency OR auto-detection, then recalculate priority.
      3. Auto-assign group; default assignee from app_settings if configured.
      4. Insert, flush, create creation TicketEvent.
      5. Download each pending TG attachment and persist to disk + DB.
      6. Link deflection articles (relation_type=related).
      7. Commit.
    """
    user_id = str(user.id)
    description = data.get("description", "") or ""
    product = data.get("product") or "pass24_online"
    category = data.get("category") or "other"

    # Title: first 100 chars of description, collapse whitespace so multi-line
    # descriptions don't produce ugly list headers.
    title_source = " ".join(description.split())
    title = title_source[:100] if title_source else "Заявка из Telegram"

    async with async_session_factory() as session:
        ticket = Ticket(
            source=TicketSource.TELEGRAM,
            creator_id=user_id,
            title=title,
            description=description[:10000],
            product=product,
            category=category,
            contact_name=getattr(user, "full_name", None),
            contact_email=getattr(user, "email", None),
        )

        impact = data.get("impact")
        urgency = data.get("urgency")
        if impact in {"high", "medium", "low"} and urgency in {"high", "medium", "low"}:
            ticket.impact = impact
            ticket.urgency = urgency
            try:
                ticket.recalculate_priority()
            except Exception as exc:
                logger.warning("recalculate_priority failed: %s", exc)
        else:
            try:
                ticket.auto_detect_category()
            except Exception as exc:
                logger.warning("auto_detect_category failed: %s", exc)
            # Re-apply user's explicit choices: auto_detect_category may overwrite
            # them based on keywords, but the user picked them deliberately.
            ticket.product = product
            ticket.category = category
            try:
                ticket.assign_priority_based_on_context()
            except Exception as exc:
                logger.warning("assign_priority_based_on_context failed: %s", exc)

        try:
            ticket.auto_assign_group()
        except Exception as exc:
            logger.warning("auto_assign_group failed: %s", exc)

        # Default assignee from app settings (matches HTTP ticket creation path).
        try:
            from backend.app_settings import get_default_assignee_id
            default_agent = await get_default_assignee_id()
            if default_agent and not ticket.assignee_id:
                ticket.assignee_id = default_agent
        except Exception as exc:
            logger.warning("default assignee lookup failed: %s", exc)

        session.add(ticket)
        await session.flush()  # assign ticket.id

        # Creation event
        event = TicketEvent(
            ticket_id=ticket.id,
            actor_id=user_id,
            description="Тикет создан из Telegram (мастер заявок v2)",
        )
        session.add(event)

        # Attachments
        for att in data.get("attachments", []) or []:
            file_id = att.get("file_id")
            if not file_id:
                continue
            downloaded = await _download_tg_file(file_id)
            if not downloaded:
                logger.warning("skipping attachment %s: download failed", file_id)
                continue
            payload, tg_filename = downloaded
            if len(payload) > _MAX_TG_FILE_SIZE:
                logger.warning("skipping attachment %s: exceeds %d bytes", file_id, _MAX_TG_FILE_SIZE)
                continue
            filename = att.get("filename") or tg_filename
            storage_path = _save_attachment_to_disk(ticket.id, filename, payload)
            attachment = Attachment(
                ticket_id=ticket.id,
                uploader_id=user_id,
                filename=filename,
                content_type=att.get("content_type") or "application/octet-stream",
                size=len(payload),
                storage_path=storage_path,
            )
            session.add(attachment)

        # Deflection article links
        for art in data.get("deflection_articles", []) or []:
            art_id = art.get("id")
            if not art_id:
                continue
            link = TicketArticleLink(
                ticket_id=ticket.id,
                article_id=str(art_id),
                relation_type="related",
                linked_by=user_id,
            )
            session.add(link)

        await session.commit()
        await session.refresh(ticket)
        return ticket

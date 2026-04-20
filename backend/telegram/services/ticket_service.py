from __future__ import annotations

import logging
import uuid as uuid_mod
from datetime import datetime
from pathlib import Path

import httpx
from sqlmodel import func, select

from backend.auth.models import User
from backend.config import settings
from backend.database import async_session_factory
from backend.tickets.models import (
    Attachment,
    Ticket,
    TicketComment,
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


# --- Ticket listing + detail (Task 9) -----------------------------------


FILTER_ALIASES: dict[str, tuple[str, ...]] = {
    "active": (
        TicketStatus.NEW.value,
        TicketStatus.IN_PROGRESS.value,
        TicketStatus.WAITING_FOR_USER.value,
        TicketStatus.ON_HOLD.value,
        TicketStatus.ENGINEER_VISIT.value,
        TicketStatus.RESOLVED.value,  # resolved is "still active" for the user — awaiting their CSAT
    ),
    "closed": (TicketStatus.CLOSED.value,),
    "all": (),  # empty tuple == no filter
}


async def list_my_tickets(
    user_id: str,
    filter: str = "active",
    page: int = 1,
    per_page: int = 5,
) -> tuple[list[Ticket], int, int]:
    """Returns (tickets, total_count, total_pages). filter ∈ {active, all, closed}."""
    statuses = FILTER_ALIASES.get(filter, FILTER_ALIASES["active"])
    offset = max(0, (page - 1) * per_page)
    async with async_session_factory() as session:
        conditions = [Ticket.creator_id == user_id]
        if statuses:
            conditions.append(Ticket.status.in_(statuses))
        count_stmt = select(func.count(Ticket.id)).where(*conditions)
        total = int((await session.execute(count_stmt)).scalar_one() or 0)
        list_stmt = (
            select(Ticket)
            .where(*conditions)
            .order_by(Ticket.created_at.desc())
            .offset(offset)
            .limit(per_page)
        )
        result = await session.execute(list_stmt)
        tickets = list(result.scalars().all())
    total_pages = max(1, (total + per_page - 1) // per_page)
    return tickets, total, total_pages


async def get_ticket_with_comments(
    ticket_id_prefix: str,
    user_id: str,
    comments_limit: int = 10,
    comments_offset: int = 0,
) -> dict | None:
    """Return {ticket, comments, total_comments} if ticket belongs to user_id, else None.

    Matches first ticket whose id startswith(ticket_id_prefix). Only returns
    public (non-internal) comments, newest first.
    """
    async with async_session_factory() as session:
        stmt = (
            select(Ticket)
            .where(
                Ticket.creator_id == user_id,
                Ticket.id.startswith(ticket_id_prefix),
            )
            .order_by(Ticket.created_at.desc())
            .limit(1)
        )
        ticket = (await session.execute(stmt)).scalar_one_or_none()
        if ticket is None:
            return None

        count_stmt = (
            select(func.count(TicketComment.id))
            .where(
                TicketComment.ticket_id == ticket.id,
                TicketComment.is_internal == False,  # noqa: E712
            )
        )
        total_comments = int((await session.execute(count_stmt)).scalar_one() or 0)

        comments_stmt = (
            select(TicketComment)
            .where(
                TicketComment.ticket_id == ticket.id,
                TicketComment.is_internal == False,  # noqa: E712
            )
            .order_by(TicketComment.created_at.desc())
            .offset(max(0, comments_offset))
            .limit(max(1, comments_limit))
        )
        comments = list((await session.execute(comments_stmt)).scalars().all())

    return {"ticket": ticket, "comments": comments, "total_comments": total_comments}


# --- Telegram message → attachment meta helper (Task 10) -----------------


def extract_tg_attachment_meta(message) -> dict | None:
    """Build `{file_id, filename, content_type, size}` from an aiogram Message.

    Returns None when the message carries no attachable media (photo / document /
    video / voice). Shared by the create-ticket wizard (Task 7) and the reply
    flow (Task 10) so both produce identical attachment dicts.
    """
    if getattr(message, "photo", None):
        photo = message.photo[-1]  # largest size
        file_id = photo.file_id
        return {
            "file_id": file_id,
            "filename": f"photo_{file_id[:8]}.jpg",
            "content_type": "image/jpeg",
            "size": photo.file_size,
        }
    if getattr(message, "document", None):
        doc = message.document
        file_id = doc.file_id
        return {
            "file_id": file_id,
            "filename": doc.file_name or f"doc_{file_id[:8]}",
            "content_type": doc.mime_type or "application/octet-stream",
            "size": doc.file_size,
        }
    if getattr(message, "video", None):
        video = message.video
        file_id = video.file_id
        return {
            "file_id": file_id,
            "filename": f"video_{file_id[:8]}.mp4",
            "content_type": "video/mp4",
            "size": video.file_size,
        }
    if getattr(message, "voice", None):
        voice = message.voice
        file_id = voice.file_id
        return {
            "file_id": file_id,
            "filename": f"voice_{file_id[:8]}.ogg",
            "content_type": "audio/ogg",
            "size": voice.file_size,
        }
    return None


# --- Ticket reply / close / CSAT (Task 10) -------------------------------


async def resolve_ticket_by_short_id(short_id: str, user_id: str) -> Ticket | None:
    """Return the user's ticket matching the short-id prefix, or None.

    Callers use this to translate the 8-char prefix baked into inline-keyboard
    callbacks back into the full ticket id before mutating the ticket.
    """
    async with async_session_factory() as session:
        stmt = (
            select(Ticket)
            .where(
                Ticket.creator_id == user_id,
                Ticket.id.startswith(short_id),
            )
            .order_by(Ticket.created_at.desc())
            .limit(1)
        )
        return (await session.execute(stmt)).scalar_one_or_none()


async def add_comment(
    ticket_id: str,
    user: User,
    text: str,
    attachments: list[dict] | None = None,
) -> TicketComment:
    """Add a public comment from the ticket owner.

    Sets ``has_unread_reply``, transitions WAITING_FOR_USER → IN_PROGRESS,
    unfreezes SLA reply-pause via ``on_public_comment_added(is_staff=False)``,
    downloads + saves attachments if provided, links them to the new comment.

    Raises ``ValueError`` with a machine code:
      - ``not_found``     — ticket does not exist
      - ``not_owner``     — caller isn't the ticket creator
      - ``empty``         — neither text nor attachments provided
    """
    text = (text or "").strip()
    attachments = attachments or []
    if not text and not attachments:
        raise ValueError("empty")

    user_id = str(user.id)

    async with async_session_factory() as session:
        ticket = await session.get(Ticket, ticket_id)
        if ticket is None:
            raise ValueError("not_found")
        if ticket.creator_id != user_id:
            raise ValueError("not_owner")

        comment = TicketComment(
            ticket_id=ticket.id,
            author_id=user_id,
            author_name=getattr(user, "full_name", None) or "",
            text=text,
            is_internal=False,
            author_is_staff=False,
        )
        session.add(comment)
        await session.flush()  # assign comment.id for attachment FK

        # Download + persist attachments, linking each to the new comment.
        for att in attachments:
            file_id = att.get("file_id")
            if not file_id:
                continue
            downloaded = await _download_tg_file(file_id)
            if not downloaded:
                logger.warning("skipping reply attachment %s: download failed", file_id)
                continue
            payload, tg_filename = downloaded
            if len(payload) > _MAX_TG_FILE_SIZE:
                logger.warning(
                    "skipping reply attachment %s: exceeds %d bytes",
                    file_id,
                    _MAX_TG_FILE_SIZE,
                )
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
                comment_id=comment.id,
            )
            session.add(attachment)

        ticket.has_unread_reply = True

        # WAITING_FOR_USER → IN_PROGRESS on client reply (agents see the activity).
        if ticket.status == TicketStatus.WAITING_FOR_USER.value:
            try:
                event = ticket.transition(
                    actor_id=user_id,
                    new_status=TicketStatus.IN_PROGRESS,
                )
                session.add(event)
            except ValueError as exc:
                logger.warning("reply status transition skipped: %s", exc)

        now = datetime.utcnow()
        ticket.on_public_comment_added(is_staff=False, now=now)
        ticket.recompute_sla_pause(now=now)

        session.add(ticket)
        await session.commit()
        await session.refresh(comment)
        return comment


async def close_ticket(ticket_id: str, user: User) -> Ticket:
    """Close a ticket on the owner's behalf.

    Raises ``ValueError``:
      - ``not_found``      — ticket does not exist
      - ``not_owner``      — caller isn't the ticket creator
      - ``already_closed`` — ticket is already in CLOSED
    """
    user_id = str(user.id)
    async with async_session_factory() as session:
        ticket = await session.get(Ticket, ticket_id)
        if ticket is None:
            raise ValueError("not_found")
        if ticket.creator_id != user_id:
            raise ValueError("not_owner")
        if ticket.status == TicketStatus.CLOSED.value:
            raise ValueError("already_closed")

        event = ticket.transition(actor_id=user_id, new_status=TicketStatus.CLOSED)
        session.add(event)
        session.add(ticket)
        await session.commit()
        await session.refresh(ticket)
        return ticket


async def rate_csat(
    ticket_id: str,
    user: User,
    rating: int,
    comment: str | None = None,
) -> Ticket:
    """Persist a CSAT rating from the ticket owner.

    Transitions ``resolved`` → ``closed`` (user accepted the resolution). Does
    NOT touch ``satisfaction_requested_at`` (that is set by the agent side when
    the ticket is resolved).

    Raises ``ValueError``:
      - ``not_found``  — ticket does not exist
      - ``not_owner``  — caller isn't the ticket creator
      - ``bad_rating`` — rating outside 1..5
    """
    user_id = str(user.id)
    if not isinstance(rating, int) or rating < 1 or rating > 5:
        raise ValueError("bad_rating")

    async with async_session_factory() as session:
        ticket = await session.get(Ticket, ticket_id)
        if ticket is None:
            raise ValueError("not_found")
        if ticket.creator_id != user_id:
            raise ValueError("not_owner")

        ticket.satisfaction_rating = rating
        ticket.satisfaction_comment = (comment or None)
        ticket.satisfaction_submitted_at = datetime.utcnow()

        if ticket.status == TicketStatus.RESOLVED.value:
            try:
                event = ticket.transition(
                    actor_id=user_id,
                    new_status=TicketStatus.CLOSED,
                )
                session.add(event)
            except ValueError as exc:
                logger.warning("csat close transition skipped: %s", exc)

        session.add(ticket)
        await session.commit()
        await session.refresh(ticket)
        return ticket

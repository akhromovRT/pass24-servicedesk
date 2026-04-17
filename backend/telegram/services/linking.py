"""Account linking service for Telegram bot v2.

Generates one-time deep-link tokens, verifies them, links a user account to a
Telegram chat_id, and migrates legacy "ghost" users (created by the old bot at
`backend/notifications/telegram.py`) into the real account.

Tokens are issued with a TTL of `LINK_TOKEN_TTL_MINUTES` minutes and are
rate-limited to `LINK_TOKEN_MAX_PER_HOUR` per user. Tokens are single-use —
consumed tokens are marked by `used_at IS NOT NULL` and never deleted (a
future cleanup job will purge expired rows).

Ghost migration:
- Ghost users are those created by the legacy telegram notifier with
  `email` ending in `@telegram.pass24.local` and `telegram_chat_id` set to
  the chat being linked.
- When present, their tickets/comments/events are reassigned to the real
  user, and the ghost row is deactivated (email renamed, is_active=False,
  telegram_chat_id cleared).
"""
from __future__ import annotations

import secrets
import uuid
from datetime import datetime, timedelta

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from backend.auth.models import User
from backend.database import async_session_factory
from backend.telegram.config import (
    DEEP_LINK_BASE,
    LINK_TOKEN_MAX_PER_HOUR,
    LINK_TOKEN_TTL_MINUTES,
)


async def generate_token(user_id: str) -> dict:
    """Generate a one-time deep-link token for the given user.

    Returns ``{"token": str, "deeplink": str, "expires_at": iso8601 str}``.
    Raises ``ValueError("rate_limit")`` if the user has already generated
    ``LINK_TOKEN_MAX_PER_HOUR`` tokens in the last hour.
    """
    now = datetime.utcnow()
    window_start = now - timedelta(hours=1)

    async with async_session_factory() as session:
        # Rate-limit: count tokens still-in-window (expires_at > now-1h means
        # issue_time > now - 1h - TTL, roughly the last hour).
        count_row = await session.execute(
            text(
                "SELECT COUNT(*) FROM telegram_link_tokens "
                "WHERE user_id = :uid AND expires_at > :cutoff"
            ),
            {"uid": user_id, "cutoff": window_start},
        )
        issued = count_row.scalar_one()
        if issued >= LINK_TOKEN_MAX_PER_HOUR:
            raise ValueError("rate_limit")

        token = secrets.token_urlsafe(32)
        expires_at = now + timedelta(minutes=LINK_TOKEN_TTL_MINUTES)

        await session.execute(
            text(
                "INSERT INTO telegram_link_tokens (token, user_id, expires_at) "
                "VALUES (:token, :uid, :exp)"
            ),
            {"token": token, "uid": user_id, "exp": expires_at},
        )
        await session.commit()

    return {
        "token": token,
        "deeplink": f"{DEEP_LINK_BASE}{token}",
        # Suffix "Z" tells browsers the timestamp is UTC; without it JS
        # Date.parse() treats naive ISO strings as LOCAL time, which puts
        # the expiry in the past for any non-UTC client (e.g. Moscow +3).
        "expires_at": expires_at.isoformat() + "Z",
    }


async def verify_token(token: str) -> dict | None:
    """Check a token and return its payload.

    Returns ``{"user": User, "token": str, "expires_at": datetime}`` when the
    token exists, is unused, and has not expired; otherwise ``None``.
    """
    if not token:
        return None

    async with async_session_factory() as session:
        row = await session.execute(
            text(
                "SELECT user_id, expires_at, used_at "
                "FROM telegram_link_tokens WHERE token = :token"
            ),
            {"token": token},
        )
        record = row.first()
        if record is None:
            return None

        user_id, expires_at, used_at = record
        if used_at is not None:
            return None
        if expires_at < datetime.utcnow():
            return None

        user_result = await session.execute(
            select(User).where(User.id == user_id)
        )
        user = user_result.scalar_one_or_none()
        if user is None:
            return None

    return {"user": user, "token": token, "expires_at": expires_at}


async def link_account(token: str, chat_id: int) -> User:
    """Link the user referenced by ``token`` to ``chat_id``.

    Marks the token consumed, sets the user's ``telegram_chat_id`` and
    ``telegram_linked_at``, and migrates any ghost user that owned tickets
    under the same chat_id. Commits once.

    Raises ``ValueError("invalid_token")`` if the token is missing, expired,
    or already used. Raises ``ValueError("token_race")`` if a concurrent
    request consumed the same token first.
    """
    payload = await verify_token(token)
    if payload is None:
        raise ValueError("invalid_token")

    user_id = payload["user"].id  # uuid.UUID

    async with async_session_factory() as session:
        # Atomically mark the token used; a race with a parallel request will
        # return rowcount 0 here.
        mark_result = await session.execute(
            text(
                "UPDATE telegram_link_tokens SET used_at = now() "
                "WHERE token = :token AND used_at IS NULL"
            ),
            {"token": token},
        )
        if mark_result.rowcount == 0:
            await session.rollback()
            raise ValueError("token_race")

        user_result = await session.execute(
            select(User).where(User.id == user_id)
        )
        user = user_result.scalar_one_or_none()
        if user is None:
            await session.rollback()
            raise ValueError("invalid_token")

        user.telegram_chat_id = chat_id
        user.telegram_linked_at = datetime.utcnow()
        session.add(user)
        await session.flush()

        # Reassign legacy ghost-user rows to the real user (does not commit).
        await migrate_ghost(str(user.id), chat_id, session)

        await session.commit()
        await session.refresh(user)
        return user


async def migrate_ghost(
    real_user_id: str, chat_id: int, session: AsyncSession
) -> int:
    """Reassign a ghost user's tickets/comments/events to the real user.

    The ghost user is identified by ``telegram_chat_id = chat_id`` and an
    ``@telegram.pass24.local`` email. If none exists, returns 0. Otherwise
    returns the total number of ticket/comment/event rows moved.

    Does NOT commit — caller (``link_account``) owns the transaction.
    """
    ghost_result = await session.execute(
        select(User).where(
            User.telegram_chat_id == chat_id,
            User.email.like("%@telegram.pass24.local"),
            User.id != uuid.UUID(real_user_id),
            User.is_active == True,  # noqa: E712 — exclude previously deactivated ghosts
        ).limit(1)
    )
    ghost = ghost_result.scalar_one_or_none()
    if ghost is None:
        return 0

    ghost_id = str(ghost.id)

    tickets_result = await session.execute(
        text(
            "UPDATE tickets SET creator_id = :real WHERE creator_id = :ghost"
        ),
        {"real": real_user_id, "ghost": ghost_id},
    )
    comments_result = await session.execute(
        text(
            "UPDATE ticket_comments SET author_id = :real "
            "WHERE author_id = :ghost"
        ),
        {"real": real_user_id, "ghost": ghost_id},
    )
    events_result = await session.execute(
        text(
            "UPDATE ticket_events SET actor_id = :real "
            "WHERE actor_id = :ghost"
        ),
        {"real": real_user_id, "ghost": ghost_id},
    )

    total = (
        (tickets_result.rowcount or 0)
        + (comments_result.rowcount or 0)
        + (events_result.rowcount or 0)
    )

    # Deactivate ghost via ORM (email is unique → rename to free the slot).
    ghost.telegram_chat_id = None
    ghost.is_active = False
    ghost.email = f"deleted_{ghost.id}@telegram.pass24.local"
    session.add(ghost)
    await session.flush()

    return total


async def unlink_account(user_id: str) -> None:
    """Clear telegram_chat_id and telegram_linked_at for the given user."""
    async with async_session_factory() as session:
        result = await session.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()
        if user is None:
            return
        user.telegram_chat_id = None
        user.telegram_linked_at = None
        session.add(user)
        await session.commit()

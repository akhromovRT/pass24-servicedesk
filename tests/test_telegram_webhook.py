"""
Smoke integration tests for the Telegram webhook (bot v2).

Запуск на сервере (требует живой FastAPI + PG с применённой миграцией 023):

  docker exec site-pass24-servicedesk python -m pytest tests/test_telegram_webhook.py -v --tb=short

Тесты бьют в ``http://localhost:8000/telegram/webhook/{secret}`` минимальными
Telegram Update payload'ами и проверяют основные контракты:
  - 403 на неверный или пустой secret
  - 200 на корректный минимальный update
  - compat mode: text от unlinked-юзера создаёт ghost-тикет
  - /start от linked-юзера возвращает главное меню (без исключений)

Полный охват (inline-кнопки, FSM, вложения) требует реального Telegram API
и не входит в smoke-набор.
"""
from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import text
from sqlmodel import select

from backend.auth.models import User, UserRole
from backend.config import settings
from backend.database import async_session_factory

pytestmark = pytest.mark.asyncio

BASE_URL = "http://localhost:8000"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _secret() -> str:
    """Shared webhook secret from backend settings."""
    return (getattr(settings, "telegram_webhook_secret", "") or "").strip()


def _update_payload(
    *,
    update_id: int,
    chat_id: int,
    user_id: int,
    text: str,
    username: str = "smoke_user",
    first_name: str = "Smoke",
    is_command: bool = False,
) -> dict:
    """Build a minimal Telegram Update JSON payload sufficient for aiogram.

    Aiogram validates via the ``Update`` pydantic model; the shape below is the
    minimum required for a private-chat text message (optionally a command).
    """
    message: dict = {
        "message_id": int(uuid.uuid4().int % 1_000_000),
        "date": 0,
        "chat": {"id": chat_id, "type": "private"},
        "from": {
            "id": user_id,
            "is_bot": False,
            "first_name": first_name,
            "username": username,
        },
        "text": text,
    }
    if is_command and text.startswith("/"):
        # Provide MessageEntity for the leading command token so CommandStart /
        # deep-link parsing works in aiogram.
        message["entities"] = [
            {"type": "bot_command", "offset": 0, "length": len(text.split()[0])}
        ]
    return {"update_id": update_id, "message": message}


async def _delete_user_by_id(user_id) -> None:
    uid_str = str(user_id)
    async with async_session_factory() as session:
        await session.execute(
            text("DELETE FROM ticket_comments WHERE author_id = :uid"),
            {"uid": uid_str},
        )
        await session.execute(
            text("DELETE FROM ticket_events WHERE actor_id = :uid"),
            {"uid": uid_str},
        )
        await session.execute(
            text("DELETE FROM tickets WHERE creator_id = :uid"),
            {"uid": uid_str},
        )
        await session.execute(
            text("DELETE FROM users WHERE id = :uid"),
            {"uid": uid_str},
        )
        await session.commit()


async def _delete_ghost_by_email(email: str) -> None:
    async with async_session_factory() as session:
        result = await session.execute(
            select(User).where(User.email == email)
        )
        user = result.scalar_one_or_none()
        if user is None:
            return
    await _delete_user_by_id(user.id)


# ---------------------------------------------------------------------------
# Webhook security contract
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestWebhook:
    async def test_webhook_rejects_wrong_secret(self):
        payload = _update_payload(
            update_id=1,
            chat_id=111,
            user_id=111,
            text="/start",
            is_command=True,
        )
        async with AsyncClient(base_url=BASE_URL, timeout=10) as client:
            r = await client.post("/telegram/webhook/definitely-wrong", json=payload)
        assert r.status_code == 403

    async def test_webhook_rejects_missing_secret(self):
        # Empty path segment → FastAPI returns 404 (route mismatch); but an
        # empty string passed explicitly still hits the 403 branch via the
        # secret check. We use a whitespace-only secret that cannot match.
        async with AsyncClient(base_url=BASE_URL, timeout=10) as client:
            r = await client.post("/telegram/webhook/ ", json={})
        assert r.status_code in (403, 404, 422)

    async def test_webhook_accepts_minimal_update(self):
        secret = _secret()
        if not secret:
            pytest.skip("telegram_webhook_secret is not configured in this environment")
        # Unique chat id per run so we don't collide with ghost users from
        # previous test runs; we also clean up afterwards.
        chat_id = int(uuid.uuid4().int % 1_000_000_000)
        payload = _update_payload(
            update_id=int(uuid.uuid4().int % 1_000_000_000),
            chat_id=chat_id,
            user_id=chat_id,
            text="/start",
            is_command=True,
            username=f"smoke_{chat_id}",
        )
        try:
            async with AsyncClient(base_url=BASE_URL, timeout=10) as client:
                r = await client.post(f"/telegram/webhook/{secret}", json=payload)
            assert r.status_code == 200
            assert r.json() == {"ok": True}
        finally:
            await _delete_ghost_by_email(f"smoke_{chat_id}@telegram.pass24.local")


# ---------------------------------------------------------------------------
# Compat mode (unlinked → ghost ticket)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestCompatMode:
    async def test_unlinked_text_creates_ghost_ticket(self):
        """An unlinked user sending descriptive text should get a ghost ticket.

        Requires ``TELEGRAM_COMPAT_MODE = True`` (default) and a valid
        webhook secret. We first post ``/start`` to prime the welcome flow,
        then post a descriptive text message and assert a ticket exists for
        the synthesized ghost user.
        """
        secret = _secret()
        if not secret:
            pytest.skip("telegram_webhook_secret is not configured in this environment")

        chat_id = int(uuid.uuid4().int % 1_000_000_000)
        username = f"ghost_{chat_id}"
        ghost_email = f"{username}@telegram.pass24.local"

        start_payload = _update_payload(
            update_id=int(uuid.uuid4().int % 1_000_000_000),
            chat_id=chat_id,
            user_id=chat_id,
            text="/start",
            is_command=True,
            username=username,
        )
        text_payload = _update_payload(
            update_id=int(uuid.uuid4().int % 1_000_000_000),
            chat_id=chat_id,
            user_id=chat_id,
            text="Не срабатывает пропуск на шлагбауме со вчерашнего вечера",
            username=username,
        )

        try:
            async with AsyncClient(base_url=BASE_URL, timeout=15) as client:
                r1 = await client.post(f"/telegram/webhook/{secret}", json=start_payload)
                assert r1.status_code == 200
                r2 = await client.post(f"/telegram/webhook/{secret}", json=text_payload)
                assert r2.status_code == 200

            # Ghost user + ticket should exist.
            async with async_session_factory() as session:
                result = await session.execute(
                    select(User).where(User.email == ghost_email)
                )
                ghost = result.scalar_one_or_none()
                assert ghost is not None, "ghost user not created"
                from backend.tickets.models import Ticket, TicketSource
                ticket_row = await session.execute(
                    select(Ticket).where(
                        Ticket.creator_id == str(ghost.id),
                        Ticket.source == TicketSource.TELEGRAM,
                    )
                )
                ticket = ticket_row.scalar_one_or_none()
                assert ticket is not None, "ghost ticket not created"
        finally:
            await _delete_ghost_by_email(ghost_email)

    async def test_linked_user_start_command_shows_menu(self):
        """A linked user sending /start should get a 200 with the menu rendered.

        We seed a real user with ``telegram_chat_id`` + ``telegram_linked_at``
        and POST /start; we only assert 200 (menu rendering is verified by
        unit tests in test_telegram_bot.py).
        """
        secret = _secret()
        if not secret:
            pytest.skip("telegram_webhook_secret is not configured in this environment")

        chat_id = int(uuid.uuid4().int % 1_000_000_000)
        from datetime import datetime as _dt

        user = User(
            email=f"linked_{uuid.uuid4().hex[:8]}@example.com",
            hashed_password="x",
            full_name="Linked Smoke User",
            role=UserRole.RESIDENT,
            telegram_chat_id=chat_id,
            telegram_linked_at=_dt.utcnow(),
        )
        async with async_session_factory() as session:
            session.add(user)
            await session.commit()
            await session.refresh(user)

        payload = _update_payload(
            update_id=int(uuid.uuid4().int % 1_000_000_000),
            chat_id=chat_id,
            user_id=chat_id,
            text="/start",
            is_command=True,
            username="linked_smoke",
        )
        try:
            async with AsyncClient(base_url=BASE_URL, timeout=10) as client:
                r = await client.post(f"/telegram/webhook/{secret}", json=payload)
            assert r.status_code == 200
            assert r.json() == {"ok": True}
        finally:
            await _delete_user_by_id(user.id)

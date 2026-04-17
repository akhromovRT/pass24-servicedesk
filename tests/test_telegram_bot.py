"""
Интеграционные тесты Telegram bot v2 (PostgresStorage для aiogram FSM).

Запуск на сервере:
  docker exec site-pass24-servicedesk python -m pytest tests/test_telegram_bot.py -v

Требуют живой PostgreSQL с применённой миграцией 023 (telegram bot v2)
для класса TestPostgresStorage. Классы TestFormatters и TestKeyboards —
pure unit tests, могут запускаться без БД.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta

import pytest
import pytest_asyncio
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.base import StorageKey
from sqlalchemy import text
from sqlmodel import select

from backend.auth.models import User, UserRole
from backend.database import async_session_factory
from backend.telegram.formatters import (
    escape_html,
    format_ticket_card,
    format_ticket_list_item,
)
from backend.telegram.keyboards.common import (
    back_cancel_kb,
    cancel_kb,
    pagination_kb,
)
from backend.telegram.keyboards.main_menu import main_menu_kb
from backend.telegram.storage import PostgresStorage
from backend.tickets.models import Ticket, TicketPriority, TicketStatus


class _TestStates(StatesGroup):
    waiting_for_title = State()
    waiting_for_description = State()


def _make_key(chat_id: int | None = None) -> StorageKey:
    # Уникальный chat_id/user_id, чтобы тесты не пересекались
    cid = chat_id if chat_id is not None else int(uuid.uuid4().int % 10_000_000)
    return StorageKey(bot_id=1, chat_id=cid, user_id=cid)


async def _cleanup_key(key: StorageKey) -> None:
    key_str = f"{key.bot_id}:{key.chat_id}:{key.user_id}"
    async with async_session_factory() as session:
        await session.execute(
            text("DELETE FROM telegram_fsm_state WHERE key = :key"),
            {"key": key_str},
        )
        await session.commit()


@pytest_asyncio.fixture
async def storage():
    s = PostgresStorage()
    yield s
    await s.close()


@pytest.mark.asyncio
class TestPostgresStorage:
    async def test_set_get_state(self, storage: PostgresStorage):
        key = _make_key()
        try:
            await storage.set_state(key, _TestStates.waiting_for_title)
            value = await storage.get_state(key)
            assert value == _TestStates.waiting_for_title.state
        finally:
            await _cleanup_key(key)

    async def test_set_get_data(self, storage: PostgresStorage):
        key = _make_key()
        try:
            payload = {"title": "Не работает домофон", "count": 3}
            await storage.set_data(key, payload)
            value = await storage.get_data(key)
            assert value == payload
        finally:
            await _cleanup_key(key)

    async def test_get_state_not_found_returns_none(self, storage: PostgresStorage):
        key = _make_key()
        value = await storage.get_state(key)
        assert value is None

    async def test_get_data_not_found_returns_empty_dict(self, storage: PostgresStorage):
        key = _make_key()
        value = await storage.get_data(key)
        assert value == {}

    async def test_update_overwrites(self, storage: PostgresStorage):
        key = _make_key()
        try:
            await storage.set_state(key, _TestStates.waiting_for_title)
            await storage.set_state(key, _TestStates.waiting_for_description)
            assert await storage.get_state(key) == _TestStates.waiting_for_description.state

            await storage.set_data(key, {"a": 1})
            await storage.set_data(key, {"b": 2})
            assert await storage.get_data(key) == {"b": 2}

            # Очистка state через None
            await storage.set_state(key, None)
            assert await storage.get_state(key) is None
        finally:
            await _cleanup_key(key)


# ---------------------------------------------------------------------------
# Pure unit tests (no DB) for formatters and keyboards.
# ---------------------------------------------------------------------------


def _make_ticket(**overrides) -> Ticket:
    defaults = dict(
        id="abcd1234efgh5678",
        creator_id="creator-1",
        title="Не работает приложение",
        description="Подробности ошибки",
        status=TicketStatus.NEW.value,
        priority=TicketPriority.NORMAL,
        created_at=datetime(2026, 4, 17, 12, 30),
    )
    defaults.update(overrides)
    return Ticket(**defaults)


def _make_user(role: UserRole = UserRole.RESIDENT, customer_id: str | None = None) -> User:
    return User(
        email=f"{uuid.uuid4().hex}@example.com",
        hashed_password="x",
        full_name="Test User",
        role=role,
        customer_id=customer_id,
    )


class TestFormatters:
    """Pure unit tests for formatter functions."""

    def test_escape_html_basic(self):
        assert escape_html("<b>bold</b> & more") == "&lt;b&gt;bold&lt;/b&gt; &amp; more"

    def test_escape_html_handles_none(self):
        assert escape_html(None) == ""
        assert escape_html("") == ""

    def test_format_ticket_list_item_short(self):
        ticket = _make_ticket(title="Короткий заголовок")
        line = format_ticket_list_item(ticket)
        assert line.startswith("🔵 ")
        assert "#abcd1234" in line
        assert "Короткий заголовок" in line

    def test_format_ticket_list_item_truncates_long_title(self):
        long_title = "A" * 150
        ticket = _make_ticket(title=long_title)
        line = format_ticket_list_item(ticket)
        assert line.endswith("…")
        # Line should be shorter than the original long title.
        assert len(line) < len(long_title) + 30

    def test_format_ticket_list_item_escapes_html(self):
        ticket = _make_ticket(title="<script>alert(1)</script>")
        line = format_ticket_list_item(ticket)
        assert "&lt;script&gt;" in line
        # Raw < must not leak through into HTML output.
        assert "<script>" not in line

    def test_format_ticket_card_has_id_and_status(self):
        ticket = _make_ticket(
            status=TicketStatus.IN_PROGRESS.value,
            priority=TicketPriority.HIGH,
            title="Проблема с пропуском",
            description="Не срабатывает QR",
        )
        card = format_ticket_card(ticket)
        assert "#abcd1234" in card
        assert "<b>" in card
        assert "В работе" in card
        assert "🟡" in card  # IN_PROGRESS emoji
        assert "🟠" in card  # HIGH priority emoji
        assert "Проблема с пропуском" in card
        assert "Не срабатывает QR" in card
        assert "17.04.2026" in card


class TestKeyboards:
    """Pure unit tests for keyboard builders."""

    def test_cancel_kb(self):
        kb = cancel_kb()
        assert len(kb.inline_keyboard) == 1
        assert len(kb.inline_keyboard[0]) == 1
        btn = kb.inline_keyboard[0][0]
        assert "Отмена" in btn.text
        assert btn.callback_data == "mm:main"

    def test_back_cancel_kb(self):
        kb = back_cancel_kb("mm:tc")
        buttons = [b for row in kb.inline_keyboard for b in row]
        cbs = [b.callback_data for b in buttons]
        assert "mm:tc" in cbs
        assert "mm:main" in cbs

    def test_main_menu_resident_no_projects_button(self):
        user = _make_user(role=UserRole.RESIDENT)
        kb = main_menu_kb(user)
        cbs = [b.callback_data for row in kb.inline_keyboard for b in row]
        assert "mm:tc" in cbs
        assert "mm:tl" in cbs
        assert "mm:kb" in cbs
        assert "mm:ai" in cbs
        assert "mm:st" in cbs
        assert "mm:pr" not in cbs

    def test_main_menu_pm_with_customer_shows_projects(self):
        user = _make_user(role=UserRole.PROPERTY_MANAGER, customer_id="cust1")
        kb = main_menu_kb(user)
        cbs = [b.callback_data for row in kb.inline_keyboard for b in row]
        assert "mm:pr" in cbs

    def test_main_menu_pm_without_customer_hides_projects(self):
        user = _make_user(role=UserRole.PROPERTY_MANAGER, customer_id=None)
        kb = main_menu_kb(user)
        cbs = [b.callback_data for row in kb.inline_keyboard for b in row]
        assert "mm:pr" not in cbs

    def test_main_menu_counters_suffix(self):
        user = _make_user(role=UserRole.PROPERTY_MANAGER, customer_id="cust1")
        kb = main_menu_kb(user, active_tickets=3, pending_approvals=2)
        buttons = [b for row in kb.inline_keyboard for b in row]
        tickets_btn = next(b for b in buttons if b.callback_data == "mm:tl")
        projects_btn = next(b for b in buttons if b.callback_data == "mm:pr")
        assert "3" in tickets_btn.text
        assert "2" in projects_btn.text
        assert "⏳" in projects_btn.text

    def test_main_menu_counters_zero_no_suffix(self):
        user = _make_user(role=UserRole.RESIDENT)
        kb = main_menu_kb(user, active_tickets=0)
        buttons = [b for row in kb.inline_keyboard for b in row]
        tickets_btn = next(b for b in buttons if b.callback_data == "mm:tl")
        assert "•" not in tickets_btn.text

    def test_pagination_first_page_no_prev(self):
        kb = pagination_kb("tl", page=1, total_pages=3)
        buttons = [b for row in kb.inline_keyboard for b in row]
        texts = [b.text for b in buttons]
        assert not any("Пред" in t for t in texts)
        assert any("След" in t for t in texts)
        assert any("1/3" in t for t in texts)

    def test_pagination_middle_page_both(self):
        kb = pagination_kb("tl", page=2, total_pages=3)
        buttons = [b for row in kb.inline_keyboard for b in row]
        texts = [b.text for b in buttons]
        assert any("Пред" in t for t in texts)
        assert any("След" in t for t in texts)
        assert any("2/3" in t for t in texts)
        # Prev should point to page 1, next to page 3.
        cbs = [b.callback_data for b in buttons]
        assert any(cb and cb.startswith("tl:page:1:") for cb in cbs)
        assert any(cb and cb.startswith("tl:page:3:") for cb in cbs)

    def test_pagination_last_page_no_next(self):
        kb = pagination_kb("tl", page=3, total_pages=3)
        buttons = [b for row in kb.inline_keyboard for b in row]
        texts = [b.text for b in buttons]
        assert any("Пред" in t for t in texts)
        assert not any("След" in t for t in texts)

    def test_pagination_single_page(self):
        kb = pagination_kb("tl", page=1, total_pages=1)
        buttons = [b for row in kb.inline_keyboard for b in row]
        texts = [b.text for b in buttons]
        # Only the Стр 1/1 no-op button remains.
        assert len(buttons) == 1
        assert "1/1" in texts[0]
        assert buttons[0].callback_data == "noop"

    def test_pagination_passes_filter_value(self):
        kb = pagination_kb("tl", page=2, total_pages=3, filter_val="open")
        cbs = [
            b.callback_data
            for row in kb.inline_keyboard
            for b in row
            if b.callback_data and b.callback_data != "noop"
        ]
        assert all(cb.endswith(":open") for cb in cbs)


# ---------------------------------------------------------------------------
# Account linking — integration tests (require live DB + migration 019).
# ---------------------------------------------------------------------------


async def _create_real_user(role: UserRole = UserRole.RESIDENT) -> User:
    user = User(
        email=f"real_{uuid.uuid4().hex[:8]}@test.local",
        hashed_password="x",
        full_name="Real User",
        role=role,
    )
    async with async_session_factory() as session:
        session.add(user)
        await session.commit()
        await session.refresh(user)
    return user


async def _create_ghost_user(chat_id: int) -> User:
    ghost = User(
        email=f"ghost_{uuid.uuid4().hex[:8]}@telegram.pass24.local",
        hashed_password="x",
        full_name="Ghost User",
        role=UserRole.RESIDENT,
        telegram_chat_id=chat_id,
    )
    async with async_session_factory() as session:
        session.add(ghost)
        await session.commit()
        await session.refresh(ghost)
    return ghost


async def _delete_user(user_id) -> None:
    uid_str = str(user_id)
    async with async_session_factory() as session:
        await session.execute(
            text("DELETE FROM telegram_link_tokens WHERE user_id = :uid"),
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


async def _insert_token(token: str, user_id, *, expires_at: datetime, used_at: datetime | None = None) -> None:
    async with async_session_factory() as session:
        await session.execute(
            text(
                "INSERT INTO telegram_link_tokens (token, user_id, expires_at, used_at) "
                "VALUES (:token, :uid, :exp, :used)"
            ),
            {
                "token": token,
                "uid": str(user_id),
                "exp": expires_at,
                "used": used_at,
            },
        )
        await session.commit()


@pytest.mark.asyncio
class TestLinking:
    async def test_generate_token_creates_record(self):
        from backend.telegram.services.linking import generate_token

        user = await _create_real_user()
        try:
            result = await generate_token(str(user.id))
            assert "token" in result
            assert "deeplink" in result
            assert "expires_at" in result
            assert result["deeplink"].endswith(result["token"])

            async with async_session_factory() as session:
                row = await session.execute(
                    text(
                        "SELECT user_id FROM telegram_link_tokens WHERE token = :t"
                    ),
                    {"t": result["token"]},
                )
                record = row.first()
                assert record is not None
                assert str(record[0]) == str(user.id)
        finally:
            await _delete_user(user.id)

    async def test_generate_token_rate_limit(self):
        from backend.telegram.services.linking import generate_token

        user = await _create_real_user()
        try:
            future = datetime.utcnow() + timedelta(minutes=10)
            for _ in range(5):
                await _insert_token(uuid.uuid4().hex, user.id, expires_at=future)
            with pytest.raises(ValueError, match="rate_limit"):
                await generate_token(str(user.id))
        finally:
            await _delete_user(user.id)

    async def test_verify_valid_token(self):
        from backend.telegram.services.linking import verify_token

        user = await _create_real_user()
        try:
            token = uuid.uuid4().hex
            future = datetime.utcnow() + timedelta(minutes=10)
            await _insert_token(token, user.id, expires_at=future)

            payload = await verify_token(token)
            assert payload is not None
            assert payload["token"] == token
            assert payload["user"].id == user.id
        finally:
            await _delete_user(user.id)

    async def test_verify_expired_token_returns_none(self):
        from backend.telegram.services.linking import verify_token

        user = await _create_real_user()
        try:
            token = uuid.uuid4().hex
            past = datetime.utcnow() - timedelta(seconds=1)
            await _insert_token(token, user.id, expires_at=past)

            assert await verify_token(token) is None
        finally:
            await _delete_user(user.id)

    async def test_verify_used_token_returns_none(self):
        from backend.telegram.services.linking import verify_token

        user = await _create_real_user()
        try:
            token = uuid.uuid4().hex
            now = datetime.utcnow()
            await _insert_token(
                token,
                user.id,
                expires_at=now + timedelta(minutes=10),
                used_at=now,
            )
            assert await verify_token(token) is None
        finally:
            await _delete_user(user.id)

    async def test_link_account_sets_chat_id_and_linked_at(self):
        from backend.telegram.services.linking import link_account

        user = await _create_real_user()
        chat_id = int(uuid.uuid4().int % 1_000_000_000)
        try:
            token = uuid.uuid4().hex
            future = datetime.utcnow() + timedelta(minutes=10)
            await _insert_token(token, user.id, expires_at=future)

            linked = await link_account(token, chat_id)
            assert linked.telegram_chat_id == chat_id
            assert linked.telegram_linked_at is not None

            async with async_session_factory() as session:
                result = await session.execute(
                    select(User).where(User.id == user.id)
                )
                refreshed = result.scalar_one()
                assert refreshed.telegram_chat_id == chat_id
                assert refreshed.telegram_linked_at is not None
        finally:
            await _delete_user(user.id)

    async def test_link_account_marks_token_used(self):
        from backend.telegram.services.linking import link_account

        user = await _create_real_user()
        chat_id = int(uuid.uuid4().int % 1_000_000_000)
        try:
            token = uuid.uuid4().hex
            future = datetime.utcnow() + timedelta(minutes=10)
            await _insert_token(token, user.id, expires_at=future)

            await link_account(token, chat_id)

            async with async_session_factory() as session:
                row = await session.execute(
                    text(
                        "SELECT used_at FROM telegram_link_tokens WHERE token = :t"
                    ),
                    {"t": token},
                )
                used_at = row.scalar_one()
                assert used_at is not None
        finally:
            await _delete_user(user.id)

    async def test_migrate_ghost_transfers_tickets(self):
        from backend.telegram.services.linking import link_account
        from backend.tickets.models import Ticket, TicketPriority, TicketStatus

        user = await _create_real_user()
        chat_id = int(uuid.uuid4().int % 1_000_000_000)
        ghost = await _create_ghost_user(chat_id)
        ticket_id = str(uuid.uuid4())
        try:
            async with async_session_factory() as session:
                ticket = Ticket(
                    id=ticket_id,
                    creator_id=str(ghost.id),
                    title="Ghost ticket",
                    description="Before migration",
                    status=TicketStatus.NEW.value,
                    priority=TicketPriority.NORMAL,
                )
                session.add(ticket)
                await session.commit()

            token = uuid.uuid4().hex
            future = datetime.utcnow() + timedelta(minutes=10)
            await _insert_token(token, user.id, expires_at=future)

            await link_account(token, chat_id)

            async with async_session_factory() as session:
                row = await session.execute(
                    text("SELECT creator_id FROM tickets WHERE id = :tid"),
                    {"tid": ticket_id},
                )
                creator_id = row.scalar_one()
                assert str(creator_id) == str(user.id)
        finally:
            async with async_session_factory() as session:
                await session.execute(
                    text("DELETE FROM tickets WHERE id = :tid"),
                    {"tid": ticket_id},
                )
                await session.commit()
            await _delete_user(user.id)
            await _delete_user(ghost.id)

    async def test_migrate_ghost_deactivates_ghost(self):
        from backend.telegram.services.linking import link_account

        user = await _create_real_user()
        chat_id = int(uuid.uuid4().int % 1_000_000_000)
        ghost = await _create_ghost_user(chat_id)
        try:
            token = uuid.uuid4().hex
            future = datetime.utcnow() + timedelta(minutes=10)
            await _insert_token(token, user.id, expires_at=future)

            await link_account(token, chat_id)

            async with async_session_factory() as session:
                result = await session.execute(
                    select(User).where(User.id == ghost.id)
                )
                refreshed = result.scalar_one()
                assert refreshed.is_active is False
                assert refreshed.telegram_chat_id is None
                assert refreshed.email.startswith("deleted_")
        finally:
            await _delete_user(user.id)
            await _delete_user(ghost.id)

    async def test_unlink_clears_fields(self):
        from backend.telegram.services.linking import unlink_account

        user = await _create_real_user()
        chat_id = int(uuid.uuid4().int % 1_000_000_000)
        try:
            async with async_session_factory() as session:
                result = await session.execute(
                    select(User).where(User.id == user.id)
                )
                u = result.scalar_one()
                u.telegram_chat_id = chat_id
                u.telegram_linked_at = datetime.utcnow()
                session.add(u)
                await session.commit()

            await unlink_account(str(user.id))

            async with async_session_factory() as session:
                result = await session.execute(
                    select(User).where(User.id == user.id)
                )
                refreshed = result.scalar_one()
                assert refreshed.telegram_chat_id is None
                assert refreshed.telegram_linked_at is None
        finally:
            await _delete_user(user.id)

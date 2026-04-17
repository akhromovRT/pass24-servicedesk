"""
Интеграционные тесты Telegram bot v2 (PostgresStorage для aiogram FSM).

Запуск на сервере:
  docker exec site-pass24-servicedesk python -m pytest tests/test_telegram_bot.py -v

Требуют живой PostgreSQL с применённой миграцией 021.
"""
from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.base import StorageKey
from sqlalchemy import text

from backend.database import async_session_factory
from backend.telegram.storage import PostgresStorage

pytestmark = pytest.mark.asyncio


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

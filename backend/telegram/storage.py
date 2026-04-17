from __future__ import annotations

import json
from typing import Any

from aiogram.fsm.state import State
from aiogram.fsm.storage.base import BaseStorage, StorageKey
from sqlalchemy import text

from backend.database import async_session_factory


def _key_to_str(key: StorageKey) -> str:
    return f"{key.bot_id}:{key.chat_id}:{key.user_id}"


def _state_to_str(state: State | str | None) -> str | None:
    if state is None:
        return None
    if isinstance(state, State):
        return state.state
    return str(state)


class PostgresStorage(BaseStorage):
    """aiogram FSM storage persisted in PostgreSQL (`telegram_fsm_state`)."""

    async def set_state(
        self, key: StorageKey, state: State | str | None = None
    ) -> None:
        key_str = _key_to_str(key)
        state_str = _state_to_str(state)
        async with async_session_factory() as session:
            await session.execute(
                text(
                    "INSERT INTO telegram_fsm_state (key, state, data, updated_at) "
                    "VALUES (:key, :state, '{}'::json, now()) "
                    "ON CONFLICT (key) DO UPDATE SET "
                    "state = EXCLUDED.state, updated_at = now()"
                ),
                {"key": key_str, "state": state_str},
            )
            await session.commit()

    async def get_state(self, key: StorageKey) -> str | None:
        key_str = _key_to_str(key)
        async with async_session_factory() as session:
            result = await session.execute(
                text("SELECT state FROM telegram_fsm_state WHERE key = :key"),
                {"key": key_str},
            )
            row = result.first()
        if row is None:
            return None
        return row[0]

    async def set_data(self, key: StorageKey, data: dict[str, Any]) -> None:
        key_str = _key_to_str(key)
        data_json = json.dumps(data)
        async with async_session_factory() as session:
            await session.execute(
                text(
                    "INSERT INTO telegram_fsm_state (key, state, data, updated_at) "
                    "VALUES (:key, NULL, CAST(:data AS json), now()) "
                    "ON CONFLICT (key) DO UPDATE SET "
                    "data = CAST(:data AS json), updated_at = now()"
                ),
                {"key": key_str, "data": data_json},
            )
            await session.commit()

    async def get_data(self, key: StorageKey) -> dict[str, Any]:
        key_str = _key_to_str(key)
        async with async_session_factory() as session:
            result = await session.execute(
                text("SELECT data FROM telegram_fsm_state WHERE key = :key"),
                {"key": key_str},
            )
            row = result.first()
        if row is None or row[0] is None:
            return {}
        value = row[0]
        if isinstance(value, str):
            return json.loads(value)
        return value

    async def close(self) -> None:
        return None

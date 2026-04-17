from __future__ import annotations

from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject
from sqlmodel import select

from backend.auth.models import User
from backend.database import async_session_factory


class AuthMiddleware(BaseMiddleware):
    """Populate data['user'] and data['is_linked'] from telegram_chat_id lookup.

    Never blocks: ghost flow (Task 14) relies on unlinked users reaching handlers.
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        chat_id = self._extract_chat_id(event)
        user: User | None = None
        if chat_id is not None:
            async with async_session_factory() as session:
                result = await session.execute(
                    select(User).where(User.telegram_chat_id == chat_id).limit(1)
                )
                user = result.scalar_one_or_none()

        data["user"] = user
        data["is_linked"] = bool(user and user.telegram_linked_at is not None)
        return await handler(event, data)

    @staticmethod
    def _extract_chat_id(event: TelegramObject) -> int | None:
        if isinstance(event, Message):
            return event.chat.id
        if isinstance(event, CallbackQuery):
            if event.message is not None:
                return event.message.chat.id
            if event.from_user is not None:
                return event.from_user.id
            return None
        return None

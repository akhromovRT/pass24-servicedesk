from __future__ import annotations

from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject
from sqlmodel import select

from backend.auth.models import User
from backend.database import async_session_factory
from backend.telegram.config import TELEGRAM_COMPAT_MODE


class AuthMiddleware(BaseMiddleware):
    """Populate data['user'] / data['is_linked'] / data['compat_mode'].

    Never blocks: the ghost flow (Task 14 compat handler) relies on unlinked
    users reaching handlers. ``compat_mode`` is True only for *unlinked* users
    while the global flag is on — linked users always see ``compat_mode=False``
    so the compat branches never steal their text.
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

        is_linked = bool(user and user.telegram_linked_at is not None)
        data["user"] = user
        data["is_linked"] = is_linked
        data["compat_mode"] = TELEGRAM_COMPAT_MODE and not is_linked
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

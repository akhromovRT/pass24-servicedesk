from __future__ import annotations

import time
from collections import defaultdict, deque
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

_WINDOW_SECONDS = 60.0
_MAX_EVENTS = 10
_THROTTLE_TEXT = "Слишком много сообщений, подождите минуту."


class ThrottleMiddleware(BaseMiddleware):
    """Per-chat in-memory rate limit: 10 events per 60s sliding window."""

    def __init__(self) -> None:
        self._buckets: dict[int, deque[float]] = defaultdict(deque)

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        chat_id = self._extract_chat_id(event)
        if chat_id is None:
            return await handler(event, data)

        now = time.monotonic()
        bucket = self._buckets[chat_id]
        cutoff = now - _WINDOW_SECONDS
        while bucket and bucket[0] < cutoff:
            bucket.popleft()
        # Drop empty buckets so idle chats do not accumulate entries forever;
        # defaultdict recreates an empty deque on the next access.
        if not bucket:
            del self._buckets[chat_id]
            bucket = self._buckets[chat_id]

        if len(bucket) >= _MAX_EVENTS:
            await self._notify(event)
            return None

        bucket.append(now)
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

    @staticmethod
    async def _notify(event: TelegramObject) -> None:
        if isinstance(event, Message):
            await event.answer(_THROTTLE_TEXT)
        elif isinstance(event, CallbackQuery):
            await event.answer(_THROTTLE_TEXT, show_alert=True)

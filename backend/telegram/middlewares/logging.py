from __future__ import annotations

import logging
import time
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

logger = logging.getLogger(__name__)


class LoggingMiddleware(BaseMiddleware):
    """Emit a single INFO line per update with chat_id, user id, callback, text and latency."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        start = time.perf_counter()
        try:
            return await handler(event, data)
        finally:
            latency_ms = (time.perf_counter() - start) * 1000
            chat_id = self._extract_chat_id(event)
            user = data.get("user")
            user_id = getattr(user, "id", None) if user is not None else None
            callback_data = event.data if isinstance(event, CallbackQuery) else None
            text_preview: str | None = None
            if isinstance(event, Message) and event.text:
                text_preview = event.text[:50]
            logger.info(
                "tg_update chat_id=%s user=%s cb=%s text=%s latency_ms=%.1f",
                chat_id,
                user_id,
                callback_data,
                text_preview,
                latency_ms,
            )

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

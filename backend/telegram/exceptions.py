from __future__ import annotations


class TelegramAuthError(Exception):
    """User not linked or token invalid."""


class TelegramRateLimit(Exception):
    """Too many requests from this chat_id."""

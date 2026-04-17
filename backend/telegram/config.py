from __future__ import annotations

from backend.config import settings

BOT_TOKEN = settings.telegram_bot_token
WEBHOOK_SECRET = settings.telegram_webhook_secret
APP_BASE_URL = settings.app_base_url
DEEP_LINK_BASE = "https://t.me/PASS24bot?start="
LINK_TOKEN_TTL_MINUTES = 10
LINK_TOKEN_MAX_PER_HOUR = 5

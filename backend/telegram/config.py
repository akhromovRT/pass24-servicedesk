from __future__ import annotations

from backend.config import settings

BOT_TOKEN = settings.telegram_bot_token
WEBHOOK_SECRET = settings.telegram_webhook_secret
APP_BASE_URL = settings.app_base_url
TELEGRAM_API_BASE = settings.telegram_api_base
DEEP_LINK_BASE = "https://t.me/PASS24bot?start="
LINK_TOKEN_TTL_MINUTES = 10
LINK_TOKEN_MAX_PER_HOUR = 5

# Compat mode: keep the old "text → ghost ticket" flow for unlinked users so
# legacy pre-v2 conversations continue to work during the rollout window.
# Plan: leave True for the first 2 weeks after deploy, then flip to False by
# editing this file manually once adoption is good. The handler in
# `backend/telegram/handlers/compat.py` reads this flag via the auth middleware.
TELEGRAM_COMPAT_MODE = True

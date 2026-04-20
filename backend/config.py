from __future__ import annotations

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/pass24_servicedesk"
    secret_key: str = "change-me-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 1440  # 24 hours

    # URL фронтенда (для ссылок в email)
    app_base_url: str = "https://support.pass24pro.ru"

    # Сброс пароля
    password_reset_expire_minutes: int = 60  # 1 час

    # SMTP (исходящая почта)
    smtp_host: str = "smtp.timeweb.ru"
    smtp_port: int = 465
    smtp_user: str = "support@pass24online.ru"
    smtp_password: str = ""
    smtp_from: str = "support@pass24online.ru"
    smtp_use_ssl: bool = True

    # IMAP (входящая почта)
    imap_host: str = "imap.timeweb.ru"
    imap_port: int = 993
    imap_poll_interval: int = 60  # секунд

    # AI Assistant (Claude + Qdrant)
    anthropic_api_key: str = ""
    anthropic_base_url: str = "https://api.anthropic.com"
    anthropic_model: str = "claude-sonnet-4-20250514"
    openai_api_key: str = ""
    openai_base_url: str = ""
    qdrant_url: str = "http://pass24-qdrant:6333"
    qdrant_api_key: str = ""
    qdrant_collection: str = "pass24_knowledge"

    # Telegram bot
    telegram_bot_token: str = ""
    telegram_webhook_secret: str = ""
    # Override Bot API base URL (e.g. reverse-proxy for hosts where
    # api.telegram.org is unreachable). Empty → use default api.telegram.org.
    # Expected format: scheme://host[:port][/prefix] — aiogram appends
    # `/bot{token}/{method}` and `/file/bot{token}/{path}` itself.
    telegram_api_base: str = ""

    # Bitrix24 CRM
    bitrix24_webhook_url: str = ""

    # DaData (поиск компаний по ИНН)
    dadata_api_key: str = ""

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()

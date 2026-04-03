from __future__ import annotations

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/pass24_servicedesk"
    secret_key: str = "change-me-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 1440  # 24 hours

    # SMTP
    smtp_host: str = "smtp.timeweb.ru"
    smtp_port: int = 465
    smtp_user: str = "support@pass24online.ru"
    smtp_password: str = ""
    smtp_from: str = "support@pass24online.ru"
    smtp_use_ssl: bool = True

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()

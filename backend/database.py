from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncGenerator
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from .config import settings

logger = logging.getLogger(__name__)

engine = create_async_engine(settings.database_url, echo=False)

async_session_factory = sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        yield session


def _run_alembic_upgrade() -> None:
    """Синхронный запуск Alembic upgrade (вызывается из отдельного потока)."""
    alembic_cfg = Config(str(Path(__file__).resolve().parent.parent / "alembic.ini"))
    command.upgrade(alembic_cfg, "head")


async def run_migrations() -> None:
    """Запуск Alembic-миграций при старте приложения.

    Выполняется в отдельном потоке, т.к. env.py использует asyncio.run()
    внутри, что конфликтует с уже запущенным event loop FastAPI.
    """
    try:
        await asyncio.to_thread(_run_alembic_upgrade)
        logger.info("Миграции БД применены успешно")
    except Exception as exc:
        logger.warning("Не удалось применить миграции БД: %s", exc)

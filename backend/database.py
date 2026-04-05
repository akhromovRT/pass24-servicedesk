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


async def _check_db_at_head() -> bool:
    """Проверяет, на какой версии сейчас БД. Возвращает True если на head."""
    from sqlalchemy import text
    async with engine.connect() as conn:
        # Читаем текущую версию из alembic_version
        try:
            result = await conn.execute(text("SELECT version_num FROM alembic_version"))
            current = result.scalar()
        except Exception:
            return False

    # Находим head версию из файлов миграций
    versions_dir = Path(__file__).resolve().parent.parent / "migrations" / "versions"
    heads = []
    for f in versions_dir.glob("*.py"):
        if f.name.startswith("_"):
            continue
        content = f.read_text(encoding="utf-8")
        # Ищем down_revision: если None или указывает на кого-то, то это не head
        # Проще: берём max по имени файла (001, 002, 003 → 003)
        import re
        m = re.search(r"^revision\s*[:=]\s*.*['\"]([^'\"]+)['\"]", content, re.MULTILINE)
        if m:
            heads.append(m.group(1))

    if not heads:
        return False
    head = max(heads)
    return current == head


async def run_migrations() -> None:
    """Запуск Alembic-миграций при старте приложения.

    Если БД уже на head — не вызываем alembic.upgrade (он иногда висит
    при совмещении с async event loop). Применяем только если нужно.
    """
    try:
        if await _check_db_at_head():
            logger.info("БД уже на последней версии миграций, upgrade пропущен")
            return
        await asyncio.to_thread(_run_alembic_upgrade)
        logger.info("Миграции БД применены успешно")
    except Exception as exc:
        logger.warning("Не удалось применить миграции БД: %s", exc)

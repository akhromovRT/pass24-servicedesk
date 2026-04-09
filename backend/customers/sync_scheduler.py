"""Ежедневная автосинхронизация Bitrix24 → Service Desk в 03:00."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta

from .bitrix24_sync import sync_companies, sync_contacts

logger = logging.getLogger(__name__)


async def bitrix24_sync_loop() -> None:
    """Бесконечный цикл: ждёт 03:00 каждый день и запускает синхронизацию."""
    logger.info("Bitrix24 daily sync scheduler started")
    while True:
        try:
            now = datetime.now()
            target = now.replace(hour=3, minute=0, second=0, microsecond=0)
            if target <= now:
                target += timedelta(days=1)
            sleep_sec = (target - now).total_seconds()
            logger.info("Next Bitrix24 sync at %s (in %.0f sec)", target.isoformat(), sleep_sec)
            await asyncio.sleep(sleep_sec)

            logger.info("Starting scheduled Bitrix24 sync...")
            stats_c = await sync_companies()
            stats_u = await sync_contacts()
            logger.info("Bitrix24 daily sync done: companies=%s, contacts=%s", stats_c, stats_u)
        except asyncio.CancelledError:
            logger.info("Bitrix24 sync scheduler stopped")
            break
        except Exception as exc:
            logger.error("Bitrix24 sync error: %s", exc, exc_info=True)
            await asyncio.sleep(300)

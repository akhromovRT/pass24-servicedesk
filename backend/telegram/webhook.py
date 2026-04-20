import logging

from aiogram.types import Update
from fastapi import APIRouter, HTTPException, Request

from backend.telegram import bot as bot_module  # module, so we see reassigned globals
from backend.telegram.config import WEBHOOK_SECRET

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/telegram", tags=["telegram"])


@router.post("/webhook/{secret}")
async def telegram_webhook(secret: str, request: Request):
    if not WEBHOOK_SECRET or secret != WEBHOOK_SECRET:
        raise HTTPException(status_code=403, detail="Forbidden")
    if not bot_module.bot or not bot_module.dp:
        raise HTTPException(status_code=503, detail="Bot not configured")
    update = Update.model_validate(await request.json())
    # Always ack Telegram with 200. If a handler raises, re-raising would cause
    # Telegram to retry the same update aggressively (bombardment). We log and
    # return OK so the update is considered delivered; reconcile failures via
    # application logs.
    try:
        await bot_module.dp.feed_update(bot_module.bot, update)
    except Exception:  # noqa: BLE001
        logger.exception("telegram update handler failed (update_id=%s)", update.update_id)
    return {"ok": True}

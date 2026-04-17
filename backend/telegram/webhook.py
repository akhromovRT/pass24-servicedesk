from aiogram.types import Update
from fastapi import APIRouter, HTTPException, Request

from backend.telegram import bot as bot_module  # module, so we see reassigned globals
from backend.telegram.config import WEBHOOK_SECRET

router = APIRouter(prefix="/telegram", tags=["telegram"])


@router.post("/webhook/{secret}")
async def telegram_webhook(secret: str, request: Request):
    if not WEBHOOK_SECRET or secret != WEBHOOK_SECRET:
        raise HTTPException(status_code=403, detail="Forbidden")
    if not bot_module.bot or not bot_module.dp:
        raise HTTPException(status_code=503, detail="Bot not configured")
    update = Update.model_validate(await request.json())
    await bot_module.dp.feed_update(bot_module.bot, update)
    return {"ok": True}

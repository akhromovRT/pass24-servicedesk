from aiogram import Bot, Dispatcher
from backend.telegram.config import BOT_TOKEN
from backend.telegram.storage import PostgresStorage

bot: Bot | None = None
dp: Dispatcher | None = None


def create_bot_and_dispatcher() -> tuple[Bot | None, Dispatcher | None]:
    global bot, dp
    if not BOT_TOKEN:
        return None, None
    bot = Bot(token=BOT_TOKEN)
    storage = PostgresStorage()
    dp = Dispatcher(storage=storage)
    from backend.telegram.handlers import register_all_routers
    register_all_routers(dp)
    return bot, dp

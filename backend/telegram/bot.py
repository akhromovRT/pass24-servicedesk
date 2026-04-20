from aiogram import Bot, Dispatcher
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.telegram import TelegramAPIServer
from backend.telegram.config import BOT_TOKEN, TELEGRAM_API_BASE
from backend.telegram.storage import PostgresStorage

bot: Bot | None = None
dp: Dispatcher | None = None


def create_bot_and_dispatcher() -> tuple[Bot | None, Dispatcher | None]:
    global bot, dp
    if not BOT_TOKEN:
        return None, None
    # On hosts where api.telegram.org is blocked outbound, route through a
    # reverse-proxy that forwards /bot<token>/<method> and /file/bot<token>/<path>
    # to api.telegram.org. Set TELEGRAM_API_BASE to the proxy base (e.g.
    # http://proxy:8080/telegram). Empty → use official api.telegram.org.
    if TELEGRAM_API_BASE:
        session = AiohttpSession(api=TelegramAPIServer.from_base(TELEGRAM_API_BASE))
        bot = Bot(token=BOT_TOKEN, session=session)
    else:
        bot = Bot(token=BOT_TOKEN)
    storage = PostgresStorage()
    dp = Dispatcher(storage=storage)

    # Register outer middlewares before routers.
    # Order matters: auth populates data['user'], throttle may short-circuit,
    # logging measures total handler latency (so it wraps the others).
    from backend.telegram.middlewares.auth import AuthMiddleware
    from backend.telegram.middlewares.logging import LoggingMiddleware
    from backend.telegram.middlewares.throttle import ThrottleMiddleware

    auth_mw = AuthMiddleware()
    throttle_mw = ThrottleMiddleware()
    logging_mw = LoggingMiddleware()

    dp.message.outer_middleware(auth_mw)
    dp.callback_query.outer_middleware(auth_mw)
    # Shared throttle instance: message + callback_query share the per-chat bucket.
    dp.message.outer_middleware(throttle_mw)
    dp.callback_query.outer_middleware(throttle_mw)
    dp.message.outer_middleware(logging_mw)
    dp.callback_query.outer_middleware(logging_mw)

    from backend.telegram.handlers import register_all_routers
    register_all_routers(dp)
    return bot, dp

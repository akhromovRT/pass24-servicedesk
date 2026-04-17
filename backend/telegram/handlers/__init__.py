from aiogram import Dispatcher


def register_all_routers(dp: Dispatcher) -> None:
    from backend.telegram.handlers.start import router as start_router
    dp.include_router(start_router)

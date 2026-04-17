from aiogram import Dispatcher


def register_all_routers(dp: Dispatcher) -> None:
    from backend.telegram.handlers.start import router as start_router
    from backend.telegram.handlers.tickets_create import router as tickets_create_router
    from backend.telegram.handlers.tickets_list import router as tickets_list_router
    from backend.telegram.handlers.menu import router as menu_router

    dp.include_router(start_router)
    # Wizard routers must register BEFORE menu so their stateful handlers
    # (description step F.text) match before menu's catch-all F.text fallback.
    dp.include_router(tickets_create_router)
    dp.include_router(tickets_list_router)
    # Menu router MUST be last: it contains a catch-all F.text handler for the
    # free-text fallback. Routers registered after it would never receive text
    # messages that fall through FSM states.
    dp.include_router(menu_router)

from aiogram import Dispatcher


def register_all_routers(dp: Dispatcher) -> None:
    from backend.telegram.handlers.start import router as start_router
    from backend.telegram.handlers.tickets_create import router as tickets_create_router
    from backend.telegram.handlers.tickets_list import router as tickets_list_router
    from backend.telegram.handlers.tickets_reply import router as tickets_reply_router
    from backend.telegram.handlers.csat import router as csat_router
    from backend.telegram.handlers.kb import router as kb_router
    from backend.telegram.handlers.ai import router as ai_router
    from backend.telegram.handlers.projects import router as projects_router
    from backend.telegram.handlers.approvals import router as approvals_router
    from backend.telegram.handlers.menu import router as menu_router

    dp.include_router(start_router)
    # Wizard routers must register BEFORE menu so their stateful handlers
    # (description step F.text) match before menu's catch-all F.text fallback.
    # tickets_create is first among stateful routers: its FSM states match
    # before tickets_reply's ReplyStates.typing F.text handler, so typing
    # inside the wizard won't accidentally feed the reply flow.
    dp.include_router(tickets_create_router)
    dp.include_router(tickets_list_router)
    dp.include_router(tickets_reply_router)
    dp.include_router(csat_router)
    # kb + ai own `kb:*`, `ai:*`, `mm:kb`, `mm:ai`, `ft:kb`, `ft:ai` and their
    # respective FSM text handlers. Register them before menu so awaiting_query
    # and chatting text handlers match before menu's catch-all F.text.
    dp.include_router(kb_router)
    dp.include_router(ai_router)
    # Projects (PM workspace) + approvals own `mm:pr`, `pr:*`, `ap:*` and
    # ApprovalStates text handler. Must register before menu for the FSM text
    # (reject reason) to match before menu's catch-all.
    dp.include_router(projects_router)
    dp.include_router(approvals_router)
    # Menu router MUST be last: it contains a catch-all F.text handler for the
    # free-text fallback. Routers registered after it would never receive text
    # messages that fall through FSM states.
    dp.include_router(menu_router)

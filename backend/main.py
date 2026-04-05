from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

# Настраиваем логирование наших модулей на INFO уровень
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
# backend.* видны, но sqlalchemy.engine слишком болтливый
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
logging.getLogger("sqlalchemy.pool").setLevel(logging.WARNING)

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .auth.router import router as auth_router
from .knowledge.router import router as knowledge_router
from .notifications.inbound import email_polling_loop
from .assistant.router import router as assistant_router
from .stats.router import router as stats_router
from .tickets.router import router as tickets_router
from .tickets.templates_router import router as templates_router
from .tickets.views_router import router as views_router
from .tickets.sla_watcher import sla_watcher_loop
from .notifications.telegram import router as telegram_router

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Запуск фоновых задач. Миграции запускаются вручную через alembic upgrade."""
    logger.info("Lifespan: starting email polling")
    poll_task = asyncio.create_task(email_polling_loop())
    logger.info("Lifespan: starting SLA watcher")
    sla_task = asyncio.create_task(sla_watcher_loop())
    logger.info("Lifespan: startup complete")
    yield
    poll_task.cancel()
    sla_task.cancel()


def create_app() -> FastAPI:
    app = FastAPI(
        title="PASS24 Service Desk API",
        description="Help Desk портал для клиентов и партнёров PASS24",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # SPA-маршруты ДО API (чтобы /tickets/create не перехватывался /tickets/{ticket_id})
    if STATIC_DIR.is_dir():
        _index = str(STATIC_DIR / "index.html")

        @app.get("/tickets/create", response_class=FileResponse, include_in_schema=False)
        async def spa_tickets_create():
            return FileResponse(_index)

        @app.get("/login", response_class=FileResponse, include_in_schema=False)
        async def spa_login():
            return FileResponse(_index)

        @app.get("/register", response_class=FileResponse, include_in_schema=False)
        async def spa_register():
            return FileResponse(_index)

    # API роутеры
    # ВАЖНО: views_router и templates_router регистрируются ДО tickets_router,
    # потому что tickets_router содержит GET /tickets/{ticket_id} — это широкий
    # паттерн, который перехватывает /tickets/saved-views, /tickets/templates и т.п.
    app.include_router(auth_router)
    app.include_router(views_router)
    app.include_router(templates_router)
    app.include_router(tickets_router)
    app.include_router(knowledge_router)
    app.include_router(stats_router)
    app.include_router(assistant_router)
    app.include_router(telegram_router)

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    # SPA fallback для всех остальных путей
    if STATIC_DIR.is_dir():
        app.mount("/assets", StaticFiles(directory=str(STATIC_DIR / "assets")), name="static-assets")

        @app.get("/{full_path:path}")
        async def serve_spa(request: Request, full_path: str):
            file_path = STATIC_DIR / full_path
            if file_path.is_file():
                return FileResponse(str(file_path))
            return FileResponse(str(STATIC_DIR / "index.html"))

    return app


app = create_app()

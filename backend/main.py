from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .auth.router import router as auth_router
from .database import run_migrations
from .knowledge.router import router as knowledge_router
from .notifications.inbound import email_polling_loop
from .assistant.router import router as assistant_router
from .stats.router import router as stats_router
from .tickets.router import router as tickets_router

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Запуск миграций БД и фоновых задач."""
    await run_migrations()
    # Запускаем фоновый опрос входящей почты
    poll_task = asyncio.create_task(email_polling_loop())
    yield
    poll_task.cancel()


def create_app() -> FastAPI:
    """
    Фабрика FastAPI-приложения PASS24 Service Desk.

    Подключает модули: аутентификация, тикеты, база знаний.
    """
    app = FastAPI(
        title="PASS24 Service Desk API",
        description="Help Desk портал для клиентов и партнёров PASS24",
        version="0.1.0",
        lifespan=lifespan,
    )

    # CORS — разрешаем запросы от фронтенда
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Роутеры
    app.include_router(auth_router)
    app.include_router(tickets_router)
    app.include_router(knowledge_router)
    app.include_router(stats_router)
    app.include_router(assistant_router)

    @app.get("/health")
    async def health():
        """Проверка работоспособности сервиса."""
        return {"status": "ok"}

    # Раздача SPA: static файлы + fallback на index.html для vue-router
    if STATIC_DIR.is_dir():
        app.mount("/assets", StaticFiles(directory=str(STATIC_DIR / "assets")), name="static-assets")

        @app.get("/{full_path:path}")
        async def serve_spa(request: Request, full_path: str):
            """Отдаёт index.html для всех не-API путей (SPA fallback)."""
            file_path = STATIC_DIR / full_path
            if file_path.is_file():
                return FileResponse(str(file_path))
            return FileResponse(str(STATIC_DIR / "index.html"))

    return app


app = create_app()

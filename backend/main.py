from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .auth.router import router as auth_router
from .database import init_db
from .knowledge.router import router as knowledge_router
from .tickets.router import router as tickets_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Создание таблиц БД при старте приложения."""
    await init_db()
    yield


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

    @app.get("/health")
    async def health():
        """Проверка работоспособности сервиса."""
        return {"status": "ok"}

    return app


app = create_app()

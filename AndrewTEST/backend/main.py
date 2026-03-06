from __future__ import annotations

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path

from .tickets.router import router as tickets_router, _TICKETS
from .tickets.schemas import TicketCreate


def create_app() -> FastAPI:
    """
    Фабрика FastAPI‑приложения.

    На данном этапе подключает только модуль тикетов.
    Позже сюда добавятся модули авторизации, базы знаний и интеграции с PASS24.
    """
    app = FastAPI(title="PASS24 Service Desk API")

    # API‑роуты
    app.include_router(tickets_router)

    # Базовая графическая оболочка (Jinja2 шаблоны)
    templates_dir = Path(__file__).resolve().parent / "templates"
    templates = Jinja2Templates(directory=str(templates_dir))

    @app.get("/", response_class=HTMLResponse)
    async def index(request: Request) -> HTMLResponse:
        """
        Простая страница: список тикетов и форма создания нового.
        Использует то же in-memory хранилище, что и API.
        """
        tickets = list(_TICKETS.values())
        # Сортируем по дате создания (новые сверху)
        tickets.sort(key=lambda t: t.created_at, reverse=True)
        return templates.TemplateResponse(
            "index.html",
            {
                "request": request,
                "tickets": tickets,
            },
        )

    @app.post("/create", response_class=HTMLResponse)
    async def create_ticket_ui(
        request: Request,
        title: str = Form(...),
        description: str = Form(...),
        creator_id: str = Form("demo-user"),
        object_id: str | None = Form(None),
        access_point_id: str | None = Form(None),
    ) -> HTMLResponse:
        """
        Обработчик формы создания тикета.
        Делегирует создание доменной логике через TicketCreate + API‑роутер.
        """
        payload = TicketCreate(
            title=title,
            description=description,
            creator_id=creator_id,
            object_id=object_id or None,
            access_point_id=access_point_id or None,
        )
        # Импортируем здесь, чтобы избежать циклов при старте
        from .tickets.router import create_ticket

        create_ticket(payload=payload)

        return RedirectResponse(url=request.url_for("index"), status_code=303)

    return app


app = create_app()


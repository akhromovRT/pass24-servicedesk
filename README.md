# PASS24 Service Desk

Help Desk портал для пользователей СКУД-системы [PASS24.online](https://pass24.online).

**Production:** https://support.pass24pro.ru

## Что это

Service Desk для команды поддержки PASS24 и клиентов (жителей ЖК, УК):
- Создание тикетов из web, email, Telegram
- Система SLA с рабочими часами и предупреждениями
- Аналитика, CSAT, дашборды агентов
- AI-ассистент на базе Claude + RAG по базе знаний

## Технический стек

- **Backend:** Python 3.12, FastAPI, SQLModel, PostgreSQL 16, Alembic
- **Frontend:** Vue 3 + TypeScript + PrimeVue 4 (Aura)
- **Auth:** JWT + bcrypt, RBAC (4 роли)
- **Каналы:** SMTP/IMAP, Telegram webhook, AI Assistant (Claude + Qdrant)
- **Деплой:** Docker multi-stage, GitHub Actions CI/CD, Nginx Proxy Manager

## Ключевые возможности

### Для клиентов
- Создание тикетов: web-портал, email, Telegram (@PASS24bot)
- Гостевая форма без регистрации
- Поиск в базе знаний + AI-ассистент
- Получение уведомлений на email и через Telegram
- Ответ на письма = комментарий к тикету (с вложениями)
- Оценка качества решения одним кликом из письма (CSAT)

### Для агентов
- Агентская панель: назначение, макросы, шаблоны ответов
- Колокольчик уведомлений о новых ответах клиентов
- Массовые действия (bulk: status/assign/delete)
- Merge дубликатов
- CSV-экспорт тикетов
- Персональный дашборд: метрики + CSAT по всем агентам
- Внутренние комментарии (видны только staff)

### Для системы
- Auto-transitions статусов по комментариям
- SLA с рабочими часами (пн-пт 9-18 МСК)
- Email-предупреждение за 30 мин до нарушения SLA
- Авто-классификация тикетов (product/category/priority)
- KB-suggestions при вводе темы

## API endpoints (36+)

| Модуль | Эндпоинты |
|--------|-----------|
| **Auth** | `POST /auth/register`, `POST /auth/login`, `GET /auth/me` |
| **Tickets CRUD** | `POST /tickets/`, `POST /tickets/guest`, `GET /tickets/`, `GET /tickets/{id}`, `DELETE /tickets/{id}` |
| **Tickets actions** | `POST /tickets/{id}/status`, `POST /tickets/{id}/comments`, `POST /tickets/{id}/attachments`, `GET /tickets/{id}/attachments/{att_id}`, `PUT /tickets/{id}/priority`, `PUT /tickets/{id}/assignment`, `POST /tickets/{id}/merge`, `POST /tickets/{id}/apply-macro`, `POST /tickets/{id}/satisfaction`, `GET /tickets/{id}/rate?r=N` |
| **Tickets staff** | `GET /tickets/agents/list`, `POST /tickets/bulk`, `GET /tickets/export.csv`, `GET /tickets/dashboard/me`, `GET /tickets/notifications/unread`, `GET /tickets/stats` |
| **Templates/Macros** | `GET/POST/DELETE /tickets/templates`, `POST /tickets/templates/{id}/use`, `GET/POST/DELETE /tickets/macros` |
| **Knowledge** | `GET /knowledge/`, `GET /knowledge/search`, `GET /knowledge/{slug}`, `POST/PUT/DELETE /knowledge/` |
| **Stats** | `GET /stats/overview`, `GET /stats/timeline`, `GET /stats/sla`, `GET /stats/agents` |
| **Assistant** | `POST /assistant/chat` |
| **Telegram** | `POST /telegram/webhook/{secret}` |
| **System** | `GET /health`, `GET /docs` (Swagger) |

## Структура проекта

```
backend/
├── main.py                   # FastAPI app + lifespan (polling + SLA watcher)
├── auth/                     # JWT, RBAC (4 роли)
├── tickets/                  # Тикеты, комментарии, вложения, SLA
│   ├── templates.py          # ResponseTemplate, Macro
│   ├── templates_router.py   # /tickets/templates, /tickets/macros
│   └── sla_watcher.py        # SLA + working-hours
├── knowledge/                # База знаний (FTS)
├── stats/                    # Аналитика
├── notifications/
│   ├── email.py              # SMTP исходящие
│   ├── inbound.py            # IMAP polling
│   └── telegram.py           # Telegram webhook
├── assistant/                # AI (Claude + Qdrant RAG)
└── scripts/                  # Утилиты (sync email, etc)

frontend/src/
├── pages/                    # 12 страниц (Login, Tickets, Dashboard, Analytics, KB, ...)
├── components/               # NotificationBell, AiChat, Badges
├── stores/                   # Pinia (auth, tickets, knowledge)
└── router/                   # vue-router с auth guard

migrations/versions/          # Alembic 001..005
tests/                        # 84 теста (pytest + httpx)
```

## Быстрый старт (локально)

```bash
# Backend
pip install -r requirements.txt
# Создать .env с DATABASE_URL и SMTP_*
docker exec site-pass24-servicedesk python -m alembic upgrade head
uvicorn backend.main:app --reload

# Frontend
cd frontend && npm install && npm run dev
# http://localhost:5173
```

## Документация

- `AGENTS.md` — правила работы AI-агентов с проектом
- `agent_docs/architecture.md` — архитектура, компоненты, roadmap, env
- `agent_docs/adr.md` — архитектурные решения (ADR-001, ADR-002)
- `agent_docs/development-history.md` — история итераций
- `agent_docs/guides/` — гайды по настройке окружения, DoD, логированию

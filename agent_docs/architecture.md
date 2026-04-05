# Архитектура

## Обзор

PASS24 Service Desk — веб-портал технической поддержки для пользователей СКУД-системы PASS24.online. Портал предоставляет систему тикетов и базу знаний.

**Основные модули:**
- **Тикеты** — создание заявок, отслеживание статуса, комментирование, уведомления
- **База знаний** — FAQ, инструкции, поиск по статьям
- **Авторизация** — разграничение ролей (резидент, администратор УК, агент поддержки)
- **Панель управления** — дашборд для агентов поддержки и администраторов

## Контекст

PASS24.online — облачная СКУД-система для жилых комплексов и бизнес-центров. Сервис-деск является самостоятельным порталом, предназначенным для обработки обращений пользователей PASS24.

**Роли пользователей:**
| Роль | Описание | Возможности |
|------|----------|-------------|
| Резидент | Житель ЖК / сотрудник БЦ | Создание тикетов, просмотр статуса, база знаний |
| Администратор УК | Управляющая компания | Просмотр тикетов своего объекта, эскалация |
| Агент поддержки | Команда PASS24 | Обработка тикетов, управление базой знаний |
| Администратор | Руководитель поддержки | Настройки, аналитика, управление пользователями |

## Ключевые компоненты

### Система тикетов
- 5-осевая классификация: product / category / ticket_type / source / status
- FSM: NEW → IN_PROGRESS → WAITING_FOR_USER → RESOLVED → CLOSED
- Auto-transitions: агент ответил → WAITING_FOR_USER; клиент ответил → IN_PROGRESS
- Комментарии (публичные + внутренние для staff)
- Вложения (10 МБ, модальный preview для images/PDF/text)
- SLA-трекинг (first_response_at, resolved_at, working-hours pause)
- CSAT: оценка 1-5 через emoji в email → HTML-страница "Спасибо"
- Назначение агентам + bulk actions + merge дубликатов
- Источники: web, email, telegram, api, phone

### База знаний
- Категории + типы (FAQ / Guide)
- Статьи с поддержкой Markdown
- PostgreSQL FTS (to_tsvector + plainto_tsquery) + ILIKE fallback
- Live KB-suggestions при создании тикета
- AI-ассистент использует KB как RAG-контекст

### Авторизация и доступ
- JWT + bcrypt (без passlib — прямой bcrypt)
- 4 роли: resident, property_manager, support_agent, admin
- Self-registration только для resident/property_manager
- Row-level security: резиденты видят только свои тикеты; агенты — все
- Внутренние комментарии скрыты от не-staff

### Агентские инструменты
- Колокольчик с polling-уведомлениями о новых ответах клиентов
- Dashboard: мои метрики (назначено/открыто/решено/CSAT) + таблица агентов
- Шаблоны ответов + макросы (одна кнопка)
- CSV-экспорт для Excel (BOM + UTF-8)

### Каналы связи (omnichannel)
- Web portal (авторизованный + guest flow)
- Email (support@pass24online.ru): IMAP polling, ответы по тегу `[PASS24-xxxxxxxx]`
- Telegram (@PASS24bot): webhook, приём тикетов в чате
- AI Assistant (Claude + Qdrant RAG): подсказки, поиск по KB

## Потоки данных

```
Резидент/Админ УК                    Агент поддержки
      │                                     │
      ▼                                     ▼
┌──────────────┐                  ┌──────────────────┐
│  Клиентский  │    REST API      │    Панель        │
│  портал      │◄────────────────►│    управления    │
└──────┬───────┘                  └────────┬─────────┘
       │                                   │
       ▼                                   ▼
┌─────────────────────────────────────────────────┐
│                   Backend API                    │
│  (тикеты, пользователи, база знаний, поиск)    │
└──────────────────────┬──────────────────────────┘
                       │
                       ▼
              ┌────────────────┐
              │    Database    │
              └────────────────┘
```

## Технологии и зависимости

> Решение зафиксировано в ADR-001.

| Компонент | Технология |
|-----------|-----------|
| Backend | Python 3.12 + FastAPI |
| ORM | SQLModel + SQLAlchemy 2.x async |
| БД | PostgreSQL 16 (asyncpg) |
| Миграции | Alembic |
| Frontend | Vue 3 + TypeScript + Vite |
| UI-библиотека | PrimeVue 4 (Aura theme) |
| State management | Pinia |
| Графики | vue-echarts |
| HTTP | httpx (async), aiosmtplib |
| Auth | python-jose (JWT) + bcrypt |
| AI | Anthropic Claude + Qdrant (RAG) |
| Фоновые задачи | FastAPI lifespan asyncio tasks |
| Email | SMTP (timeweb) + IMAP polling |
| Messaging | Telegram Bot API (webhook) |
| Deployment | Docker + GitHub Actions + Nginx Proxy Manager |

**Не используется:** Redis (BackgroundTasks + lifespan достаточно). Можно добавить при росте нагрузки.

## Нефункциональные требования и ограничения

- Портал должен быть адаптивным (мобильные устройства)
- Интерфейс на русском языке (основной), английский (опционально)
- Время отклика страниц < 2 секунды
- Безопасное хранение данных пользователей

## Текущая структура backend

```
backend/
├── main.py                   # FastAPI app factory, lifespan (polling + SLA watcher)
├── config.py                 # Настройки из .env (SMTP, IMAP, Telegram, AI)
├── database.py               # Async PostgreSQL engine + session
├── auth/                     # JWT-аутентификация, RBAC
│   ├── models.py             # User, UserRole (resident/PM/agent/admin)
│   ├── schemas.py, router.py, dependencies.py, utils.py
├── tickets/                  # Система тикетов
│   ├── models.py             # Ticket (с SLA, CSAT, has_unread_reply, merged_into), TicketEvent, TicketComment, Attachment
│   ├── templates.py          # ResponseTemplate, Macro
│   ├── schemas.py, router.py # CRUD + bulk + merge + apply-macro + CSV export + dashboard
│   ├── templates_router.py   # /tickets/templates, /tickets/macros
│   └── sla_watcher.py        # Фоновая проверка SLA + working-hours
├── knowledge/                # База знаний (FTS-поиск, slug)
│   ├── models.py, schemas.py, router.py
├── stats/                    # Аналитика
│   └── router.py             # /stats/overview, /stats/sla, /stats/agents
├── notifications/            # Email + Telegram
│   ├── email.py              # SMTP исходящие (notify_ticket_*)
│   ├── inbound.py            # IMAP polling, ответы → комментарии + вложения
│   └── telegram.py           # Telegram webhook → тикеты
├── assistant/                # AI-помощник (Claude + Qdrant RAG)
│   ├── router.py, rag.py
└── scripts/
    └── sync_email_replies.py # Ручная синхронизация пропущенных ответов

frontend/                     # Vue 3 SPA
├── src/
│   ├── pages/
│   │   ├── TicketsPage.vue           # Список с фильтрами, views, пагинацией
│   │   ├── TicketDetailPage.vue      # Детали + агентская панель (assign/templates/macros)
│   │   ├── CreateTicketPage.vue      # Создание + on-behalf-of + KB suggestions + phone mask
│   │   ├── AgentDashboardPage.vue    # Мои метрики + таблица агентов
│   │   ├── AnalyticsPage.vue         # Графики (echarts)
│   │   ├── KnowledgePage.vue, ArticlePage.vue
│   │   ├── InstructionsPage.vue, GuidePage.vue
│   │   ├── LoginPage.vue, RegisterPage.vue
│   │   └── SettingsPage.vue
│   ├── components/
│   │   ├── NotificationBell.vue      # Колокольчик с polling
│   │   ├── AiChat.vue                # AI-ассистент
│   │   ├── TicketStatusBadge.vue, TicketPriorityBadge.vue
│   │   └── CategoryBadge.vue, ArticleCard.vue
│   ├── stores/                       # Pinia (auth, tickets, knowledge)
│   ├── api/client.ts                 # fetch wrapper с JWT
│   └── router/                       # vue-router с auth guard

migrations/versions/
├── 001_initial_schema.py             # Базовая схема
├── 002_add_fts_and_stats.py          # FTS + индексы
├── 003_sla_attachments_internal_comments.py
├── 004_has_unread_reply.py           # Флаг непрочитанных ответов
└── 005_templates_macros_notifications.py  # Шаблоны, макросы, merge
```

## Деплой

- **Домен:** https://support.pass24pro.ru (Let's Encrypt SSL через NPM)
- **Сервер:** VPS (5.42.101.27), Docker
- **CI/CD:** GitHub Actions → GHCR → SSH deploy через `appleboy/ssh-action`
- **БД:** PostgreSQL 16 (`pass24-postgres` контейнер, БД `pass24_servicedesk`)
- **Сеть:** `onvis-net` через nginx-proxy-manager
- **Volumes:** `/opt/sites/pass24-servicedesk/data` (вложения)
- **Миграции:** запуск вручную после деплоя: `docker exec site-pass24-servicedesk python -m alembic upgrade head`

### Фоновые задачи (lifespan)
- **Email polling** (IMAP): каждые 60 сек
- **SLA watcher**: каждые 5 минут — email-предупреждение за 30 мин до нарушения

### Env переменные
```
DATABASE_URL, SECRET_KEY
SMTP_PASSWORD, SMTP_USER, IMAP_HOST
ANTHROPIC_API_KEY, ANTHROPIC_BASE_URL, ANTHROPIC_MODEL
OPENAI_API_KEY, OPENAI_BASE_URL
QDRANT_URL, QDRANT_API_KEY, QDRANT_COLLECTION
TELEGRAM_BOT_TOKEN, TELEGRAM_WEBHOOK_SECRET
```

## Roadmap

### MVP v0.1 — ✅ Завершён (2026-04-03)
- [x] Auth (JWT + bcrypt + RBAC, 4 роли)
- [x] Tickets CRUD + FSM + комментарии + аудит
- [x] Knowledge Base (CRUD, slug, ILIKE поиск)
- [x] Vue 3 SPA + PrimeVue 4
- [x] Email: SMTP out + IMAP in (автосоздание тикетов)
- [x] CI/CD деплой на VPS (Docker + GitHub Actions)

### v0.2 — ✅ Завершён (2026-04-03)
- [x] Alembic миграции
- [x] PostgreSQL FTS для базы знаний
- [x] Фильтры тикетов (object, creator, my, status, category, product, type)
- [x] Аналитика (vue-echarts): overview, timeline, SLA, agents

### v0.3 — ✅ Завершён (2026-04-03/04)
- [x] SLA-трекинг (first_response_at, resolved_at, sla_breached)
- [x] Вложения (10 МБ, images/PDF/docs, модальный preview)
- [x] Внутренние комментарии для агентов
- [x] ITIL-поля: impact, urgency, assignment_group, assignee_id
- [x] CSAT: оценка + one-click из email
- [x] Email-ответы → комментарии (через тег `[PASS24-xxx]`)
- [x] Создание тикетов агентами от имени клиента

### v0.4 — ✅ Завершён (2026-04-05)
- [x] Назначение тикетов агентам + dropdown
- [x] Массовые действия (bulk: status/assign/delete)
- [x] Шаблоны ответов + counter использования
- [x] Макросы (одна кнопка = статус + коммент + назначение)
- [x] Merge дубликатов
- [x] CSV-экспорт тикетов
- [x] Дашборд агента (/dashboard) + таблица всех агентов
- [x] SLA watcher (email за 30 мин до нарушения)
- [x] Working-hours SLA (пн-пт 9-18 МСК)
- [x] KB-suggestions при создании тикета
- [x] Авто-transitions статусов по комментариям
- [x] Флаг `has_unread_reply` + колокольчик уведомлений
- [x] Telegram-бот @PASS24bot (webhook)
- [x] Phone input с кодом страны (26 стран)
- [x] Синхронизация пропущенных email-ответов
- [x] Cleanup fixtures в тестах (84 теста)

### v0.5 (идеи)
- [ ] Push-уведомления (Service Workers, PWA)
- [ ] Multi-object фильтры для УК
- [ ] Связь статей с тикетами (link back)
- [ ] Saved views / persistent filters
- [ ] Интеграции: Sigur, Trassir, ZKTeco (планируется)
- [ ] Мобильное приложение

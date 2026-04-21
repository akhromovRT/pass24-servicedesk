# Архитектура

## Обзор

PASS24 Service Desk — веб-портал технической поддержки для пользователей СКУД-системы PASS24.online. Портал предоставляет систему тикетов и базу знаний.

**Основные модули:**
- **Тикеты** — создание заявок, отслеживание статуса, комментирование, уведомления
- **База знаний** — FAQ, инструкции, поиск по статьям
- **Проекты внедрения** — управление процессом установки PASS24 у клиентов (этапы, задачи, документы, timeline)
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
- 7 статусов: new → in_progress → waiting_for_user / on_hold / engineer_visit → resolved → closed
- Auto-transitions: первый ответ агента → in_progress; клиент ответил → in_progress
- SLA pause: on_hold и waiting_for_user ставят таймер на паузу; engineer_visit — нет
- Комментарии (публичные + внутренние для staff) — чат-формат с пузырями
- Вложения (10 МБ, inline в сообщениях + модальный preview для images/PDF/text)
- Колонка status хранится как VARCHAR (не PostgreSQL enum) для совместимости с asyncpg
- SLA-трекинг (first_response_at, resolved_at, working-hours pause)
- CSAT: оценка 1-5 через emoji в email → HTML-страница "Спасибо"
- Назначение агентам + bulk actions + merge дубликатов
- Источники: web, email, telegram, api, phone
- **Saved Views**: персональные фильтры агентов (личные / shared), счётчик usage_count
- **Parent-Child**: Incident → Problem связь, bulk-привязка инцидентов к проблеме
- **KB Article Links**: привязка статей БЗ к тикету (`helped`/`related`/`created_from`) + статистика (Deflection Rate)

### База знаний
- Категории + типы (FAQ / Guide)
- Статьи с поддержкой Markdown
- PostgreSQL FTS (to_tsvector + plainto_tsquery) + ILIKE fallback
- Live KB-suggestions при создании тикета
- AI-ассистент использует KB как RAG-контекст

### Проекты внедрения (v0.6 + v0.8)
- **ImplementationProject** → **ProjectPhase** → **ProjectTask** (иерархия)
- 4 шаблона проектов: Стандартный ЖК (10 фаз), Стандартный БЦ (9), Только камеры (5), Большая стройка (12)
- FSM статусов: draft → planning → in_progress ⇄ on_hold → completed/cancelled
- Автоматический пересчёт прогресса: `project.progress = weighted_avg(phase.progress * phase.weight)`, `phase.progress = done_tasks / active_tasks`
- Документы (contract/spec/act/diagram/photo/report), команда (5 ролей), комментарии (public/internal), события (audit log)
- Опциональная связь с тикетами через `Ticket.implementation_project_id` + флаг `is_implementation_blocker`
- Email-уведомления: создание проекта, смена статуса, завершение фазы, достижение milestone-задачи
- RBAC: property_manager видит только свой проект, support_agent/admin — все
- **Approvals (v0.8)**: `ProjectApproval` — утверждение фаз клиентом (pending/approved/rejected), email-уведомления, возврат фазы в in_progress при отклонении
- **Risk tracker (v0.8)**: `ProjectRisk` — severity/probability/impact, mitigation plan, статусы (open/mitigated/occurred/closed)
- **Template editor (v0.8)**: `ProjectTemplateDB` — шаблоны в БД вместо Python-констант, auto-seed, CRUD для админов
- **Analytics (v0.8)**: endpoint `/projects/analytics` — метрики, on-time rate, распределение по типам/статусам

### Авторизация и доступ
- JWT + bcrypt (без passlib — прямой bcrypt)
- 4 роли: resident, property_manager, support_agent, admin
- Self-registration только для resident/property_manager
- Row-level security: резиденты видят только свои тикеты; агенты — все
- Внутренние комментарии скрыты от не-staff
- **Password reset**: forgot-password → email со ссылкой (SHA-256 token, 60 мин TTL) → reset-password

### Агентские инструменты
- Колокольчик с polling-уведомлениями о новых ответах клиентов
- Dashboard: мои метрики (назначено/открыто/решено/CSAT) + таблица агентов
- Шаблоны ответов + макросы (одна кнопка)
- CSV-экспорт для Excel (BOM + UTF-8)

### CRM-интеграция (Bitrix24 + DaData)
- **Bitrix24** (pass24pro.bitrix24.ru): синхронизация компаний и контактов по ИНН
  - ИНН из `crm.requisite.list` (поле `RQ_INN`)
  - Компании → Customer, контакты → User (property_manager)
  - Фоновая синхронизация: `POST /customers/sync`
- **DaData** (suggestions.dadata.ru): поиск по ИНН и названию из ФНС
  - `findById/party` — точный поиск по ИНН
  - `suggest/party` — fuzzy поиск по названию
  - Автозаполнение: название, КПП, ОГРН, адрес, директор, ОПФ
- **CustomerSelect** (переиспользуемый Vue-компонент):
  - Autocomplete по синхронизированным компаниям
  - Если мало результатов → авто-fallback на DaData (реестр ФНС)
  - Кнопка «+» → создание по ИНН из DaData

### Каналы связи (omnichannel)
- Web portal (авторизованный + guest flow)
- Email (support@pass24online.ru): IMAP polling, ответы по тегу `[PASS24-xxxxxxxx]`; идемпотентность через `ticket_comments.email_message_id` + unique partial index (ADR-010)
- Telegram (@PASS24bot): webhook-бот (bot v2, aiogram 3) — см. раздел «Telegram-канал» ниже
- AI Assistant (Claude + Qdrant RAG): подсказки, поиск по KB

### Telegram-канал (`backend/telegram/`)

Полноценный menu-driven бот на **aiogram 3**, интегрированный в FastAPI через webhook (ADR-011).

- **Webhook:** `POST /telegram/webhook/{secret}` → `dp.feed_update(bot, update)` (`backend/telegram/webhook.py`).
- **FSM storage:** PostgreSQL (таблица `telegram_fsm_state`, без Redis) — `backend/telegram/storage.py`.
- **Account linking:** deep link с одноразовым токеном (TTL 10 мин), таблица `telegram_link_tokens`, миграция ghost-пользователей от старого бота — `backend/telegram/services/linking.py`.
- **Flows:** создание заявок (wizard: продукт → категория → описание → KB-deflection → impact/urgency → подтверждение), «мои заявки» с фильтрами и пагинацией, карточка с комментариями, ответы/закрытие/CSAT, KB-поиск, AI-чат (RAG через `assistant/rag.py`), PM-workspace (проекты + approvals), настройки уведомлений.
- **Push-уведомления:** `backend/telegram/services/notify.py` (прямой httpx в Bot API, с retry и авто-отвязкой при 403 Forbidden).
- **Compat mode:** `TELEGRAM_COMPAT_MODE` в `backend/telegram/config.py` — на время rollout unlinked-пользователи продолжают работать по старому text-flow (`backend/telegram/handlers/compat.py`). Флаг вручную переводится в False после периода адаптации.
- **Bot API reverse-proxy:** опциональная `TELEGRAM_API_BASE` (`backend/telegram/config.py`) — база для `TelegramAPIServer.from_base(...)` в `aiogram.AiohttpSession`. Используется там, где прямой исходящий трафик до `api.telegram.org` (149.154.160.0/20) заблокирован провайдером. Прокси обязан сохранять путь `/bot<token>/<method>` и `/file/bot<token>/<path>`. Переменная также подхватывается `services/notify.py` для push-уведомлений (прямые httpx-вызовы) — это отдельный путь от aiogram session, но конфиг один. Референсная реализация прокси — `ops/tg-proxy/` (nginx + docker-compose), разворачивается на VPS вне RU-блокировки; `TELEGRAM_API_BASE=http://<proxy-host>:8080/telegram`.

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
│   ├── models.py             # Ticket (SLA, CSAT, has_unread_reply, merged_into, parent_ticket_id), TicketEvent, TicketComment, Attachment
│   ├── templates.py          # ResponseTemplate, Macro, SavedView, TicketArticleLink
│   ├── schemas.py, router.py # CRUD + bulk + merge + apply-macro + CSV export + dashboard
│   ├── templates_router.py   # /tickets/templates, /tickets/macros
│   ├── views_router.py       # /tickets/saved-views, /tickets/{id}/articles, /tickets/{id}/parent, /children
│   └── sla_watcher.py        # Фоновая проверка SLA + working-hours
├── knowledge/                # База знаний (FTS-поиск, slug)
│   ├── models.py, schemas.py, router.py
├── stats/                    # Аналитика
│   └── router.py             # /stats/overview, /stats/sla, /stats/agents
├── customers/                # Компании-клиенты (Bitrix24 + DaData)
│   ├── models.py             # Customer (inn, bitrix24_company_id, ...)
│   ├── router.py             # CRUD + search + sync + create-by-inn
│   ├── bitrix24_sync.py      # Синхронизация из Bitrix24 CRM по ИНН
│   └── dadata.py             # Поиск по ИНН/названию через DaData API
├── notifications/            # Email (Telegram переехал в backend/telegram/)
│   ├── email.py              # SMTP исходящие (notify_ticket_*)
│   └── inbound.py            # IMAP polling, ответы → комментарии + вложения
├── telegram/                 # Telegram bot v2 (aiogram 3, ADR-011)
│   ├── config.py             # TELEGRAM_COMPAT_MODE, deep-link TTL
│   ├── bot.py                # create_bot_and_dispatcher
│   ├── webhook.py            # POST /telegram/webhook/{secret} → dp.feed_update
│   ├── storage.py            # PostgresStorage для aiogram FSM
│   ├── handlers/             # start, tickets_create/list/reply, csat, kb, ai, projects, approvals, settings, compat, menu
│   ├── middlewares/          # auth (is_linked, compat_mode), logging, throttle
│   ├── services/             # linking, ticket_service, kb_service, ai_service, project_service, notify
│   ├── keyboards/            # common, main_menu, tickets, projects, approvals
│   ├── formatters.py         # HTML-форматирование карточек тикетов/статей/проектов
│   └── deflection.py         # KB-deflection для wizard'а создания
├── assistant/                # AI-помощник (Claude + Qdrant RAG)
│   ├── router.py, rag.py
├── projects/                  # Проекты внедрения (v0.6)
│   ├── models.py             # ImplementationProject, ProjectPhase, ProjectTask, ProjectDocument, ProjectTeamMember, ProjectEvent, ProjectComment
│   ├── schemas.py            # Pydantic-схемы
│   ├── router.py             # CRUD проектов + phases + tasks (+ FSM transition)
│   ├── workspace_router.py   # Documents, Team, Comments, Events, Ticket-link
│   ├── templates.py          # 4 pre-configured шаблона проектов
│   ├── services.py           # create_project_from_template, recalculate_progress
│   └── dependencies.py       # get_project_with_access (RBAC guard)
└── scripts/
    ├── sync_email_replies.py  # Ручная синхронизация пропущенных ответов
    └── cleanup_html_bodies.py # Бэкофилл: очистка HTML в description/comments

frontend/                     # Vue 3 SPA
├── src/
│   ├── pages/
│   │   ├── TicketsPage.vue           # Список с фильтрами, views, пагинацией
│   │   ├── TicketDetailPage.vue      # 2-колоночный layout: чат + сайдбар (shell ~220 строк)
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
│   │   ├── CategoryBadge.vue, ArticleCard.vue
│   │   └── ticket/                   # 18 компонентов детальной страницы тикета (v0.8)
│   │       ├── TicketConversation.vue    # Timeline чат-переписки
│   │       ├── TicketMessageBubble.vue   # Пузырь сообщения (клиент/агент/внутренний)
│   │       ├── TicketComposeArea.vue     # Поле ввода ответа + вложения
│   │       ├── TicketSidebar.vue         # Правая панель (контейнер секций)
│   │       ├── TicketStatusDropdown.vue  # Выпадающий список смены статуса
│   │       ├── TicketSlaProgress.vue     # Прогресс-бар SLA
│   │       ├── TicketAssignment.vue      # Назначение агента
│   │       ├── TicketInlineAttachments.vue # Вложения в строку сообщения
│   │       └── ... (TicketContactInfo, TicketObjectInfo, TicketClassification, etc.)
│   ├── composables/                  # Переиспользуемая логика (v0.8)
│   │   ├── useTicketConversation.ts  # Мерж комментариев + событий в timeline
│   │   ├── useTicketTransitions.ts   # Допустимые переходы статусов
│   │   ├── useTicketPreview.ts       # Предпросмотр вложений
│   │   └── useAgentTools.ts          # Агенты, шаблоны, макросы
│   ├── stores/                       # Pinia (auth, tickets, knowledge)
│   ├── api/client.ts                 # fetch wrapper с JWT
│   └── router/                       # vue-router с auth guard

migrations/versions/
├── 001_initial_schema.py             # Базовая схема
├── 002_add_fts_and_stats.py          # FTS + индексы
├── 003_sla_attachments_internal_comments.py
├── 004_has_unread_reply.py           # Флаг непрочитанных ответов
├── 005_templates_macros_notifications.py  # Шаблоны, макросы, merge
├── 006_telegram_chat_id.py           # Telegram chat_id на user
├── 007_saved_views_kb_links_parent.py # Saved views, KB links, parent_ticket_id
├── 008_kb_improvement_suggestions.py # KB improvement suggestions
├── 009_article_feedback.py           # Article helpful counters
├── 010_article_tags_synonyms.py      # Tags, synonyms, slug_aliases (JSONB + GIN)
├── 011_implementation_projects.py    # Проекты внедрения (7 таблиц + 2 поля в tickets)
├── 012_customers_bitrix24.py         # Customers + users.customer_id + tickets.customer_id
├── 013_password_reset_fields.py      # Password reset token + expires_at
├── 014_add_on_hold_engineer_visit.py # Статусы on_hold/engineer_visit + attachments.comment_id
├── 015_app_settings.py               # app_settings key-value (default assignee)
├── 016_project_approvals.py          # Утверждение фаз клиентом
├── 017_project_risks.py              # Риски проектов
└── 018_project_templates_db.py       # Шаблоны проектов в БД

tests/
├── test_full_suite.py                # Auth, Tickets, Comments, Attachments, KB, Stats (71 тест)
├── test_inbound_email_integration.py # Email inbound: создание тикетов, ответы, вложения (13 тестов)
├── test_tickets_models.py            # FSM transitions, auto-priority (unit)
├── test_projects_models.py           # Project FSM, progress calculation, templates (33 теста)
├── test_customers.py                 # Customer CRUD, RBAC, DaData, Bitrix24 sync (30 тестов)
└── test_password_reset.py            # Forgot/reset flow, token security (14 тестов)
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
DATABASE_URL, SECRET_KEY, APP_BASE_URL
SMTP_PASSWORD, SMTP_USER, IMAP_HOST
ANTHROPIC_API_KEY, ANTHROPIC_BASE_URL, ANTHROPIC_MODEL
OPENAI_API_KEY, OPENAI_BASE_URL
QDRANT_URL, QDRANT_API_KEY, QDRANT_COLLECTION
TELEGRAM_BOT_TOKEN, TELEGRAM_WEBHOOK_SECRET
TELEGRAM_API_BASE             # Optional reverse-proxy for api.telegram.org (RU hosts where Bot API is blocked)
BITRIX24_WEBHOOK_URL          # CRM sync: companies + contacts by INN
DADATA_API_KEY                # Company lookup by INN/name (ФНС registry)
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

### v0.5 — ✅ Завершён (2026-04-05)
- [x] Saved Views / persistent filters (личные + shared, usage_count)
- [x] Parent-Child (Incident → Problem) + bulk-link-to-parent
- [x] KB Article Links (связь статей с тикетами, helped/related/created_from)
- [x] Route ordering fix (specific paths перед /{ticket_id} catch-all)
- [x] HTML cleanup в inbound email (Яндекс Мобильная Почта отправляет single-part text/html)

### v0.6 — ✅ Завершён (2026-04-05)
- [x] Модуль проектов внедрения: Projects + Phases + Tasks + Documents + Team + Events
- [x] 4 шаблона проектов (ЖК, БЦ, камеры, большая стройка)
- [x] FSM transitions проекта с автоматическими датами
- [x] Автоматический пересчёт прогресса (phase.progress → project.progress)
- [x] Связь тикетов с проектами (implementation_project_id, is_implementation_blocker)
- [x] Email-уведомления (создание, статус, завершение фазы, milestone)
- [x] RBAC: PM видит свои проекты, PASS24 — все
- [x] UI: список проектов, Timeline фаз, карточки этапов с задачами, TabView детали

### v0.7 — ✅ Завершён (2026-04-06)
- [x] Интеграция Bitrix24 CRM: синхронизация компаний по ИНН (230 компаний, 489 контактов)
- [x] DaData API: поиск компании по ИНН и по названию (ФНС реестр)
- [x] Модель Customer + customers таблица (ИНН уникальный)
- [x] CustomerSelect компонент: autocomplete из своих + DaData fallback
- [x] Связь User↔Customer↔Ticket (customer_id)
- [x] Колонка «Компания» + поиск по компании в настройках пользователей
- [x] Тикет из статьи БЗ: skip Step 1, auto-link created_from, improvement suggestions
- [x] KB improvement suggestions (CRUD + admin workflow)
- [x] Руководства пользователей role-based (агент vs администратор)
- [x] Сброс пароля через email (forgot-password / reset-password)

### v0.8 (планируется) — Approvals & Risk Management
- [ ] Approvals workflow: PM подписывает завершение фазы / deliverable
- [ ] Risk tracker: управление рисками проекта (severity/probability/impact)
- [ ] Редактор шаблонов проектов в админке (из Python-констант → БД)
- [ ] Project analytics dashboard: Time-to-Go-Live, On-Time Delivery Rate

### v0.9 (планируется) — Gantt & Real-time
- [ ] Gantt chart (frappe-gantt / SVG), drag-n-drop сроков
- [ ] CRM webhook: Bitrix24 сделки → автосоздание проектов
- [ ] WebSocket real-time (замена polling)
- [ ] Push-уведомления / PWA

### v1.0 (будущее) — Scale & Optimization
- [ ] Multi-tenant isolation
- [ ] Budget tracking, Project cloning, Import/Export
- [ ] Mobile app для PM и монтажников

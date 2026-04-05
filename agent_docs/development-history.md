# История разработки

Правило: хранить только последние 10 записей. При добавлении новой переносить старые в
`agent_docs/development-history-archive.md`. Архив читать при необходимости.

---

Краткий журнал итераций проекта.

## Записи

### 2026-04-05 — Top-3 ROI: Saved Views, Parent-Child, KB Links + inbound HTML cleanup

**Что сделано:**
- **Saved Views / persistent filters** (`SavedView` модель): личные + shared фильтры агентов
  - CRUD-эндпоинты `/tickets/saved-views`, счётчик `usage_count` при применении
  - UI в TicketsPage: dropdown иконок (6 пресетов), Dialog создания, preview чипов
  - Watcher на фильтрах сбрасывает `activeSavedViewId` при ручной правке
- **Parent-Child связь** (`parent_ticket_id` на Ticket): Incident → Problem
  - `PUT/DELETE /tickets/{id}/parent`, `GET /tickets/{id}/children`
  - Массовая привязка: `POST /tickets/bulk-link-to-parent`
  - UI: секция "Связь с Problem" в TicketDetailPage (3 состояния: has parent / has children / regular)
- **KB Article Links** (`TicketArticleLink` модель): связь тикет ↔ статья
  - Типы отношений: `helped` / `related` / `created_from`
  - `GET/POST/DELETE /tickets/{id}/articles`, статистика `/tickets/articles/stats`
  - UI: секция "Связанные статьи" + Dialog поиска (debounced 300ms)
- **Route ordering fix**: `views_router` + `templates_router` регистрируются **ДО** `tickets_router`, потому что `GET /tickets/{ticket_id}` перехватывает все specific-пути (saved-views, templates, macros)
- **HTML cleanup в inbound email**: Яндекс Мобильная Почта отправляет single-part `text/html` → сырой HTML попадал в `description`
  - Добавлен `_HTMLToTextParser` (stdlib `html.parser`, без новых зависимостей)
  - Вырезает `<style>/<script>/<head>`, блочные теги → `\n`, HTML entities декодируются автоматически
  - Эвристика `_looks_like_html`: если text/plain содержит 3+ тегов или entities — тоже чистится
  - Скрипт бэкофилла `cleanup_html_bodies.py` (dry-run + --apply)

**Миграции:**
- 007: `saved_views`, `ticket_article_links`, `tickets.parent_ticket_id` + индексы

**Баги найденные:**
- `GET /tickets/saved-views` возвращал 404 — перехватывался `GET /tickets/{ticket_id}` (порядок регистрации роутеров в FastAPI)
- `_extract_text_body` в single-part ветке возвращал сырое тело без проверки content-type → HTML в description (заявка 9020)

**Обновления:**
- [x] Миграция 007 применена на prod
- [x] Интеграционные тесты Top-3 прошли (POST/GET/DELETE = 201/200/204)
- [x] HTML-парсер протестирован на реальных примерах Яндекс Мобильной Почты
- [x] Документация обновлена (architecture.md: Saved Views, Parent-Child, KB Links, v0.5 в roadmap)

**Коммиты:**
- `01737db` feat: saved views + KB article links + parent-child
- `d2e15ed` feat: saved views UI + parent-child + KB links UI
- `9b70430` fix: route ordering — specific paths before /{ticket_id} catch-all
- `d4dc0c8` fix: clean HTML from inbound email body
- `8def583` feat: script to cleanup HTML in existing tickets/comments

---

### 2026-04-05 — Агентские инструменты, дашборд, макросы, Telegram-бот, working-hours SLA

**Что сделано:**
- Auto-transition статусов по комментариям:
  - Агент → публичный комментарий = WAITING_FOR_USER
  - Клиент → ответ = IN_PROGRESS
- Флаг `has_unread_reply` + колокольчик уведомлений для staff
  - Polling каждые 20 сек, тихий звуковой сигнал при новом уведомлении
  - Dropdown со списком тикетов, требующих внимания
- Назначение тикетов агентам (`assignee_id`): "Взять себе" + dropdown всех агентов
- Массовые действия (bulk): выбор нескольких тикетов → смена статуса/назначения/удаления
- Шаблоны ответов (`response_templates`): быстрая вставка в комментарий, счётчик использования
- Макросы (`macros`): одна кнопка = статус + комментарий + назначение
- Merge дубликатов: слияние тикетов с переносом комментариев/вложений
- CSV-экспорт тикетов (BOM + UTF-8 для Excel)
- Дашборд агента (`/dashboard`): мои метрики + таблица всех агентов с CSAT
- SLA watcher (фоновая задача каждые 5 мин): email админам за 30 мин до нарушения
- Working-hours SLA: SLA не тикает ночью и в выходные (пн-пт 9-18 МСК)
- KB-suggestions при создании тикета: live-поиск статей по теме (debounce 400ms)
- CSAT one-click rating из email: клик на смайлик → HTML-страница "Спасибо"
- Telegram-бот @PASS24bot (webhook): приём тикетов из Telegram
- Разделение кода страны и цифр в phone input (26 стран с флагами)

**Миграции:**
- 004: `has_unread_reply` на tickets
- 005: таблицы `response_templates`, `macros`; `sla_breach_warned`, `merged_into_ticket_id`

**Баги найденные:**
- Alembic upgrade зависал в FastAPI startup (async loop конфликт) → убрали автомиграцию, применяется вручную
- IMAP auth failed после rate-limit от Timeweb → пароль корректный, нужна пауза
- 401 на скачивание вложений: браузер не шлёт JWT при `<a href>` → модалка с fetch+blob

**Обновления:**
- [x] Миграции 004, 005 применены
- [x] Тестов: 84 (71 suite + 13 inbound) pass на production
- [x] Cleanup fixtures в тестах (авто-удаление @example.com)

**Метрики после очистки БД:**
- 26 реальных пользователей (было 179)
- 17 реальных тикетов (было 101)

---

### 2026-04-04 — ITIL-поля, CSAT, умный inbound email

**Что сделано:**
- ITIL-поля на тикете: `impact`, `urgency`, `assignment_group`, `assignee_id`
- CSAT: оценка 1-5 + комментарий + timestamps (`satisfaction_*`)
- CSAT-запрос автоматически при переходе в resolved (5 emoji в email)
- Расширение классификации тикетов: 5-осевая (product, category, type, source, status)
- Email-ответы с тегом `[PASS24-xxxxxxxx]` → комментарий к тикету
- Fallback: ответы без тега (`Re: ...`) → поиск тикета по теме + email
- Сохранение вложений из email
- Авто-анализ тикетов: FTS-поиск по базе знаний → ссылки в email
- RBAC: резиденты/УК видят только свои тикеты
- Регистрация — только `resident`/`property_manager` (SUPPORT_AGENT/ADMIN назначает админ)
- Отдельная кнопка «Вход для агентов техподдержки» на login-странице
- Создание тикетов агентами от имени клиента (`on_behalf_of_*`)

**Следующие шаги:**
- ~~Агентские инструменты (dashboard, templates, macros)~~ — сделано 2026-04-05

---

### 2026-04-03 — Vue 3 SPA frontend + email-уведомления + inbound email

**Что сделано:**
- Vue 3 SPA frontend (`frontend/`): Vite + TypeScript + PrimeVue 4 (Aura) + Pinia
  - Auth: LoginPage, RegisterPage, auth store (JWT persist)
  - Tickets: TicketsPage (DataTable, фильтры, пагинация), CreateTicketPage, TicketDetailPage (timeline, комментарии, FSM кнопки)
  - Knowledge: KnowledgePage (поиск с debounce, grid), ArticlePage (markdown render, slug)
  - Компоненты: TicketStatusBadge, TicketPriorityBadge, CategoryBadge, ArticleCard
  - Router с auth guard, SPA fallback в FastAPI
- Multi-stage Dockerfile: Node build → Python API + static serving
- Email-уведомления (исходящие, SMTP):
  - Создание тикета → email создателю
  - Смена статуса → email создателю (с указанием кто изменил)
  - Новый комментарий → email создателю (если комментирует не он)
  - SMTP: smtp.timeweb.ru:465 SSL, support@pass24online.ru
  - Async через BackgroundTasks (не блокирует API)
- Приём входящей почты (IMAP polling):
  - Чтение UNSEEN писем каждые 60 сек (imap.timeweb.ru:993)
  - Парсинг темы/тела → определение категории по ключевым словам
  - Достаточно информации → автосоздание тикета + ответ-подтверждение
  - Недостаточно информации → ответ с запросом уточнений
  - Авто-создание пользователя из email отправителя
  - Защита от петель: собственные письма и auto-reply пропускаются

**Обновления:**
- [x] Документация обновлена
- [x] Тесты: 14 unit, SMTP/IMAP проверены на production

**Следующие шаги:**
- Alembic миграции
- Полнотекстовый поиск (PostgreSQL FTS)
- Аналитика и дашборды

---

### 2026-04-03 — Полный backend: auth, tickets DB, knowledge base, деплой

**Что сделано:**
- Создан модуль аутентификации (`backend/auth/`): JWT-токены, bcrypt-хеширование, RBAC (4 роли: resident, property_manager, support_agent, admin)
- Переписан модуль тикетов на SQLModel + PostgreSQL: пагинация, фильтрация, комментарии, аудит-трейл событий; сохранена бизнес-логика (автоприоритет, FSM)
- Создан модуль базы знаний (`backend/knowledge/`): CRUD статей, полнотекстовый поиск (ILIKE), транслитерация slug, ролевой доступ
- Общая инфраструктура: `config.py` (pydantic-settings + .env), `database.py` (async PostgreSQL), CORS, healthcheck
- Docker: compose с PostgreSQL 16, Dockerfile с healthcheck и non-root user
- Юнит-тесты расширены до 14 (автоприоритет, FSM, события)
- Деплой на VPS (5.42.101.27): CI/CD через GitHub Actions, БД `pass24_servicedesk` на существующем `pass24-postgres`
- Интеграционный тест: 25/25 pass на production

**Баги найденные при деплое:**
- passlib несовместим с bcrypt 5.x → заменён на прямой `bcrypt` (ADR-002)
- UUID из User.id не конвертировался в str для Ticket.creator_id → добавлен `str()`
- SQLModel Relationship ломается с `from __future__ import annotations` на Python 3.9 → использованы строковые forward references

**Обновления:**
- [x] Документация обновлена
- [x] ADR-002 создан (bcrypt vs passlib)
- [x] Тесты: 14 unit + 25 integration

**API endpoints (20):**
- AUTH: POST /auth/register, POST /auth/login, GET /auth/me
- TICKETS: POST/GET /tickets/, GET /tickets/{id}, POST /tickets/{id}/status, POST /tickets/{id}/comments, DELETE /tickets/{id}
- KNOWLEDGE: GET /knowledge/, GET /knowledge/search, GET /knowledge/{slug}, POST/PUT/DELETE /knowledge/
- SYSTEM: GET /health, GET /docs

**Следующие шаги:**
- Vue 3 SPA frontend (замена Jinja2 mockup)
- Email-уведомления при смене статуса тикета
- Alembic миграции для управления схемой БД

---

### 2026-03-04 — Инициализация проекта и заполнение документации

**Что сделано:**
- Заполнен блок описания проекта в `AGENTS.md` (PASS24 Service Desk — Help Desk портал для PASS24.online)
- Написана начальная архитектура в `agent_docs/architecture.md` (роли, компоненты, потоки данных, roadmap)
- Обновлён `README.md` под реальный проект
- Определены роли пользователей: резидент, администратор УК, агент поддержки, администратор
- Определён MVP-scope: тикеты + база знаний

**Почему:**
- Необходимо зафиксировать контекст проекта до начала разработки, чтобы AI-агенты и разработчики имели единую точку правды

**Обновления:**
- [x] Документация обновлена
- [x] ADR: технологический стек зафиксирован (ADR-001)
- [ ] Тесты: не применимо (нет кода)

**Следующие шаги:**
- Настроить окружение разработки (проект Vue + FastAPI)
- Начать реализацию MVP (авторизация → тикеты → база знаний)

---

### 2026-03-04 — Выбор технологического стека (ADR-001)

**Что сделано:**
- Зафиксирован стек: Python 3.12 + FastAPI, SQLModel, PostgreSQL 16, Vue 3 + TypeScript, PrimeVue, Pinia, vue-echarts
- Redis убран из стека (не требуется на MVP)
- Фоновые задачи: crontab + FastAPI BackgroundTasks
- Создан ADR-001 в `agent_docs/adr.md`
- Обновлены `architecture.md` и `AGENTS.md`

**Почему:**
- FastAPI — async, автодокументация, SQLModel совмещает валидацию и ORM
- Vue 3 + PrimeVue — богатый набор enterprise-компонентов для портала поддержки
- Redis отложен — BackgroundTasks достаточно для MVP

**Обновления:**
- [x] Документация обновлена
- [x] ADR-001 создан
- [ ] Тесты: не применимо (нет кода)

**Следующие шаги:**
- Инициализировать проекты (backend + frontend)
- Настроить окружение разработки
- Начать MVP: модели данных → API → UI
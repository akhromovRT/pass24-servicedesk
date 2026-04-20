# История разработки

Правило: хранить только последние 10 записей. При добавлении новой переносить старые в
`agent_docs/development-history-archive.md`. Архив читать при необходимости.

---

Краткий журнал итераций проекта.

## Записи

### 2026-04-20 — fix: SMTP guard на зарезервированные домены + ужесточение ops-run-tests

**Инцидент:** ручной запуск workflow `Ops — run pytest on prod` с расширенным target прогнал интеграционные тесты против прод-БД. Фикстуры создали десятки тикетов с адресами `test-<hex>@example.com`, приложение отослало notify-письма через SMTP timeweb, и 36+ bounce-писем упало в inbox `support@pass24online.ru`.

**Что сделано:**
- `backend/notifications/email._send_email` — guard: молча пропускает получателей на RFC 2606/6761 зарезервированных доменах (`example.com/net/org`, `.example`, `.test`, `.invalid`, `.localhost`) с INFO-логом.
- `tests/test_email_reserved_guard.py` — 22 unit-теста.
- `.github/workflows/ops-run-tests.yml` — allowlist конкретных файлов, whole-suite прогон и пустой target запрещены.
- Из прод-БД удалены 2 старых закрытых тест-тикета (`itil-test@example.com`, `test@example.com`) и их события.
- ADR-012 зафиксировал правило «не слать SMTP на reserved-домены».

**Файлы:** `backend/notifications/email.py`, `tests/test_email_reserved_guard.py`, `.github/workflows/ops-run-tests.yml`, `agent_docs/adr.md`.

### 2026-04-17 — feat: Telegram Bot v2 (ветка `feature/telegram-bot-v2`)

Переписан Telegram-бот с минимального text-only интерфейса (390 строк на raw httpx) в полнофункциональный menu-driven канал на aiogram 3.

**Масштаб:** 14 задач по плану `docs/superpowers/plans/2026-04-17-telegram-bot-v2.md`, ~2500 строк в `backend/telegram/`, 11+ коммитов.

**Ключевые компоненты:**
- aiogram 3 + `PostgresStorage` для FSM (таблица `telegram_fsm_state`, без Redis)
- Deep link account binding (`telegram_link_tokens`, TTL 10 мин) с ghost-миграцией тикетов/комментариев/событий от старого бота
- Wizard создания заявок: продукт → категория → описание → KB-deflection → impact/urgency → подтверждение
- Список «мои заявки» с фильтрами (active/all/closed) и пагинацией, карточка с комментариями
- Ответы / закрытие / CSAT flow с inline-кнопками
- KB-поиск и AI-чат (RAG через `assistant/rag.py`)
- PM-workspace: проекты, фазы, approvals (утверждение/отклонение с причиной)
- Push-уведомления с inline-кнопками + авто-отвязка аккаунта при 403 от Bot API
- Настройки уведомлений (7 тумблеров в `User.telegram_preferences`), отвязка аккаунта
- Compat mode (`TELEGRAM_COMPAT_MODE` в `backend/telegram/config.py`) на 2 недели для unlinked-пользователей через `backend/telegram/handlers/compat.py` — ghost-flow из старого бота портирован 1-в-1

**Миграция:** `023_telegram_bot_v2.py` (после конфликта с 021/022 в main — ветка ребейзнута).

**Удалено:** `backend/notifications/telegram.py` (функционал перенесён).

**ADR:** ADR-011.

**Тесты:** `tests/test_telegram_bot.py` (PostgresStorage + pure-unit formatters/keyboards + linking integration), `tests/test_telegram_webhook.py` (smoke integration: 403 на wrong secret, 200 на минимальный update, ghost-ticket в compat mode, /start для linked-юзера).

**Follow-up TODO (отдельный PR):**
- Подключить продьюсеры уведомлений для approval-запросов, milestones и risks (сейчас в `notify.py` есть отправка, но триггеры на стороне `backend/projects/` ещё не вызывают).
- Персист `ArticleFeedback` (👍/👎 на KB-статьях из бота) — модель есть, handler ещё не пишет в БД.

### 2026-04-17 — fix: идемпотентность inbound email — один Message-ID = один комментарий

**Проблема:** В тикетах (пример #D6393659) дублируются клиентские сообщения из email-ответов. Корневая причина — единственной защитой от повторной обработки был in-memory `set _processed_message_ids` в процессе воркера:
- Любой рестарт обнуляет set → IMAP-polling проходит `SINCE = 2 дня` и создаёт повторные комментарии.
- На 501-м уникальном Message-ID выполнялся опасный `set.clear()` — не LRU, а полный сброс.
- Письма без `Message-ID` не добавлялись в set, то есть обрабатывались каждые 60 сек.
- `_handle_reply` / `_handle_reply_by_subject` не имели никакой идемпотентности на стороне БД.

**Что сделано:**
- Миграция `022_ticket_comment_email_message_id.py`: колонка `ticket_comments.email_message_id VARCHAR(998) NULL` + частичный unique-индекс `WHERE email_message_id IS NOT NULL`. Авторитетная защита от дублей теперь в БД.
- `_fetch_unseen_emails` передаёт `message_id` в `mail_data`; для писем без заголовка генерируется стабильный synthetic `<synthetic-sha1(from+date+subject+body)@pass24-local>`.
- `_handle_reply` и `_handle_reply_by_subject` пишут `email_message_id` в комментарий, делают `session.flush()` и ловят `IntegrityError` **до** записи вложений на диск — дубль не создаёт orphan-файлов. Возвращают `True`, чтобы polling не скатывался в ветку создания нового тикета.
- In-memory кеш переведён на `OrderedDict`-LRU (обрезает самый старый при превышении 500), `.clear()` на 500 удалён.
- Интеграционные тесты: повторный вызов с тем же `message_id` оставляет 1 комментарий и не создаёт повторное вложение.
- Backfill-скрипт `backend/scripts/dedup_ticket_comments.py` для чистки уже накопленных дублей в старых тикетах (группирует по `(author_id, text.strip())`, оставляет самый ранний; `--dry-run`, `--ticket <prefix>`, `--all`).

**Follow-up (коммит `51f4f02`):** live smoke-тест на проде вскрыл `MissingGreenlet` в моём же guard'е — после `session.rollback()` SQLAlchemy экспирит ORM-атрибуты, и форматирование лог-строки с `ticket.id[:8]` триггерило lazy-reload в asyncpg без greenlet. Unique-индекс рабоал корректно, падала сама диагностика. Пофикшено кешированием префикса в локальную строку до flush.

**Прод-чистка:** `dedup_ticket_comments.py --all` удалил 98 дублей в 11 тикетах (оставлен 121 оригинал). Повторный `--dry-run` → 0 дублей. Smoke-тест идемпотентности на живом тикете: 2 вызова `_handle_reply` с одним `message_id` → 1 комментарий в БД.

**Архитектурное решение:** `agent_docs/adr.md` ADR-010 — идемпотентность inbound email через unique-индекс в БД.

**Файлы:** `migrations/versions/022_ticket_comment_email_message_id.py`, `backend/tickets/models.py`, `backend/notifications/inbound.py`, `backend/scripts/dedup_ticket_comments.py`, `tests/test_inbound_email_integration.py`, `agent_docs/adr.md`, `agent_docs/architecture.md`

### 2026-04-17 — feat: message-driven SLA pause

**Что сделано:**
- SLA «Решение» теперь автоматически встаёт на паузу, когда последний публичный комментарий в тикете — от сотрудника поддержки, и снимается при ответе клиента. Статус при этом не меняется.
- Новые поля `Ticket.sla_paused_by_status` / `sla_paused_by_reply` + единый метод `recompute_sla_pause` с OR-семантикой. `transition` и `on_public_comment_added` — единственные точки, которые обновляют флаги.
- Интеграция во все 5 путей создания публичного комментария: web (`add_comment`, macros), email (`_handle_reply`, `_handle_reply_by_subject`), Telegram.
- Фикс скрытого бага в `sla_watcher`: активная пауза теперь учитывается в расчёте дедлайна (раньше watcher мог ложно предупреждать, пока тикет на паузе по статусу/reply).
- UI: в `TicketSlaProgress.vue` добавлен бейдж «⏸ SLA на паузе — ждём ответ клиента» / «статус «{label}»» с серой заливкой прогресс-бара.
- Миграция `021_add_sla_pause_flags.py` + backfill `paused_by_status` из текущих статусов; `paused_by_reply` исторически оставляем `false`.
- Регламент `support-operations.md` обновлён: ручной перевод в «Ожидает ответа» больше не обязателен для паузы.

**Файлы:**
- Backend: `backend/tickets/models.py`, `schemas.py`, `router.py`, `sla_watcher.py`, `notifications/inbound.py`, `notifications/telegram.py`
- Frontend: `TicketSlaProgress.vue`, `types/index.ts`
- Миграция: `021`
- Тесты: `test_tickets_models.py`, `test_inbound_email_integration.py`, new `test_sla_watcher.py`
- Документация: `agent_docs/guides/support-operations.md`
- Spec: `docs/superpowers/specs/2026-04-17-message-driven-sla-pause-design.md`
- Plan: `docs/superpowers/plans/2026-04-17-message-driven-sla-pause.md`

### 2026-04-17 — fix: вложения из email-ответов отображаются внутри пузыря сообщения

**Проблема:** Вложения, отправленные клиентом в ответном письме на тикет, не отображались в переписке рядом с сообщением — попадали в «описание тикета» в самом верху (или визуально «исчезали» из контекста ответа).

**Первопричина:** После редизайна UI 7 апреля (v0.8 Phase 1) вложения отображаются inline внутри пузыря сообщения по полю `Attachment.comment_id`. Однако функция `_save_attachment` в `backend/notifications/inbound.py` не принимала `comment_id`, и обработчики `_handle_reply` / `_handle_reply_by_subject` не передавали его при сохранении вложений из ответных email. В итоге у всех таких вложений `comment_id = NULL`, и фронтенд (`TicketConversation.vue`) показывал их как вложения описания тикета.

**Что сделано:**
- `_save_attachment(...)` получил необязательный параметр `comment_id: Optional[str] = None` и пишет его в модель `Attachment`.
- `_handle_reply` / `_handle_reply_by_subject` создают `TicketComment` также при пустом теле, если есть вложения (чтобы было к чему привязать), и передают `comment.id` в `_save_attachment`. `TicketComment.id` доступен сразу после конструктора благодаря `default_factory=uuid4`.
- Обработчик создания нового тикета из email оставлен без изменений — там вложения корректно относятся к описанию (`comment_id=None`).
- Тест `test_reply_with_attachment` в `tests/test_inbound_email_integration.py` расширен: проверяет, что `attachment.comment_id == comment.id`.

**Файлы:** `backend/notifications/inbound.py`, `tests/test_inbound_email_integration.py`

### 2026-04-09 — v0.8 Phase 2: Approvals, Risks, Templates, Analytics

**Что сделано:**
- **Approvals workflow**: модель `ProjectApproval` (pending/approved/rejected), API endpoints запроса/утверждения/отклонения, email-уведомление клиенту, компонент `PhaseApproval.vue` с бейджами и кнопками
- **Risk tracker**: модель `ProjectRisk` (severity/probability/impact/mitigation/status), CRUD API, компонент `RiskPanel.vue` с цветовыми карточками, создание/редактирование/удаление
- **Template editor**: модель `ProjectTemplateDB` — шаблоны проектов в БД вместо Python-констант, auto-seed из существующих шаблонов, CRUD API (admin only), soft delete
- **Project analytics**: endpoint `GET /projects/analytics` — метрики: total/active/completed, средняя длительность, on-time delivery rate, распределение по типам/статусам, открытые риски, ожидающие утверждения
- **Миграции**: 016 (project_approvals), 017 (project_risks), 018 (project_templates_db)

**Также исправлено (7-8 апреля):**
- Обрезание email-писем в комментариях (убран лимит 4000, сохраняются цитирования)
- Спам-фильтр: заменили `PASS24.online` на `PASS24` в шаблонах писем
- HTML-теги в text/plain от Яндекс Почты (снижен порог детекции с 3 до 1 тега)
- Кнопка «Взять себе» не сохраняла назначение (UI не вызывал API)
- Настройка «Назначать новые заявки на» в разделе Настройки → Заявки
- Вкладка по умолчанию — «Открытые» вместо «Все»

**Файлы:**
- Backend: `projects/models.py`, `projects/router.py`, `projects/workspace_router.py`
- Frontend: `PhaseApproval.vue`, `RiskPanel.vue`, `types/index.ts`
- Миграции: 016-018
- Spec: `docs/superpowers/specs/2026-04-09-v08-approvals-risks-templates-analytics.md`

### 2026-04-07 — v0.8 Phase 1: Редизайн интерфейса агента

**Что сделано:**
- **Новые статусы FSM**: добавлены `on_hold` (Отложена) и `engineer_visit` (Выезд инженера) к существующим 5 статусам → 7 статусов
  - `on_hold`: SLA ставится на паузу (как waiting_for_user)
  - `engineer_visit`: SLA продолжает тикать (работа идёт, но offsite)
  - Миграция: `014_add_on_hold_engineer_visit_statuses.py`
- **Автостатус**: первый ответ агента теперь переводит тикет `new → in_progress` (было → waiting_for_user)
  - Агент сам решает когда ставить waiting_for_user через ручной dropdown
- **2-колоночный layout**: TicketDetailPage.vue переписан с 2196 строк до ~220 строк shell
  - Центр: чат-переписка с пузырями сообщений (TicketConversation, TicketMessageBubble, TicketComposeArea)
  - Правый сайдбар 380px: статус dropdown, SLA, назначение, контакт, объект, техинфо, связи
  - 18 новых компонентов в `frontend/src/components/ticket/`
  - 4 composables в `frontend/src/composables/`
- **Inline-вложения**: attachments привязываются к comment_id, отображаются внутри пузырей сообщений
  - Thumbnail для изображений, chips для файлов
- **Email threading**: тег PASS24-xxx добавлен в тело письма + In-Reply-To/References заголовки
  - Inbound: проверка body перед fallback на subject → тройная защита
- **Дефолтная сортировка**: для агентов теперь `created_desc` (новые первые) вместо SLA
- **Вкладка «Выезды»**: добавлена для фильтрации тикетов со статусом engineer_visit

**Файлы:**
- Backend: `models.py`, `router.py`, `schemas.py`, `email.py`, `inbound.py`, `sla_watcher.py`
- Frontend: `TicketDetailPage.vue`, `TicketStatusBadge.vue`, `TicketsPage.vue`, `types/index.ts`
- Новые: 18 компонентов `ticket/`, 4 composables, 1 миграция
- Spec: `docs/superpowers/specs/2026-04-07-agent-interface-redesign.md`

### 2026-04-06 — Стабилизация v0.7: тесты + roadmap sync

**Что сделано:**
- **Roadmap** (`agent_docs/roadmap.md`): синхронизирован с реальностью — CRM = v0.7 (факт), Approvals → v0.8, Gantt → v0.9, Scale → v1.0
- **Docstring fix** (`migrations/versions/012_customers_bitrix24.py`): исправлена копипаста Revision 009→012, Revises 008→011
- **30 новых тестов** для `backend/customers/` (`tests/test_customers.py`):
  - RBAC: agent видит всё, admin видит всё, PM — только свою компанию, resident — пусто, 401 без авторизации
  - Search: по названию, по ИНН, пустой результат
  - CRUD: создание (агент), 409 на дубликат ИНН, 403 для resident/PM
  - Create-by-INN: реальный DaData API (Газпром), fallback без DaData, 403 для resident
  - DaData endpoints: lookup по ИНН (Сбербанк), 404 при не найден, search по названию
  - Contacts: получение контактов компании, пустой список
  - Bitrix24 sync: admin-only, 403 для agent/resident
  - Unit-тесты: _parse_suggestion (полный/минимальный), lookup/search без API-ключа
- **14 новых тестов** для password reset (`tests/test_password_reset.py`):
  - forgot-password: валидный email (проверка токена в БД), 404, 403 inactive, 422 invalid format
  - reset-password: валидный токен, 400 invalid, 400 expired, 422 short password, one-time use
  - Full cycle: token → reset → login с новым паролем, 401 со старым
  - Unit-тесты: create_reset_token, hash_reset_token deterministic, create+hash match, uniqueness

**Итого тестов в проекте:** 44 новых + существующие (test_full_suite, test_inbound_email, test_projects_models, test_tickets_models)

**Smoke-тест на проде (Playwright):**
- [x] База знаний: 42 статьи, 6 категорий, теги, поиск
- [x] Логин/выход, ссылка «Забыли пароль?»
- [x] Страница /forgot-password: форма email + «Отправить ссылку»
- [x] Заявки: 35 тикетов, фильтры, SLA-таймеры
- [x] Создание заявки: wizard (9 категорий), форма с CustomerSelect (autocomplete + «+»)
- [x] Проекты внедрения: страница, фильтры, кнопка создания
- [x] Настройки: почта SMTP/IMAP, Telegram, Пользователи с колонкой «Компания»
- [x] Дашборд агента, Аналитика (графики)

**Cleanup:** удалено 127 тестовых юзеров (@example.com) из prod БД + тестовые customers (INN LIKE 'TEST%')

**Обновления:**
- [x] Все 44 тестов проходят на production
- [x] Roadmap обновлён
- [x] architecture.md: миграции 010-013, тесты, password reset, roadmap v0.8-v1.0
- [x] Документация обновлена

---

### 2026-04-06 — v0.7: Интеграция Bitrix24 CRM + DaData + компании-клиенты

**Что сделано:**
- **Модель `Customer`** (`customers` таблица): ИНН (уникальный), название, bitrix24_company_id, адрес, телефон, email
- **Синхронизация с Bitrix24** (`backend/customers/bitrix24_sync.py`):
  - ИНН берётся из `crm.requisite.list` (поле `RQ_INN`)
  - Компании: 232 → 230 синхронизировано (2 без ИНН пропущены)
  - Контакты: 904 → 487 создано, 26 обновлено (привязаны к компаниям как property_manager)
  - ID-based пагинация для полной выгрузки (>50 записей)
  - `POST /customers/sync` (admin-only, background task)
- **DaData интеграция** (`backend/customers/dadata.py`):
  - `lookup_by_inn()` → findById: название, КПП, ОГРН, адрес, директор, ОПФ, статус
  - `search_by_name()` → suggest: поиск по названию, top-5 ACTIVE
  - `GET /customers/lookup-inn/{inn}` и `GET /customers/dadata-search?q=`
  - `POST /customers/create-by-inn?inn=` → автосоздание из DaData
- **CustomerSelect.vue** — переиспользуемый компонент autocomplete:
  - Двухуровневый поиск: сначала среди своих (Bitrix24), затем DaData (ФНС)
  - Если <3 результатов из своих и query >= 3 символов → авто-подгрузка из DaData
  - Кнопка «+» → dialog ввода ИНН → preview из DaData → создание
  - Встроен в CreateTicketPage (секция «Компания-клиент»)
- **Связь User↔Customer**: `users.customer_id`, `tickets.customer_id` — привязка автоматическая
- **Колонка «Компания»** в SettingsPage → Пользователи и агенты
- **Поиск по компании** (`GET /auth/users?q=АЛЬФА`) — ищет по ФИО, email И названию компании
- **Route ordering fix** для `/customers/search`, `/dadata-search`, `/lookup-inn`
- **Руководства пользователей** — role-based: «Руководство агента» vs «Руководство администратора» (3 доп. раздела для admin)
- **Тикет из статьи БЗ**: кнопка «Не помогло → создать заявку» → skip Step 1, auto-link `created_from`, improvement suggestions при закрытии
- **KB improvement suggestions** (таблица + CRUD): агенты предлагают улучшения статей

**Миграции:**
- 008: `kb_improvement_suggestions`
- 009 (→012): `customers`, `users.customer_id`, `tickets.customer_id`
- 013: `users.password_reset_token/expires_at`

**Env переменные добавлены:**
- `BITRIX24_WEBHOOK_URL` = `https://pass24pro.bitrix24.ru/rest/1/k8s07s2shaitmhmy/`
- `DADATA_API_KEY` = подключён

**Обновления:**
- [x] Миграции 008-013 применены на prod
- [x] Первая полная синхронизация Bitrix24 выполнена (230 компаний, 489 контактов)
- [x] DaData проверена: Сбербанк (7707083893), Газпром (7736050003) — ОК

---

### 2026-04-05 — v0.6: Модуль «Проекты внедрения клиентов»

**Что сделано:**
- **Новый домен** `backend/projects/` с 7 таблицами: ImplementationProject, ProjectPhase, ProjectTask, ProjectDocument, ProjectTeamMember, ProjectEvent, ProjectComment
- **Миграция 010**: создание всех таблиц + добавление `implementation_project_id` и `is_implementation_blocker` в `tickets`
- **FSM проекта**: DRAFT → PLANNING → IN_PROGRESS ⇄ ON_HOLD → COMPLETED/CANCELLED, с автоматическим заполнением `actual_start_date/actual_end_date`
- **Автопересчёт прогресса**: `phase.progress = done_tasks / active_tasks × 100` (cancelled исключаются), `project.progress = Σ(phase.progress × weight) / Σ(weight)` (skipped-фазы исключаются)
- **4 шаблона** проектов в `templates.py`: Стандартный ЖК (10 фаз, 91 день), Стандартный БЦ (9, 66), Только камеры (5, 28), Большая стройка (12, 143)
- **RBAC через dependency** `get_project_with_access()`: резидент → 403, PM → только свой проект (customer_id), support_agent/admin → все проекты
- **CRUD endpoints**: projects (`POST /projects/`, `GET /projects/`, `PATCH /projects/{id}`, `POST /projects/{id}/transition`, `DELETE` = soft-cancel), phases (`start`, `complete`), tasks (`complete`, soft-delete via CANCELLED)
- **Workspace endpoints** (`workspace_router.py`): upload/download документов (20 МБ, 9 MIME типов), команда (admin-only add/remove), комментарии (PM не видит is_internal), события (audit log)
- **Ticket-link**: `POST /projects/{id}/link-ticket`, `/unlink-ticket/{ticket_id}`, `GET /projects/{id}/tickets` — опциональная привязка тикета к проекту с флагом `is_implementation_blocker`
- **Email-уведомления** (`backend/notifications/projects.py`): `notify_project_created`, `notify_project_status_changed`, `notify_phase_completed`, `notify_milestone_reached` — отправка клиенту + менеджеру через background_tasks
- **Frontend**: новый Pinia store `stores/projects.ts` (24 action'а), 3 страницы (`ProjectsListPage`, `ProjectDetailPage` с TabView из 7 табов, `ProjectCreatePage` с preview шаблона), 5 компонентов (`ProjectCard`, `ProjectStatusBadge`, `ProjectTypeBadge`, `PhaseCard`, `TaskRow`, `ProjectTimeline`)
- **Секция "Проект внедрения"** в `TicketDetailPage.vue`: Select активных проектов + Checkbox "Блокер" + кнопки Связать/Отвязать
- **RBAC в роутере**: `router.beforeEach` расширен проверкой `to.meta.roles` против `authStore.user?.role`
- **Пункт меню «Проекты»** в App.vue для ролей `property_manager`, `support_agent`, `admin` (резиденты НЕ видят)
- **33 unit-теста** в `tests/test_projects_models.py`: FSM, recalculate_progress (edge-cases: skipped/cancelled/empty), все 4 шаблона, phase/task methods
- **ADR-006** (Проекты — отдельный домен) + **ADR-007** (Шаблоны как Python-константы)

**Зачем:** PASS24 Service Desk был только реактивным (тикеты). Теперь это **единый портал** для клиента: и поддержка после запуска, и контроль процесса внедрения СКУД. PM видит прогресс online, команда знает текущие задачи и блокеры. Опциональная связь тикетов с проектами даёт целостный контекст: тикет-блокер → проект встаёт.

---

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
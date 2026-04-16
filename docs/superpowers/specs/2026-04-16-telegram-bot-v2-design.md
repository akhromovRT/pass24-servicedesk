# Telegram-бот PASS24 v2 — Design Spec

**Scope:** Resident Core (A) + PM Workspace (B)
**Date:** 2026-04-16
**Status:** Approved

## 1. Цели

Переписать минимальный Telegram-бот (390 строк, 3 функции) в полнофункциональный канал взаимодействия, покрывающий 100% портала для внешних пользователей (резидентов и property-менеджеров).

### Чего нет в текущем боте
- Нет inline-кнопок, wizard'ов, меню — только свободный текст
- Нет привязки к реальному аккаунту (ghost-юзер `@telegram.pass24.local`)
- Нет KB-поиска, AI-чата, CSAT, approvals, проектов
- Нет фильтрации/списка «мои заявки»
- Нет управления уведомлениями

### Что будет
- Menu-driven UX с inline keyboards на каждом экране
- Deep link привязка к реальному аккаунту портала
- Wizard создания тикета с KB deflection (снижение нагрузки)
- Список «мои заявки» с карточкой, ответами, CSAT
- KB-поиск и просмотр статей
- AI-ассистент (Claude + Qdrant RAG)
- PM: мои проекты, approvals (утвердить/отклонить фазу)
- Гибкие push-уведомления с inline-кнопками
- Настройки: toggle уведомлений, отвязка

## 2. Пользователи и роли

| Роль | Что видит в боте |
|---|---|
| `resident` | Меню без «Мои проекты» |
| `property_manager` | Полное меню с проектами и approvals |
| Не привязан | Приветствие + ссылка на привязку. Ghost-flow как fallback |

## 3. Архитектурные решения

### 3.1 Библиотека: aiogram 3

Стандарт для Python + Telegram. Встроенный FSM, callback query routing, middleware, async-first. Интегрируется в FastAPI через `Dispatcher.feed_update()` — никакого отдельного HTTP-сервера.

### 3.2 FSM Storage: PostgreSQL

Кастомный `PostgresStorage(BaseStorage)` (~80 строк) поверх таблицы `telegram_fsm_state`. Переживает рестарт контейнера. Не добавляет Redis (сохраняем принцип из ADR — «Redis не используется»).

### 3.3 Аутентификация: Deep link

Пользователь в портале (Настройки → Telegram) генерирует одноразовый токен → открывает `https://t.me/PASS24bot?start=<token>` → бот матчит с аккаунтом → привязка. Токен одноразовый, TTL 10 мин.

Ghost-flow (`@telegram.pass24.local`) остаётся как аварийный fallback для новых пользователей, не зарегистрированных в портале. При последующей привязке тикеты ghost-юзера переносятся на реального.

### 3.4 UX: Menu-driven + inline keyboards

Каждый шаг wizard'а перерисовывается через `message.edit_text()` (один экран, чат не замусоривается). Навигация и выбор — кнопки; свободный текст — только для описания проблемы, комментариев, AI-вопросов.

### 3.5 Callback data: compact format

`<domain>:<action>:<short_id>[:<param>]`, short_id = первые 8 символов UUID. Влезает в 64-byte лимит TG.

Примеры: `mm:tc` (главное меню → создать тикет), `tc:prod:mobile_app`, `tl:open:a1b2c3d4`, `ap:approve:f1e2d3c4`, `csat:rate:a1b2c3d4:5`.

### 3.6 Push-уведомления: BackgroundTasks + retry

Без outbox-таблицы на MVP. Retry с exponential backoff внутри `_tg_send_with_retry()` (3 попытки). При 403 Forbidden (бот заблокирован) — автоматическая отвязка `user.telegram_chat_id = None`. Фильтр по `user.telegram_preferences` перед отправкой.

### 3.7 Язык: только русский

Мультиязычность — при первом реальном запросе.

## 4. Структура кода

```
backend/telegram/                        # новый пакет
├── __init__.py
├── config.py                            # токен, webhook secret, deep link base URL
├── bot.py                               # Bot() + Dispatcher() singleton
├── webhook.py                           # FastAPI router: POST /telegram/webhook/{secret}
├── storage.py                           # PostgresStorage(BaseStorage) для aiogram FSM
├── middlewares/
│   ├── auth.py                          # User по chat_id → data['user'], ghost detection
│   ├── throttle.py                      # 10 msg/min rate limit
│   └── logging.py                       # structured log каждого update
├── keyboards/
│   ├── main_menu.py
│   ├── ticket_wizard.py                 # продукт, категория, impact/urgency, confirm
│   ├── ticket_detail.py                 # действия в карточке
│   ├── kb.py                            # поиск, статья, feedback
│   ├── projects.py                      # список, карточка, approvals
│   └── common.py                        # Cancel/Back/Pagination builders
├── handlers/
│   ├── __init__.py                      # dp.include_router(...)
│   ├── start.py                         # /start, deep link, account linking
│   ├── menu.py                          # главное меню, fallback free-text
│   ├── tickets_create.py               # wizard (CreateTicketStates FSM)
│   ├── tickets_list.py                  # мои заявки, карточка, пагинация
│   ├── tickets_reply.py                 # ответ, вложения, закрытие
│   ├── kb.py                            # поиск и просмотр KB
│   ├── ai.py                            # AI-чат (Claude + RAG)
│   ├── projects.py                      # мои проекты (PM)
│   ├── approvals.py                     # approve/reject фаз (PM)
│   ├── csat.py                          # рейтинг CSAT
│   └── settings.py                      # toggle уведомлений, отвязка
├── services/
│   ├── linking.py                       # generate/verify deep-link токен, ghost migration
│   ├── ticket_service.py               # create/list/comment — обёртки
│   ├── kb_service.py                    # FTS, markdown→HTML для TG
│   ├── ai_service.py                    # обёртка над assistant/rag.py
│   ├── project_service.py              # list/approve/reject
│   └── notify.py                        # notify_telegram_comment/status/sla/csat/approval
├── deflection.py                        # KB suggest + deflection tracking
├── formatters.py                        # Ticket/Article/Project → HTML для TG
└── exceptions.py                        # TelegramAuthError, TelegramRateLimit
```

Принципы:
- Каждый файл ≤ 300 строк
- Handlers не содержат бизнес-логики — только FSM state + вызов services + ответ
- Services переиспользуют существующие модули (`tickets/*`, `knowledge/*`, `assistant/*`, `projects/*`)
- `backend/notifications/telegram.py` (старый) → удаляется, `notify_*` переезжают в `telegram/services/notify.py`

## 5. БД: миграция 019

### Новая таблица `telegram_fsm_state`

| Колонка | Тип | Назначение |
|---|---|---|
| `key` | `VARCHAR PK` | `"bot:{bot_id}:chat:{chat_id}:user:{user_id}"` |
| `state` | `VARCHAR NULL` | `"CreateTicket:description"` |
| `data` | `JSONB` | `{product, category, description, attachments[]}` |
| `updated_at` | `TIMESTAMPTZ` | TTL-очистка > 24ч |

### Новая таблица `telegram_link_tokens`

| Колонка | Тип | Назначение |
|---|---|---|
| `token` | `VARCHAR(64) PK` | `secrets.token_urlsafe(32)` |
| `user_id` | `UUID FK users.id` | Кто генерирует |
| `expires_at` | `TIMESTAMPTZ` | `now() + 10 min` |
| `used_at` | `TIMESTAMPTZ NULL` | One-time use |

### Изменения в `users`

- `telegram_linked_at TIMESTAMPTZ NULL` — признак привязки через deep link
- `telegram_preferences JSONB DEFAULT '{}'` — `{notify_comments, notify_status, notify_sla, notify_approvals}`, все `true` по умолчанию

## 6. FSM Wizard: создание тикета

```python
class CreateTicketStates(StatesGroup):
    product = State()
    category = State()
    description = State()      # текст + медиа, кнопка «Далее»
    kb_deflection = State()    # top-3 статьи из FTS, «Помогло» / «Создать заявку»
    impact_urgency = State()   # impact (3 кнопки) + urgency (3 кнопки) + «Пропустить»
    confirm = State()          # preview → «Отправить» / «Изменить» / «Отмена»
```

### KB Deflection flow

1. После `description` → `kb_service.search(query=description, limit=3)`
2. Если пустой → пропускаем, сразу impact_urgency
3. Если есть → показываем 3 статьи inline
4. Клик на статью → показ текста + `[👍 Помогло] [👎 Не помогло]`
5. `👍 Помогло` → deflection (тикет НЕ создаётся), FSM сброс, `article_feedback(helpful=True)`
6. `👎` или `➡ Не помогло, создать заявку` → продолжаем wizard, при создании тикета линкуем показанные статьи как `TicketArticleLink(relationship="related")`

### Шаг description — сбор вложений

Бот аккумулирует все сообщения пользователя (текст, фото, документы, видео, голосовые) в `state.data.description` + `state.data.attachments[]`. Каждое фото в media group обрабатывается как отдельное вложение (без группировки — YAGNI). Кнопка `➡ Далее` появляется при `len(description) >= 10 OR attachments`.

### Шаг impact_urgency

Два ряда по 3 кнопки: impact (Все/Группа/Только я) + urgency (Немедленно/Сегодня/Может подождать). Кнопка `⏭ Пропустить` → backend вызовет `assign_priority_based_on_context()`. При выборе обоих → priority через `PRIORITY_MATRIX`.

### Шаг confirm

Preview: продукт, категория, приоритет, количество вложений, описание. Кнопки: `[✅ Отправить] [✏ Изменить описание] [✕ Отмена]`. При отправке: создание `Ticket(source=TELEGRAM)`, скачивание вложений из TG, создание `TicketEvent`, показ номера и SLA.

## 7. Экраны

### 7.1 Главное меню

Динамическое по роли. Показывает счётчики (активных заявок, pending approvals).

```
[📝 Новая заявка]
[📋 Мои заявки  •3]
[📚 База знаний]
[🤖 Спросить AI]
[🏗 Мои проекты  •1⏳]      ← только PM
[⚙ Настройки]
```

### 7.2 Мои заявки

Список с фильтром `[Активные] [Все] [Закрытые]`, пагинация 5/стр. Метка `•💬 новое` если `has_unread_reply`. Клик → карточка тикета: шапка (номер, статус, приоритет, SLA, категория), последние комментарии (10, `⬆ Показать ещё`), действия (`💬 Ответить`, `📎 Вложение`, `✕ Закрыть`, `⭐ Оценить`).

### 7.3 База знаний

Поиск свободным текстом → FTS top-5. Просмотр статьи (Markdown → HTML, 4000 chars max). Feedback: `[👍 Помогло] [👎 Не помогло] [📝 Создать заявку по теме]`. `👍/👎` → `article_feedback`. `📝` → wizard с auto-link `TicketArticleLink(created_from)`.

### 7.4 AI-ассистент

FSM state `AIChatStates.chatting`. Текст → `ai_service.ask(text, session_id)` → ответ с references на KB-статьи. Кнопки: `[📝 Создать заявку] [📄 Открыть статью] [⬅ Выйти]`. История в рамках сессии в FSM data.

### 7.5 Мои проекты (только PM)

Список проектов по `customer_id`. Карточка: название, тип, статус, прогресс-бар, текущая фаза, ближайшие задачи. Подменю: `[🏗 Фазы] [📎 Документы] [⚠ Риски] [💬 Комментарии]`.

### 7.6 Approvals (только PM)

Отдельный пункт `[⏳ Ожидают утверждения: N]`. Карточка фазы: описание, документы, комментарий менеджера. Кнопки: `[✅ Утвердить] [❌ Отклонить]`. Утверждение → confirmation → `project_service.approve_phase()`. Отклонение → FSM запрос причины → `project_service.reject_phase(reason)`, фаза возвращается в `in_progress`.

### 7.7 CSAT

Инлайн при RESOLVED: `[⭐1] [⭐2] [⭐3] [⭐4] [⭐5]`. При ≤3 звезды → доп. вопрос «Что улучшить?». Пишет в `ticket.satisfaction_score/comment`.

### 7.8 Настройки

Toggle уведомлений (comments, status, sla, approvals) через `telegram_preferences JSONB`. Отвязка → `user.telegram_chat_id = None`. Привязанный email и роль.

### 7.9 Free-text fallback

Вне wizard'а и вне карточки тикета: бот предлагает `[📝 Создать заявку] [🤖 AI] [📚 KB] [🏠 Меню]`, текст сохраняется в state для переиспользования.

## 8. Account linking — end-to-end

### Портал

1. `POST /auth/telegram/link-token` (JWT required) → `{token, deeplink, expires_at}`
2. Rate limit: 5 токенов/час на юзера
3. Инвалидация предыдущих неиспользованных токенов того же юзера
4. Frontend: `TelegramLinkCard.vue` в SettingsPage — QR-код + кнопка «Открыть Telegram» + polling `GET /auth/me` каждые 3 сек до появления `telegram_chat_id`

### Бот

1. `/start <token>` → `linking_service.verify_token(token)`
2. Проверки: не expired, не used, не привязан к другому chat_id
3. Preview: «Привязать аккаунт Ивана Петрова?» → `[✅ Да] [✕ Нет]`
4. `link_account()`: `user.telegram_chat_id = chat_id`, `telegram_linked_at = now()`, ghost migration, `token.used_at = now()`
5. → главное меню

### Ghost migration

При привязке: ищем ghost-юзера по chat_id с email `@telegram.pass24.local`. Если найден: переносим его тикеты (`UPDATE tickets SET creator_id = real_user_id`), комментарии, события. Ghost деактивируется (`is_active=False`). Одна транзакция.

### `/start` без токена

- Не привязан → приветствие + `[🔗 Получить ссылку привязки]` (открывает портал)
- Привязан → главное меню

## 9. Push-уведомления

| Событие | Содержание | Inline-кнопки |
|---|---|---|
| Новый комментарий агента | Текст комментария, тикет | `[💬 Ответить] [📋 Открыть]` |
| Смена статуса | old → new | `[📋 Открыть тикет]` |
| Статус RESOLVED | Запрос CSAT | `[⭐1]...[⭐5] [⏭ Пропустить]` |
| SLA breach warning | За 30 мин до нарушения | `[📋 Открыть тикет]` |
| Запрос approval (PM) | Фаза, документы | `[✅ Утвердить] [❌ Отклонить]` |
| Milestone (PM) | Фаза завершена | `[🏗 К проекту]` |
| Риск severity=high (PM) | Описание риска | `[🏗 К проекту]` |

Фильтрация: проверка `telegram_preferences.notify_*` перед отправкой. При 403 → auto-unlink.

## 10. Изменения в существующем коде

| Файл | Изменение | Масштаб |
|---|---|---|
| `backend/main.py` | Импорт `telegram.webhook`, создание Bot/Dispatcher в lifespan | 5 строк |
| `backend/notifications/telegram.py` | **Удаляется** | -390 строк |
| `backend/tickets/router.py` | Импорт `notify_*` из `telegram.services.notify` | 4 строки |
| `backend/tickets/sla_watcher.py` | Ветка «если chat_id и notify_sla → push» | +15 строк |
| `backend/projects/router.py` | Approval endpoints → вынос в `projects/services.py` | ~50 строк рефакторинга |
| `backend/projects/services.py` | Новые `approve_phase()`, `reject_phase()` | +50 строк |
| `backend/auth/router.py` | `POST /auth/telegram/link-token`, `DELETE /auth/telegram/link` | +40 строк |
| `backend/auth/models.py` | +`telegram_linked_at`, +`telegram_preferences` | 2 строки |
| `backend/knowledge/router.py` | Выделить `search_articles()` в `knowledge/services.py` (если ещё не выделена) | 0-20 строк |
| `frontend/src/pages/SettingsPage.vue` | Секция `<TelegramLinkCard>` | +10 строк |
| `frontend/src/components/TelegramLinkCard.vue` | **Новый** (QR, polling, состояния) | ~150 строк |
| `frontend/src/api/auth.ts` | `generateTelegramLinkToken()`, `unlinkTelegram()` | +10 строк |

**Итого**: ~12 существующих файлов (точечные правки) + ~25 новых в `backend/telegram/` + 1 Vue-компонент + 1 миграция.

## 11. Тестирование

### Unit-тесты (`tests/test_telegram_bot.py`)

- Linking: generate/verify token (valid/expired/used), link_account, ghost migration
- PostgresStorage: set/get/clear, TTL cleanup
- Callback data parsing: все domain-prefixes
- Ticket wizard: полный flow через mock Message/CallbackQuery
- KB deflection: поиск, article_feedback, TicketArticleLink
- Approvals: approve/reject через services, проверка FSM фазы
- Notifications: фильтр preferences, 403 → unlink, retry на timeout

### Integration-тесты (`tests/test_telegram_webhook.py`)

Реальные TG update payloads → webhook endpoint → проверка состояния БД.

### Ручной smoke-тест

Чеклист: привязка через QR, wizard с вложением, deflection, push о статусе, CSAT, approval approve/reject, AI-чат, отвязка.

## 12. Rollout

1. **Миграция 019** — обратно совместима (только добавления)
2. **Деплой** — тот же webhook path `/telegram/webhook/{secret}`
3. **Compat mode** (2 недели): если юзер не привязан и нет FSM state → старая логика (ghost + тикет из текста). Для привязанных → полный новый UX
4. **Push-рассылка** текущим TG-юзерам: «Бот обновлён, привяжите аккаунт для полного функционала»
5. Через 2 недели: убираем compat mode, все видят «привяжи аккаунт»

## 13. DoD

- [ ] Миграция 019 на prod
- [ ] Старый `notifications/telegram.py` удалён, импорты переехали
- [ ] Unit-тесты написаны и проходят
- [ ] Integration-тест webhook проходит
- [ ] Smoke-тест с реального телефона по чеклисту
- [ ] `agent_docs/architecture.md` обновлён
- [ ] ADR-008 «Telegram-бот v2: aiogram 3 + PG FSM + отдельный домен»
- [ ] Запись в `development-history.md`
- [ ] Deploy с compat mode
- [ ] `telegram-bot-user-guide.md` для менеджеров поддержки

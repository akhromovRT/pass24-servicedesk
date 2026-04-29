# ADR

## Записи

### [2026-04-29] ADR-018: SPA-fallback middleware для конфликта SPA-route и API-endpoint

#### Статус
Принято. Дополняет существующие SPA-handlers в `backend/main.py` (для статических путей `/login`, `/tickets/create` и т.п.).

#### Контекст
Backend FastAPI отдаёт и API, и статический SPA-фронт (`STATIC_DIR/index.html`). SPA-роуты с фиксированными именами уже зарегистрированы как FastAPI-handlers до `include_router(tickets_router)` (`/login`, `/tickets/create`, `/forgot-password`, `/reset-password`, `/projects/analytics`, etc.). Но **динамические detail-роуты SPA коллидируют с API-endpoint'ами**:
- SPA `/tickets/:id` совпадает с API `GET /tickets/{ticket_id}`
- SPA `/projects/:id` совпадает с API `GET /projects/{project_id}`

При AJAX-запросах от фронта это работает: api-клиент шлёт `Authorization: Bearer ...`, попадает в API → JSON.
При **прямом HTTP-запросе из браузера** (middle-click новая вкладка, F5 на странице тикета, клик по ссылке `support.pass24pro.ru/tickets/<id>` из email-уведомления) браузер не отправляет `Authorization` — backend возвращает `401 application/json`, пользователь видит JSON-ошибку вместо страницы тикета.

Это был **давний скрытый баг** — F5 на тикете и ссылки в email тоже отдавали 401, но никто не пытался. Высветился, когда `<RouterLink>` заменил `@click` для middle-click new tab.

#### Рассмотренные альтернативы

- **Изменить SPA-route с `/tickets/:id` на `/t/:id`** (или другой префикс, не совпадающий с API). Чистое решение, но: ломает все существующие URL в email-уведомлениях, закладках пользователей, Bitrix24-комментариях. Migration-шум на сотни ссылок.
- **Префиксовать API под `/api/...`** (а SPA оставить на корне). Правильное архитектурное решение, но требует синхронных изменений в трёх слоях (backend routes, frontend api-клиент, deploy/nginx). Большая работа.
- **Перевод routing на nginx**: добавить `location /tickets/<UUID-pattern>` → SPA, остальное в backend. Работает, но требует SSH-доступ к VPS и не версионируется в репо (nginx живёт вне Docker compose в этом проекте).
- **ASGI middleware** (выбрано). Различение AJAX vs browser-visit в одном файле кода, никаких миграций URL, исправляет F5/email-ссылки автоматически.

#### Решение
ASGI middleware `spa_detail_fallback` в `backend/main.py`, регистрируется до `include_router(tickets_router)`. Срабатывает при **одновременном** выполнении 4 условий:

1. `request.method == "GET"`
2. `path` совпадает с UUID-regex `^/(tickets|projects)/<8-4-4-4-12 hex>/?$`
3. `Authorization` header **отсутствует** (AJAX от api-клиента всегда его шлёт)
4. `Accept` содержит `text/html` (реальный browser navigation)

При срабатывании — возвращает `FileResponse(STATIC_DIR/"index.html", headers={"Cache-Control": "no-store"})`. SPA читает токен из localStorage и делает AJAX-запрос с Bearer — попадает в API.

**Условие #4 критическое:** без него middleware ловил бы и AJAX, который ушёл без `Authorization` (например, токен ещё не подгрузился из localStorage). Браузер шлёт `Accept: text/html,...`, fetch без явного Accept — `*/*`. Это надёжно различает.

`Cache-Control: no-store` на SPA-fallback ответе — чтобы браузер не закэшировал HTML на URL, который потом будет дёргаться api-клиентом за JSON.

**Frontend защита (вторая линия):** `frontend/src/api/client.ts` теперь явно шлёт `Accept: application/json` в AJAX и проверяет `Content-Type` ответа: если 200 пришёл с не-JSON типом — расценивает как «middleware ошибочно отдал SPA из-за протухшего токена», очищает токен и редиректит на `/login` вместо падения `JSON.parse`.

#### Последствия
- Один файл (`backend/main.py`, +24 строки), без миграций URL и nginx.
- Одновременно фиксит middle-click new tab, F5 на странице тикета и ссылки `/tickets/<id>` в email-уведомлениях SLA/CSAT (раньше уводили в JSON).
- Покрыты `/tickets/:id` И `/projects/:id` — заодно решена та же скрытая проблема для проектов.
- Frontend api-клиент усилен: `Accept: application/json` явный, content-type guard. Это полезное усиление в любом случае.
- Не покрывает кейс, когда у пользователя нет токена в localStorage и он middle-click'ает: SPA загружается → router beforeEach видит `meta.auth: true` без токена → редирект на `/login?redirect=/tickets/<id>`. Это правильное поведение.
- Long-term: если когда-то решим унифицировать routing через `/api/...` префикс — middleware можно убрать. Сейчас компромисс «один файл vs migration по сотням URL» в пользу middleware.

---

### [2026-04-29] ADR-017: SLA-пауза в бизнес-секундах + единая точка истины через `compute_sla_state`

#### Статус
Принято. Уточняет ADR-005 в части семантики паузы и контракта API.

#### Контекст
SLA уже считался в бизнес-часах на бэке (ADR-005: `deadline_with_business_hours`, шаг 30 мин), но:
1. **API не отдавал готовые дедлайны и `remaining_seconds`** — фронт самостоятельно считал «осталось» через `Date.now() - created_at - sla_total_pause_seconds * 1000` в линейном времени. Тикеты, созданные ночью или в выходные, с утра показывались «красными» при том, что бэк не считал их просроченными.
2. **`sla_total_pause_seconds` копил линейные секунды.** Пауза с пт 17:00 до пн 10:00 добавляла к дедлайну 65 линейных часов — пауза «дарила» нерабочее время и формально ослабляла SLA.
3. **Расчёт «активного» дедлайна был размазан**: watcher `_check_sla_breaches` дублировал inline-арифметику паузы и дедлайна, фронт делал свою (неправильную) — рассинхрон при изменениях.

#### Решение
1. Бизнес-часы выделены в чистый модуль `backend/tickets/business_hours.py` без зависимостей от моделей. Перенесены `WORK_START_HOUR`, `WORK_END_HOUR`, `MSK_OFFSET_HOURS`, `_msk_hour`, `_is_work_time`, `business_hours_between`. Добавлена `deadline_with_business_minutes(start, target_minutes)` — обобщение `deadline_with_business_hours`.
2. Новый сервис `backend/tickets/sla_service.py` экспортирует `compute_sla_state(ticket, now) -> SlaState` — единая точка истины. Возвращает `response_due_at`, `resolve_due_at`, `active_due_at`, `response_remaining_seconds`, `resolve_remaining_seconds`, `remaining_seconds`, `is_paused`. `remaining_seconds` может быть отрицательным (= просрочено на abs(value)).
3. `Ticket.recompute_sla_pause` (`models.py`) копит **бизнес-секунды**: при снятии паузы `elapsed = int(business_hours_between(sla_paused_at, now) * 3600)`. Семантика поля `sla_total_pause_seconds` изменена с линейных на бизнес-секунды.
4. `_check_sla_breaches` в `sla_watcher.py` переведён на `compute_sla_state` (явное `if state.is_paused: continue` + `state.active_due_at`). Watcher автоматически следит за активной фазой: response пока нет первого ответа, иначе resolve.
5. `TicketRead` (`schemas.py`) расширен 6 computed-полями (`sla_response_due_at`, `sla_resolve_due_at`, `sla_response_remaining_seconds`, `sla_resolve_remaining_seconds`, `sla_remaining_seconds`, `sla_is_paused`) через `@model_validator(mode="after")`. Миграция БД не требуется — поля только в памяти.
6. На фронте `frontend/src/utils/sla.ts` (`buildResponseProgress`, `buildResolveProgress`, `buildActiveProgress`, `getPauseLabel`) и `frontend/src/composables/useSlaProgress.ts` берут готовые числа с бэка. Никаких `Date.now()`-вычислений. `TicketSlaProgress.vue` и `TicketsPage.vue` рефакторены на этот слой; в `TicketsPage` добавлен polling `setInterval(loadTickets, 60_000)` чтобы полоска не «замораживалась» в фоне.

#### Рассмотренные альтернативы
- **Линейная пауза (как было).** Минус: нерабочее время «дарится» SLA, отчего тикеты не просрочиваются формально, хотя реальная работа в бизнес-часах могла бы исчерпать SLA. Расходится с интуицией пользователя «фиксировать оставшееся время».
- **Конфигурируемые рабочие часы через `.env`.** Не нужно сейчас (рабочие часы стабильны: пн-пт 9-18 МСК). Если понадобятся праздники/гибкий график — отдельный тикет, потребуется `holidays`/`workalendar`.
- **WebSocket-события для real-time обновления SLA.** `useWebSocket.ts` подготовлен на фронте, но не подключён. Polling 60с проще, не требует серверного события `ticket_sla_updated` и тестирования reconnect-логики. UX-эффект (смена цвета после возврата в рабочее время) не критичен к секундам.
- **Хранить `sla_*_due_at` в БД.** Дёшево считать в памяти (десятки мс на список 50 тикетов через `business_hours_between`); хранение требовало бы пересчёта при каждой смене паузы и денормализации.

#### Последствия
- Единый поток данных: `Ticket → compute_sla_state → TicketRead → fetch → utils/sla → UI`. Любое изменение бизнес-часов или паузы локализовано в `sla_service.py` / `business_hours.py`.
- API контракт расширен (новые опциональные поля). Старые клиенты не ломаются — добавление полей обратно совместимо.
- Семантика `sla_total_pause_seconds` изменена. Миграция 028 обнуляет поле для активных тикетов без активной паузы (`sla_paused_at IS NULL AND status NOT IN ('resolved','closed')`); закрытые тикеты не трогаем (исторические данные), активные паузы корректно обновятся при следующем `recompute_sla_pause`.
- Watcher теперь warn-ит и за фазу response, не только resolve (раньше проверял только `sla_resolve_hours`). Это улучшение, фиксируется здесь.
- Линейная пауза, упомянутая как «упрощение» в ADR-005, явно заменена на бизнес-секунды.

---

### [2026-04-28] ADR-016: Авто-привязка guest-тикетов к Customer по поддомену embed-страницы

#### Статус
Принято.

#### Контекст
ADR-014 закрепил доставку AI-виджета через loader+iframe на ~250 клиентских сайтов формата `https://{name}.pass24online.ru/...`. Гостевые тикеты, создаваемые через виджет (`POST /tickets/guest`), приходили с `Ticket.customer_id = NULL` — оператор поддержки вынужден был руками связывать заявку с компанией в `customers` каждый раз. Реестр постоянных клиентов уже синхронизирован из Bitrix24 по ИНН (миграция 020 + `bitrix24_sync.py`), но связи между Customer и его сайтом в базе не было.

#### Рассмотренные альтернативы
- **Полный домен на стороне Customer (`Customer.site_domain = "bristol.pass24online.ru"`)**. Плюс: точное совпадение, не нужен парсинг. Минус: дубль с базой, при смене корневого домена pass24online → миграция данных. Слабее по семантике («поле для произвольного домена», но мы поддерживаем только subdomain).
- **Принимать на бэке полный hostname без собственного поля у Customer + матчить по транслитерации Customer.name**. Минус: нестабильно (имена в Bitrix часто как «ООО Жилищный комплекс Бристоль» — slug не предсказать), хрупко при ребрендинге.
- **Поле `Customer.subdomain`** (выбрано). Хранит «bristol» в чистом виде, индексировано. Backend парсит embed_host и матчит. Если когда-то появятся кастомные домены (не `*.pass24online.ru`) — добавим вторым полем `Customer.custom_domain` без ломки текущей логики.

#### Решение
- **Backend:** новая колонка `customers.subdomain` (миграция 027) с частичным unique-индексом по ненулевым значениям — паттерн как у миграции 026 для `tickets.email_message_id`. Хелпер `backend/utils/embed_host.extract_subdomain(host)` извлекает первый label из `*.pass24online.ru`. В `POST /tickets/guest` (`backend/tickets/router.py`): если в payload пришёл `embed_host` и из него извлекается валидный subdomain — `SELECT customers WHERE subdomain = ? AND is_permanent_client AND is_active`; найден — заполняем `customer_id`, `company` (= `Customer.name`), `object_name` (если payload не задал собственное значение).
- **Frontend (loader):** `chat-loader.js` подмешивает `?host=<window.location.hostname>` в URL iframe. Изменение совместимо назад: backend payload без `embed_host` ведёт себя как раньше.
- **Frontend (widget):** `ChatWidgetPage.vue` читает `route.query.host` и шлёт его как `embed_host` в `POST /tickets/guest`.
- **Наполнение реестра:** subdomain'ы заводятся через одноразовый seed-скрипт `backend/scripts/seed_customer_subdomains.py` из CSV вида `subdomain,inn`. Скрипт идемпотентен; пример CSV — `backend/scripts/customer_subdomains.csv.example`.

#### Обоснование
- Один FK-кандидат у Ticket (`customer_id`) — не плодим дублирующих полей; `company` и `object_name` — текстовые «снимки» имени, удобные при отображении в списке/email-уведомлении (не зависят от JOIN с customers).
- Матчим только `is_permanent_client` — намеренно: разовые/ушедшие клиенты могут случайно сохранить subdomain в Bitrix, но не должны автозаполняться в новых тикетах.
- `embed_host` приходит от клиента и теоретически подделывается через DevTools. На этапе 1 принимаем на веру — последствие подделки = тикет помечен не той компанией, у guest'а нет доступа на чтение клиентских данных. TODO в коде на сверку с `Referer`-заголовком в будущем.

#### Последствия
- **(+)** Авто-связывание: оператор видит «Бристоль» в карточке тикета без ручной привязки.
- **(+)** Фундамент для per-tenant функций: KB-фильтрация, кастомизация AI-промпта, аналитика «с какого ЖК больше всего обращений».
- **(+)** Обратная совместимость: payload без `embed_host` создаёт тикет как раньше (`customer_id = NULL`).
- **(−)** Без CSV от ops-команды поле остаётся пустым у всех Customer'ов → автосвязывание не работает. Это известный prerequisite.
- **(−)** Кастомные домены клиентов (не `*.pass24online.ru`) не покрываются — добавится отдельным ADR при появлении.

---

### [2026-04-24] ADR-015: Self-hosted telegram-bot-api в гибридном режиме (без `logOut`) для вложений >20 МБ

#### Статус
Принято. Реализовано в PR #22.

#### Контекст
Cloud `api.telegram.org` ограничивает `getFile` верхним потолком 20 МБ — реальные email-вложения от клиентов PASS24 (PDF-планы ЖК, видео объектов) регулярно больше и молча пропускались (`ticket_service.py` логировал `skipping attachment ... exceeds ... bytes`). Нужно было поднять этот лимит, сохранив бот `@PASS24bot` работающим.

#### Рассмотренные альтернативы
- **Прямая миграция бота на self-hosted через `logOut`** (из исходного плана). Минус: `logOut` на `api.telegram.org` триггерит 10-минутный `FLOOD_WAIT`, в течение которого бот не принимает сообщения. Плюс ещё 10 минут при возможном rollback. В рабочее время неприемлемо.
- **Self-hosted на том же VPS `5.42.101.27`**. Минус: `telegram-bot-api` под нагрузкой берёт 150–500 МБ RAM, плюс `--local` режим пишет файлы в FS; на shared VPS (pass24, ONVIS, OpenClaw под общим nginx) это риск OOM и deadlock диска. Отдельный VPS эксплуатационно чище.
- **Принимать 20 МБ лимит, писать клиентам «перешлите по email»**. Минус: поддержка уже загружена, дополнительный ручной шаг удваивает SLA response.
- **Гибридный режим без `logOut`** (выбрано): webhook остаётся на `api.telegram.org` (zero downtime), `pass24-api` дополнительно ходит на self-hosted `telegram-bot-api` **только за `getFile`** для больших файлов. Read-only операции не требуют session-lockа → два Bot API сервера сосуществуют для одного и того же бота.

#### Решение
- Hetzner Cloud CX23 в Nuremberg (`178.104.228.43`, `tg-api.pass24pro.ru` DNS-запись в зоне Timeweb не применилась из-за бага провайдера — см. history 2026-04-20; временно используется IP напрямую, HTTP без TLS между pass24-api `5.42.101.27` и VPS).
- Docker-контейнер `aiogram/telegram-bot-api:latest` с флагом `--local` (обязательно — без него self-hosted тоже ограничен 20 МБ). `API_ID` / `API_HASH` получены на `my.telegram.org` под служебным аккаунтом PASS24.
- Caddy на VPS слушает `:80`, делает `reverse_proxy localhost:8081` и `file_server /tgfiles/*` из `/var/lib/telegram-bot-api` (каталог с скачанными файлами в `--local` режиме). IP-allowlist: `5.42.101.27` + админский IP.
- `backend/telegram/services/ticket_service.py` патч в `_download_tg_file()`: параметризация базового URL через `settings.telegram_api_base` (существовало), добавлен `settings.telegram_file_api_base` для `--local` FS-путей. Бранчинг по префиксу `/var/lib/telegram-bot-api/`: cloud → `{api_base}/file/bot{token}/{path}`, self-hosted → `{file_api_base}/{relative}`.
- `_MAX_TG_FILE_SIZE` поднят 20 → 100 МБ (application-level cap для защиты диска; `--local` технически поддерживает до 2 ГБ).
- На проде `support.pass24pro.ru`: `TELEGRAM_API_BASE=http://178.104.228.43`, `TELEGRAM_FILE_API_BASE=http://178.104.228.43/tgfiles`.

#### Обоснование
Ключевое открытие: read-only операции Bot API (`getMe`, `getFile`, `getWebhookInfo`) **не требуют session-лока**. Каждый Bot API сервер хранит своё представление состояния бота (webhook, pending updates), но одинаково видит один и тот же бот в Telegram backend через MTProto. `logOut` нужен только для **передачи управления** `getUpdates`/webhook. Пока self-hosted не делает setWebhook / getUpdates — конфликта нет. Это разрешено Telegram и подтверждено на практике: `getMe` через self-hosted для `@PASS24bot` возвращает валидный JSON, параллельно прод-webhook продолжает доставлять updates.

#### Последствия
- **(+)** Zero downtime миграция: клиенты не заметили переключения, pending FLOOD_WAIT не сработал.
- **(+)** Маленькие файлы (<20 МБ, 95%+ трафика) продолжают идти через cloud `api.telegram.org` — самый быстрый путь, нет overhead прокси.
- **(+)** Rollback = 2 env-переменные: убрать `TELEGRAM_API_BASE`/`TELEGRAM_FILE_API_BASE` из `.env` + `docker compose up -d`. Код автоматически вернётся к cloud-режиму.
- **(−)** Bot token передаётся в cleartext по HTTP между `5.42.101.27` и `178.104.228.43` (EU ↔ MSK). Митигация: временно, до восстановления DNS / перехода на домен + Let's Encrypt TLS. IP-allowlist на Caddy + UFW сужает риск.
- **(−)** Диск VPS `40 ГБ` — при нагрузке надо мониторить `/opt/telegram-bot-api/data/`; старые файлы сейчас не чистятся (TDLib их не удаляет автоматически). Требуется cron-job на удаление `atime > 7 days`.
- **(−)** Когда/если Telegram изменит правила Bot API и запретит cross-server read-only — план сломается. Митигация: fallback на `logOut` в maintenance-окне, код уже поддерживает обе схемы.
- Архитектура: `pass24-api (5.42.101.27) ──HTTP──> Caddy:80 (178.104.228.43) ──> telegram-bot-api:8081 (docker) ──MTProto──> Telegram DC`.
- Подробный runbook: `agent_docs/guides/telegram-bot-api-self-hosted.md`.

---

### [2026-04-22] ADR-014: Embed AI-чата через loader-скрипт + iframe (без изменений backend/CORS)

#### Статус
Принято.

#### Контекст
Нужно встроить AI-помощник PASS24 (RAG над базой знаний + гостевое создание заявок) на ~250 облачных сайтов клиентов под разными доменами (tilda, WordPress, Bitrix, React/Next, статические сайты). Требования: нулевые изменения на стороне клиента кроме одной строки; никаких API-ключей, секретов, CORS-настроек; централизованное обновление для всех клиентов сразу; backend не трогать (уже работает для внутреннего чата в портале).

#### Рассмотренные альтернативы
- **Web Component / Custom Element** — чище семантически, Shadow DOM изолирует стили. Минус: требует CORS на backend (`/assistant/chat`, `/tickets/guest`) для всех клиентских доменов + сложнее сборка.
- **NPM-пакет** — клиент ставит пакет, бандлит у себя. Минус: каждому клиенту нужен developer time, обновления не автоматические.
- **Iframe + loader-script** (выбрано) — loader создаёт button+iframe, iframe рендерит ту же страницу портала `/chat-widget`. Запросы идут изнутри iframe в `support.pass24pro.ru` → same-origin, CORS не возникает.

#### Решение
- `frontend/public/chat-loader.js` — vanilla JS (~130 строк), раздаётся статикой с `support.pass24pro.ru/chat-loader.js`. Создаёт floating-кнопку и iframe с `src=/chat-widget`. Управляет open/close через клик + postMessage + Esc.
- `frontend/src/pages/ChatWidgetPage.vue` — Vue-страница с UI по референсу (тёмная шапка с AI-аватаром, серые/тёмные пузыри, зелёная круглая кнопка отправки, inline guest-форма тикета). Использует те же API `/assistant/chat` и `/tickets/guest`, что и внутренний `AiChat.vue`.
- `frontend/src/App.vue` — на роуте `/chat-widget` скрывает navbar/Toast/floating AiChat/HelpModal (переменная `isEmbed`).
- Установка на клиентском сайте: одна строка `<script src="https://support.pass24pro.ru/chat-loader.js" async></script>` перед `</body>`.

#### Последствия
- **(+)** Backend не трогаем вообще. CORS отсутствует: запросы идут same-origin изнутри iframe.
- **(+)** Централизованное обновление: push в main → auto-deploy → все 250+ сайтов клиентов получают новую версию виджета сразу при следующей загрузке.
- **(+)** Изоляция: стили и JS iframe не конфликтуют с сайтом клиента.
- **(−)** Iframe нельзя затемизовать под бренд клиента из коробки (подготовлено `data-*` для будущих параметров `data-color`, `data-greeting`, но не реализовано — не требовалось на старте).
- **(−)** Ограничения iframe: X-Frame-Options / CSP на стороне клиента должны разрешать `frame-src https://support.pass24pro.ru;` (у дефолтных CSP разрешено).
- Подробная инструкция по встраиванию на разные платформы (WordPress, Tilda, Webflow, Bitrix, React, Vue и т.д.): `docs/embed-ai-chat-guide.md`.

---

### [2026-04-20] ADR-013: Alembic `upgrade head` на старте контейнера (возврат к auto-migrate)

#### Статус
Принято. Заменяет ADR-003 (ручное применение).

#### Контекст
ADR-003 (2026-04-05) закрепил ручной запуск миграций после деплоя. Практика показала минусы: агенты забывали выполнять `alembic upgrade head`, и после деплоя получали 500-ки на новых колонках. Коммит `b7273b6 fix: auto-run alembic migrations on container start` вернул `alembic upgrade head` в `entrypoint.sh`, но ADR не был обновлён → документация разошлась с кодом.

#### Решение
`entrypoint.sh` выполняет `alembic upgrade head` перед стартом uvicorn на каждом рестарте контейнера (auto-migrate). Ручной запуск больше не требуется и не применяется в СI/deploy-workflow.

#### Обоснование
- **Атомарный деплой**: образ с новым кодом = образ с накатанной схемой, не бывает рассинхрона.
- **CI-friendly**: GitHub Actions просто делает `docker compose up`, никаких дополнительных SSH-шагов.
- **Fail-fast**: сломанная миграция останавливает контейнер до её починки → сервис недоступен, но в валидном состоянии, а не в «код-новый / схема-старая».

#### Последствия
- (+) Zero drift между кодом и схемой.
- (+) Любой старт контейнера сам подтягивает пропущенные миграции (актуально при ручных рестартах / backup-восстановлениях).
- (-) Сломанная миграция = crash loop. Контейнер рестартится каждые несколько секунд (`restart: unless-stopped`), пока fix не приедет через push.
- (-) Backfill-запросы бегут при каждом старте (если они не идемпотентны — проблема).

#### Практики для безопасных миграций
Все эти пункты обязательны, потому что цена ошибки — прод в crash loop:

1. **Проверять enum-регистр в SQL-предикатах.** Postgres enum `userrole` хранит значения как uppercase имена Python Enum-членов (`SUPPORT_AGENT`, `ADMIN`, `RESIDENT`, `PROPERTY_MANAGER`), а не lowercase `.value`. Bare string literal `'support_agent'` даёт `InvalidTextRepresentationError`. Паттерн: `u.role::text IN ('SUPPORT_AGENT', 'ADMIN')`.
2. **Кастовать UUID-колонки к `::text`** при сравнении с строковыми полями (например, `ticket_comments.author_id`).
3. **Делать backfill идемпотентным**: если миграция применится повторно (или двумя параллельными контейнерами), результат не должен испортиться.
4. **Разделять schema и data**: если backfill сложный — отдельной миграцией после schema-change. Сломанный data-backfill легче чинить отдельной «025»-миграцией, не трогая исходную.
5. **Никогда не удалять колонки «задним числом»**. Если старый код ещё может быть развёрнут при rollback'е, он упадёт на отсутствие колонки. Стандартный expand-contract паттерн.
6. **Тестировать миграцию на staging / локальной БД** с прод-данными перед пушем.

Инцидент 2026-04-20 (миграция 024) проиллюстрировал пункты 1 и 4: сравнение с lowercase string + backfill внутри schema-change → прод в crash loop на 15 минут, пришлось выпускать два fix'а (`9982a17` с `::text`, `ee48c6c` с миграцией 025). Миграцию 025 можно было бы избежать, если 024 изначально была только `add_column`, а backfill шёл отдельной data-миграцией с проверкой на staging.

---

### [2026-04-20] ADR-012: SMTP guard на зарезервированные домены (RFC 2606/6761)

#### Статус
Принято

#### Контекст
20 апреля 2026 через ручной запуск workflow `Ops — run pytest on prod` с расширенным target тесты создали десятки тикетов с адресами `test-<hex>@example.com` / `agent-<hex>@example.com` в прод-БД. Приложение честно отослало email-уведомления по каждому тикету на эти адреса через SMTP timeweb, и получило 36+ bounce-писем от mailer-daemon на `support@pass24online.ru`.

#### Решение
`backend/notifications/email._send_email` проверяет домен получателя перед отправкой SMTP и **молча пропускает** (с INFO-логом) адреса на зарезервированных доменах:
- `example.com` / `.net` / `.org` (RFC 2606)
- `.example`, `.invalid`, `.localhost`, `.test` (RFC 2606 + RFC 6761)

Гарантия работает независимо от источника адреса: тестовые фикстуры, пользовательский ввод, импорты из внешних систем, background-скрипты. Один слой защиты на выходе из приложения, без опоры на дисциплину авторов тестов.

#### Последствия
- Тесты могут безопасно использовать `@example.com` для фикстур без риска залить прод-почту.
- Если реальный клиент ошибётся и введёт `foo@example.com` как контакт — приложение не будет слать туда письма и создавать bounce-шум.
- Добавление нового reserved-домена = одно место (`_RESERVED_EMAIL_DOMAINS` / `_RESERVED_EMAIL_TLDS` в `email.py`).
- Юнит-тесты `tests/test_email_reserved_guard.py` закрывают 22 кейса (RFC-домены, реальные похожие, malformed-input).

Дополнительно ужесточён `.github/workflows/ops-run-tests.yml`: whole-suite прогон на проде запрещён, разрешены только файлы из явного allowlist'а.

### [2026-03-04] ADR-001: Технологический стек проекта

#### Статус
Принято

#### Контекст
Необходимо выбрать технологический стек для Help Desk портала PASS24. Требования: веб-портал с системой тикетов, базой знаний, ролевой моделью, графиками аналитики. Раздельные frontend и backend.

#### Решение

| Компонент | Технология |
|-----------|-----------|
| Backend | Python 3.12 + FastAPI |
| ORM | SQLModel |
| БД | PostgreSQL 16 |
| Frontend | Vue 3 + TypeScript |
| UI-библиотека | PrimeVue |
| State management | Pinia |
| Графики | vue-echarts |
| Фоновые задачи | crontab + FastAPI BackgroundTasks |
| Redis | убран (не требуется) |

#### Обоснование
- **FastAPI + SQLModel** — высокая производительность, автодокументация API (Swagger/OpenAPI), SQLModel совмещает Pydantic-валидацию и SQLAlchemy ORM
- **Vue 3 + TypeScript** — Composition API, хорошая экосистема, лёгкость освоения
- **PrimeVue** — богатый набор enterprise-компонентов (таблицы, формы, меню), подходит для admin-панели и портала
- **Pinia** — официальный state manager для Vue 3, простой API
- **vue-echarts** — мощные интерактивные графики для аналитики и дашбордов
- **Без Redis** — на этапе MVP фоновые задачи покрываются FastAPI BackgroundTasks + crontab; Redis можно добавить позже при необходимости

#### Последствия
- (+) Единый язык (Python) на backend, быстрая итерация
- (+) Автоматическая документация API через FastAPI
- (+) PrimeVue даёт готовые enterprise-компоненты без написания с нуля
- (-) SQLModel менее зрелый, чем чистый SQLAlchemy — возможно потребуется fallback на SQLAlchemy для сложных запросов
- (-) Без Redis нет кэширования и очередей — может стать узким местом при росте нагрузки

#### Альтернативы рассмотрены
- **Next.js / React** — отвергнут в пользу Vue 3 (предпочтение команды)
- **Django** — отвергнут в пользу FastAPI (легковеснее, async из коробки, автодокументация)
- **Redis** — отложен до момента, когда BackgroundTasks перестанет справляться

---

### [2026-04-03] ADR-002: bcrypt напрямую вместо passlib

#### Статус
Принято

#### Контекст
При деплое на production (Python 3.12, bcrypt 5.x) модуль `passlib` вызывал ошибку `ValueError: password cannot be longer than 72 bytes`. Проект passlib не поддерживается (последний релиз — 2020), несовместим с bcrypt >= 4.1.

#### Решение
Заменить `passlib.context.CryptContext` на прямые вызовы `bcrypt.hashpw()` / `bcrypt.checkpw()`.

#### Обоснование
- passlib — unmaintained (последний коммит 2020, нет поддержки bcrypt 4+)
- Прямой bcrypt API — 2 функции, нет лишних абстракций
- bcrypt 5.x — актуальная библиотека, активно поддерживается

#### Последствия
- (+) Совместимость с bcrypt 5.x на Python 3.12
- (+) Убрана неподдерживаемая зависимость (passlib)
- (-) Нет автоматического выбора схемы хеширования (только bcrypt)

---

### [2026-04-05] ADR-003: Ручное применение Alembic миграций вместо auto-migrate при старте

#### Статус
**Устарело — заменено ADR-013 (2026-04-20).** Текущий `entrypoint.sh` выполняет `alembic upgrade head` на каждом старте контейнера.

#### Контекст
При запуске FastAPI `await run_migrations()` в lifespan вешался на `Will assume transactional DDL` и не возвращал управление. Проблема: `asyncio.to_thread(command.upgrade)` вызывает `asyncio.run()` внутри Alembic env.py, что конфликтует с запущенным event loop uvicorn в некоторых конфигурациях.

#### Решение
Убрать `run_migrations()` из lifespan. Миграции применяются вручную после деплоя:
```bash
docker exec site-pass24-servicedesk python -m alembic upgrade head
```

#### Обоснование
- Production-safe: миграции применяются осознанно, не при каждом рестарте
- Нет риска падения приложения из-за сломанной миграции
- Легко rollback (контейнер живой, хоть с неправильной схемой)
- Стандартный подход в Django / Rails / .NET

#### Последствия
- (+) Приложение запускается мгновенно
- (+) Ясный контроль над миграциями в production
- (-) Забытая миграция → 500 ошибки при обращении к новым колонкам
- Митигация: CI/CD может быть расширен шагом `alembic upgrade head` после docker compose up

---

### [2026-04-05] ADR-004: Email-ответы → комментарии через тег в теме

#### Статус
Принято

#### Контекст
Нужно привязать email-ответы клиентов к существующим тикетам, а не создавать новые тикеты при каждом ответе.

#### Решение
Добавлять тег `[PASS24-xxxxxxxx]` (первые 8 символов ticket.id) в тему всех исходящих писем. При получении ответа — парсить тему на этот паттерн → добавлять комментарий к найденному тикету + сохранять вложения.

Fallback: если тега нет (старые письма), но тема начинается с `Re:` — искать тикет по заголовку + email отправителя.

#### Обоснование
- Стандартный подход (Jira, Zendesk, GitHub Issues, Linear)
- Работает в любом email-клиенте без настройки
- Устойчивость: даже если Message-ID / In-Reply-To потерялись, тег в теме выживает
- UTF-8 friendly (в отличие от некоторых Message-ID)

#### Последствия
- (+) 100% ответов клиентов корректно привязываются к тикетам
- (+) Не требует изменений на стороне клиента
- (-) Тег виден в теме, может немного мешать UX (но это индустриальный стандарт)

---

### [2026-04-05] ADR-005: Working-hours SLA через 30-минутные интервалы

#### Статус
Принято

#### Контекст
SLA не должен тикать ночью и в выходные. Нужен способ точно учитывать рабочие часы (пн-пт 9-18 МСК) при расчёте дедлайна.

#### Решение
Вместо сложных формул с календарями — пробегаем по 30-минутным интервалам от start до накопления нужного количества рабочих часов:
```python
while accumulated_work_minutes < target:
    if is_work_time(cur): accumulated += 30
    cur += timedelta(minutes=30)
```

#### Обоснование
- Простота: 15 строк кода вместо сложных формул
- Точность ±30 мин достаточна для SLA 4-24 часов
- Легко расширить (праздники, разные графики для групп)
- Нет багов с DST, часовыми поясами

#### Последствия
- (+) Легко читать и отлаживать
- (+) Работает для любых графиков работы
- (-) O(N/30) по минутам — на длинных SLA (сутки+) медленнее, но всё равно <1мс

---

---

### [2026-04-05] ADR-006: Модуль проектов внедрения как отдельная сущность

#### Статус
Принято

#### Контекст
Нужно добавить в PASS24 Service Desk управление проектами внедрения СКУД у клиентов (8-16 недель, много этапов, команда исполнителей). Вопрос: расширить существующую модель `Ticket.parent_ticket_id` или создать отдельный домен?

#### Решение
Создать отдельный модуль `backend/projects/` с новой иерархией `ImplementationProject → ProjectPhase → ProjectTask`. Связь с тикетами — опциональная: `Ticket.implementation_project_id` (nullable FK) + флаг `is_implementation_blocker`.

#### Обоснование
- **Разная FSM**: тикет (NEW → IN_PROGRESS → RESOLVED → CLOSED) ≠ проект (DRAFT → PLANNING → IN_PROGRESS ⇄ ON_HOLD → COMPLETED).
- **Разная семантика времени**: тикет = часы/дни (SLA), проект = месяцы (фазы, milestones).
- **Разная иерархия**: `parent_ticket_id` создан для Incident→Problem (2 уровня, одинаковые сущности). Проекты требуют Project→Phase→Task (3 уровня, разнотипные сущности).
- **RBAC различается**: PM видит только свои проекты (через customer_id), в то время как в тикетах он ограничен своими тикетами через другой механизм.
- Опциональная связь через `implementation_project_id` даёт гибкость: тикет может жить без проекта, проект — без тикетов.

#### Последствия
- (+) Чистое разделение доменов, каждая модель решает свою задачу
- (+) Можно эволюционировать независимо (добавить risks/approvals в projects, не затрагивая tickets)
- (+) Централизованный RBAC-guard `get_project_with_access()` исключает дыры в безопасности
- (-) Дублирование паттернов (events, attachments, comments) между tickets/ и projects/
- Митигация: копируем проверенные паттерны, а не абстрагируем преждевременно

#### Альтернативы рассмотрены
- **Расширить Ticket.parent_ticket_id до 3 уровней**: отвергнуто — усложнит существующие запросы и UI тикетов
- **Единая модель Task с полями для обоих доменов**: отвергнуто — смешивает FSM и нарушает SRP

---

### [2026-04-05] ADR-007: Шаблоны проектов как Python-константы, не БД-таблица

#### Статус
Принято

#### Контекст
При создании проекта нужны pre-configured фазы и задачи. Типы проектов: ЖК, БЦ, камеры, большая стройка. Вопрос: хранить шаблоны в БД (с UI редактирования) или как Python-константы?

#### Решение
Шаблоны — Python-константы в `backend/projects/templates.py` (dataclasses). Endpoint `GET /projects/templates` отдаёт их read-only. UI-редактор шаблонов в админке в MVP не делаем.

#### Обоснование
- MVP-принцип: 4 статичных шаблона покрывают 95% кейсов PASS24
- Проще тестировать: `TemplateDefinition` — чистые dataclasses, легко импортировать в unit-тесты
- Нет миграций при изменении шаблонов (только код)
- При первом деплое не нужен seed-скрипт

#### Последствия
- (+) Быстрая реализация (нет админки, нет CRUD endpoints, нет миграции seed-данных)
- (+) Шаблоны — часть кода, версионируются в git
- (-) Изменения требуют деплоя (не real-time)
- Митигация: если потребуется кастомизация, в v0.7 можно вынести в БД с миграцией из текущих констант

---

### [2026-04-06] ADR-008: ИНН как ключ синхронизации Bitrix24 ↔ ServiceDesk

#### Статус
Принято

#### Контекст
Нужно синхронизировать компании из Bitrix24 CRM с порталом Service Desk. Вопрос: по какому полю матчить записи?

#### Решение
ИНН компании (из `crm.requisite.list`, поле `RQ_INN`) — единственный unique-ключ синхронизации. В таблице `customers` поле `inn` имеет `UNIQUE INDEX`.

#### Обоснование
- **ИНН уникален**: каждая организация в РФ имеет уникальный ИНН
- **Не зависит от CRM**: если компания переедет из Bitrix24 в другую CRM — ИНН останется
- **DaData использует ИНН**: `findById/party` работает по ИНН, что даёт единый ключ для двух внешних систем
- **Не Bitrix24 ID**: `COMPANY_ID` привязан к конкретному порталу, при миграции данных он теряется

#### Последствия
- (+) Устойчивость к смене CRM
- (+) Единый ключ для Bitrix24 + DaData + ServiceDesk
- (-) Компании без ИНН (2 из 232) пропускаются при синхронизации
- (-) ИП могут менять ИНН (редко, но бывает)

---

### [2026-04-06] ADR-009: Двухуровневый поиск компаний (локальный + DaData)

#### Статус
Принято

#### Контекст
При создании тикета/проекта агент должен выбрать компанию. Если она не среди постоянных клиентов — нужно найти по реестру ФНС и создать.

#### Решение
Двухуровневый поиск в компоненте `CustomerSelect.vue`:
1. Сначала ILIKE-поиск по `customers` таблице (sync'нутые из Bitrix24)
2. Если < 3 результатов и query >= 3 символов → автоматический запрос в DaData (suggest/party)
3. Клик по DaData-результату → `POST /customers/create-by-inn` → компания в БД

#### Обоснование
- Быстро для 95% случаев: клиент уже в Bitrix24 → мгновенный autocomplete из БД
- Fallback на DaData для новых клиентов — не нужно выходить из формы
- Без ручного ввода адреса/КПП/ОГРН — всё подтягивается из DaData автоматически

#### Последствия
- (+) UX без трения: агент не уходит из формы для поиска компании
- (+) Данные компании всегда верные (из ФНС, а не от человека)
- (-) DaData бесплатный тариф: 10 000 запросов/сутки (достаточно)

---

### [2026-04-17] ADR-010: Идемпотентность inbound email через unique-индекс в БД

#### Статус
Принято

#### Контекст
В тикетах (пример #D6393659) дублировались клиентские сообщения из email-ответов. До фикса защитой от повторной обработки был только in-memory `set` в процессе воркера (`_processed_message_ids`): любой рестарт обнулял кеш, IMAP polling проходил `SINCE = 2 дня` и создавал повторные комментарии. На 501-м уникальном Message-ID `set.clear()` сбрасывал кеш полностью (не LRU), а письма без `Message-ID` вообще не дедуплицировались. Итого: ~98 дублей в 11 тикетах.

#### Решение
Перенести дедупликацию в БД: добавить колонку `ticket_comments.email_message_id VARCHAR(998) NULL` + частичный уникальный индекс `WHERE email_message_id IS NOT NULL`. В `_handle_reply` / `_handle_reply_by_subject` сохраняем Message-ID из письма и делаем `session.flush()` до записи файлов на диск: при `IntegrityError` — `rollback` + возврат `True` (чтобы polling не уходил в ветку «новый тикет»). Для писем без заголовка — synthetic `<synthetic-sha1(from+date+subject+body)@pass24-local>`. In-memory кеш переведён на `OrderedDict`-LRU как быстрый short-circuit, но авторитет — БД.

#### Обоснование
- In-memory set нельзя сделать «exactly once» на рестартуемом сервисе — это фундаментальное ограничение, а не баг дедупликации.
- Частичный unique-индекс по `email_message_id IS NOT NULL` не мешает legacy-комментариям без этого поля (миграция 022 его не бэкфилит — ретроактивно Message-ID взять неоткуда).
- Flush до записи файлов исключает orphan-вложения: если дубль — на диск ничего не пишется.
- Синтетический ID покрывает редкий случай писем без Message-ID (кастомные релеи, некоторые мобильные клиенты).

#### Последствия
- (+) «Одно письмо = один комментарий» гарантировано на уровне схемы, независимо от рестартов.
- (+) Orphan-файлы при дубле невозможны.
- (-) Миграция 022 оставляет старые комментарии с `email_message_id = NULL` — исторические дубли удалены отдельным backfill-скриптом `backend/scripts/dedup_ticket_comments.py` (группирует по `(author_id, text.strip())`, оставляет самый ранний).
- Митигация log-reload-гонки: в fix-коммите `51f4f02` закешировали `ticket.id[:8]` в локальную строку до flush, потому что после `rollback` ORM-атрибуты expired и lazy-reload из asyncpg-контекста валится в `MissingGreenlet`.

#### Расширение (2026-04-22, миграция 026)
Исходное решение закрывало только `_handle_reply` / `_handle_reply_by_subject` (новые комментарии из email-ответов). `_handle_new_ticket` (создание тикета из свежего письма) оставался на старой защите — TOCTOU-SELECT по `(title, contact_email, source='email')` в отдельной сессии, с рассогласованной нормализацией title (sirую subject против stripped-title при save). В апреле 2026 это дало 3-5 дублей одного письма при серии деплоев.

Симметричное применение того же паттерна: миграция **026** добавила `tickets.email_message_id VARCHAR(998) NULL` + частичный уникальный индекс `WHERE email_message_id IS NOT NULL`. `_handle_new_ticket` переписан на ту же связку `session.flush()` + `except IntegrityError` + `rollback`. Теперь оба inbound-пути (reply и new-ticket) защищены единообразно на уровне БД; три симметричных блока try/flush/IntegrityError в `inbound.py` (строки 592/690/845) — живое документирование паттерна. Cleanup pre-026 дублей — `backend/scripts/dedup_tickets.py` (non-destructive merge через `merged_into_ticket_id`, как ручной `/tickets/{id}/merge`).

Нового ADR для расширения не заводилось — это то же архитектурное решение, просто доведённое до полного покрытия inbound-канала. Отдельный ADR потребовался бы, если бы мы выбрали другой паттерн (advisory-locks, exactly-once queue, внешний idempotency-сервис).

---

### [2026-04-17] ADR-011: Telegram Bot v2 — aiogram 3 + PG FSM + отдельный домен

#### Статус
Принято

#### Контекст
Минимальный бот (`backend/notifications/telegram.py`, ~390 строк на raw httpx) умел только text-flow: «первое сообщение → тикет, последующие → комментарии». Не поддерживал inline keyboards, wizard'ы (multi-step create), FSM, account linking, уведомления с действиями, KB-deflection, CSAT. Для полноценного клиентского канала нужна проработанная архитектура обработчиков, хранилище состояний, и раздельный домен от notifications.

#### Решение
Переписать бот на **aiogram 3** с интеграцией через FastAPI webhook (`dp.feed_update(bot, update)`), **PostgreSQL FSM storage** (без Redis), deep link account binding с ghost-миграцией. Вынести код в отдельный пакет `backend/telegram/` (config, bot, webhook, handlers, middlewares, services, keyboards, storage, formatters). Старый модуль `backend/notifications/telegram.py` удалить, `notify_telegram_*` перенести в `backend/telegram/services/notify.py` с inline-кнопками и авто-отвязкой при 403.

#### Обоснование
- **aiogram 3** — современный async-фреймворк, удобные роутеры, FSM, middlewares, типизированные фильтры; активно поддерживается.
- **Raw httpx** — слишком много boilerplate для wizard'ов, FSM, inline-кнопок и их роутинга.
- **python-telegram-bot** — тяжелее, async-поддержка исторически хуже.
- **PostgreSQL FSM storage** — в проекте уже есть PG; Redis тащить ради FSM — лишняя зависимость.
- **Отдельный пакет** `backend/telegram/` — чётко отделяет канал от `notifications/` (email, websocket, projects).

#### Последствия
- (+) Menu-driven UX: создание заявок (wizard с KB-deflection), «мои заявки» с пагинацией, ответы/закрытие/CSAT, KB-поиск, AI-чат, PM-workspace (approvals).
- (+) Push-уведомления с inline-кнопками (ответить, открыть, оценить).
- (+) Account linking через deep link (токен, TTL 10 мин), миграция ghost-пользователей из старого бота.
- (-) +1 зависимость (`aiogram>=3.15`).
- (-) +2 таблицы (`telegram_fsm_state`, `telegram_link_tokens`) + 2 колонки в `users` (`telegram_linked_at`, `telegram_preferences`).
- (-) Объём кода: `backend/telegram/` ~2500 строк, 20+ файлов.
- Compat mode на 2 недели (`TELEGRAM_COMPAT_MODE` в `backend/telegram/config.py`): unlinked-пользователи продолжают работать по старому text-flow через `backend/telegram/handlers/compat.py`. После периода флаг вручную переводится в False.

---

Шаблон записи: `agent_docs/templates/adr.md`

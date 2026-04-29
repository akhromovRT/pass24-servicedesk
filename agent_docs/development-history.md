# История разработки

Правило: хранить только последние 10 записей. При добавлении новой переносить старые в
`agent_docs/development-history-archive.md`. Архив читать при необходимости.

---

Краткий журнал итераций проекта.

## Записи

### 2026-04-29 — feat(tickets): UX списка тикетов + критичный баг с email-вложениями (три задачи в одном релизе)

**Контекст:** агенты поддержки жаловались на три проблемы по интерфейсу списка тикетов и работе с тикетом. Все три закрыты одним релизом, потому что задачи 1 и 2 затрагивают одни и те же файлы (`TicketsPage.vue`, `stores/tickets.ts`).

**Задача 1 — pagination 20/50/100 default 50.** Раньше `per_page=20` хардкодом, на 1080p помещалось 14–15 карточек, агент много пагинировал. Сейчас:
- `frontend/src/stores/tickets.ts` — новый ref `perPage` со значением из `localStorage['tickets-per-page']` (валидация `[20, 50, 100]`, fallback 50). Функция `setPerPage(n)` пишет в localStorage и перезагружает первую страницу.
- `frontend/src/pages/TicketsPage.vue` — Paginator получил `:rows-per-page-options="[20, 50, 100]"`, `RowsPerPageDropdown` в template, и `current-page-report-template="{first}–{last} из {totalRecords}"`. Хэндлер `onPageChange` различает смену страницы и смену rows-per-page (PrimeVue эмитит то же `@page`).
- Backend не трогали — там уже было `le=100` (`backend/tickets/router.py:422-424`).

**Задача 2 — middle-click открывает в новой вкладке.** Раньше карточка `<article @click="router.push(...)">` — программная навигация, у браузера нет настоящего `<a href>`, поэтому Ctrl/Cmd-click и middle-click не работали. Сейчас:
- `frontend/src/pages/TicketsPage.vue` — `<article>` заменён на `<RouterLink :to="...">` с тем же контентом и классами. Браузер сам обработает middle-click → новая вкладка, Ctrl/Cmd-click → новая вкладка, обычный click → SPA-навигация через Vue Router.
- Удалена функция `openTicket(id)` — не используется.
- В CSS `.ticket-row` добавлены `text-decoration: none`, `color: inherit`, `:visited { color: inherit }` — нейтрализация дефолтных стилей якоря, чтобы карточка визуально не отличалась от прежнего `<article>`. Также `:focus-visible { outline: 2px solid #6366f1 }` для keyboard-нав.
- ProjectCard и ArticleCard имеют ту же проблему, но трогать не стали — пользователь явно просил только список тикетов.

**Задача 3 (КРИТИЧНО) — скриншоты и вложения от агента доходят клиенту по email.** Это был блокирующий баг: агент прикреплял файл, видел toast «Файл загружен», но в composer'е никаких следов файла не было, при «Отправить» комментарий создавался **без связи с этим файлом**, email клиенту приходил без attachments. Архитектура была частично готова (`Attachment.comment_id` существует с commit `2fccbd0`, `TicketConversation.vue` уже отображает inline по `comment_id`), но outbound-flow от агента не использовал эту инфраструктуру. Сейчас:

- `frontend/src/components/ticket/TicketComposeArea.vue` — переписан целиком:
  - State `pendingAttachments: ref<PendingAttachment[]>([])` накапливает загруженные файлы.
  - `<input type="file" multiple>` — несколько файлов за один диалог.
  - UI: chips под Textarea с превью (для image/* через `URL.createObjectURL`), имя, размер, кнопка ✕. Кнопка «Отправить» теперь активна, если есть текст ИЛИ хотя бы один файл (раньше только текст).
  - `removeAttachment(id)` шлёт DELETE на бэкенд, ревокает objectURL. На submit все ID идут в `addComment(...)`.
  - `onBeforeUnmount` — общий revokePreviews для memory-leak protection.
- `frontend/src/stores/tickets.ts:addComment` — новый необязательный параметр `attachment_ids?: string[]`, передаётся в payload только если массив непустой (бэкенд получит дефолт `[]`).
- `backend/tickets/schemas.py:CommentCreate` — новое поле `attachment_ids: list[str] = []` с docstring.
- `backend/tickets/router.py:add_comment` — после `commit/refresh` комментария делает `UPDATE attachments SET comment_id = comment.id WHERE id IN (:ids) AND ticket_id = :ticket_id AND comment_id IS NULL`. Защита от race / угона: только attachments этого тикета, ещё не привязанные ни к одному комменту. После UPDATE перечитывает Attachment-ы и формирует payload `[{storage_path, filename, content_type, size}]` для уведомления.
- `backend/tickets/router.py` — новый эндпоинт `DELETE /tickets/{ticket_id}/attachments/{attachment_id}`. Проверки: (1) attachment принадлежит этому тикету, (2) удалять может только uploader или staff, (3) запрещено удалять, если `comment_id IS NOT NULL` (исторические сообщения неизменяемы — отдаём 409). Файл с диска удаляется best-effort, ошибки логируются.
- `backend/notifications/email.py` — крупно расширен:
  - Новый helper `_build_mime_attachment(file_path, filename, content_type) -> MIMEBase | None`. Если файл недоступен — возвращает None, письмо уходит без него (защита от удалённого файла).
  - `_send_email(...)` принимает `attachments: list[dict] | None`. Если список не пуст — переключается с `MIMEMultipart("alternative")` на `MIMEMultipart("mixed")` со вложенным `alternative` для HTML и MIME-частями для файлов.
  - `notify_ticket_comment(...)` принимает `attachments: list[dict] | None`. Делит файлы на «помещаются в лимит ~20 МБ суммарно» и «слишком большие» (сортирует по возрастанию размера, чтобы максимизировать число уместившихся). Помещающиеся прикладываются к письму; превышающие — упоминаются в HTML списком со ссылкой на тикет в кабинете.
  - Лимит `_MAX_EMAIL_ATTACHMENT_BYTES = 20 * 1024 * 1024` — после base64-кодирования это даст ~26 МБ raw size, около типичного предела SMTP в 25 МБ.
  - Новый helper `_human_size(bytes)` — формат «1.2 МБ» / «512 КБ» для отображения в HTML и логах.

**Решения по уточнениям пользователя:**
- Pagination: dropdown 20/50/100, default 50, выбор в localStorage.
- Email size: ≤20 МБ (с запасом на base64) — attachment'ом, остальное — ссылками.
- Inline-img: НЕ делаем (MVP). Все вложения — обычные `Content-Disposition: attachment`. Inline через CID можно добавить отдельной задачей, если будет запрос.

**Что переиспользовали:**
- `Attachment.comment_id` (commit `2fccbd0`) — существующая инфраструктура линковки.
- `TicketConversation.vue` — уже фильтрует и показывает inline-attachments по `comment_id`. Благодаря этому в треде агентский комментарий с вложениями отображается правильно автоматически.
- `_is_reserved_address` (RFC 2606/6761 guard) и threading headers — без изменений.

**Что НЕ делали:**
- Inline image через Content-ID — отложено.
- Cleanup orphan-attachments (если агент закрыл вкладку, не отправив комментарий) — отдельная background-задача, нужен cron.
- Прогрессбар при upload (сейчас просто toast при ошибке) — UX-полировка.
- Drag&drop файлов в composer — отдельная задача, инпут пока через кнопку «прикрепить».

**Верификация:** `vue-tsc -b` (frontend) и `python -m py_compile` (backend) прошли без ошибок. End-to-end smoke-тест в браузере после deploy: прикрепить 2 PNG → отправить → проверить, что клиент получает письмо с обоими PNG attachment'ами, в треде комментарий с inline-thumbnail.

**Файлы:** `frontend/src/components/ticket/TicketComposeArea.vue` (переписан), `frontend/src/stores/tickets.ts` (+~30 строк), `frontend/src/pages/TicketsPage.vue` (~30 строк изменений), `backend/tickets/schemas.py` (+1 поле), `backend/tickets/router.py` (+~70 строк, новый DELETE-эндпоинт + линковка), `backend/notifications/email.py` (+~120 строк).

---

### 2026-04-29 — feat(chat-loader): drag-and-drop кнопки AI-виджета по 4 углам с persistence

**Проблема (от пользователя):** статические `data-offset-x/y` от админа сайта не покрывают все случаи перекрытия. На разных страницах одного и того же сайта виджет может мешать в одном месте и не мешать в другом, а пиксельная подгонка ломается при ресайзе/смене страницы. «Жёсткая привязка» неудобна.

**Что сделано:** конечный посетитель сайта может сам перетащить плавающую кнопку AI-помощника в любой из 4 углов. Snap к ближайшему углу по фактическому центру кнопки (не по точке курсора), позиция сохраняется в `localStorage` под ключом `pass24-chat-corner` для текущего домена и переживает перезагрузку. `data-position` остаётся как **начальный** угол до первого перетаскивания. Окно чата перепривязывается к выбранному углу: при кнопке вверху чат раскрывается **под** ней, при кнопке внизу — **над**. Drag отключён на mobile (`≤480px`) — там сохраняется текущее bottom-sheet поведение.

**Реализация (`frontend/public/chat-loader.js`):**
- CSS переписан на 4 corner-классы вместо одного фиксированного `right/bottom`: переключение угла = `classList.toggle('corner-…')` без перерасчёта inline-стилей. Bottom-sheet @media теперь срабатывает на оба `corner-bottom-*`.
- Pointer Events API (`pointerdown/move/up/cancel`) с `setPointerCapture` — единый код для мыши и тачпада, события не теряются за пределами viewport. `touch-action: none` на кнопке исключает конфликт с pan-скроллом.
- Порог 5px разделяет `click` и `drag`. После «настоящего» drag вешается `click`-handler с `{capture:true, once:true}` + `stopImmediatePropagation()` — гасим именно следующий синтетический click, не весь поток.
- При drag и кнопка, и iframe (если открыт) синхронно двигаются через `transform: translate(...)`, на iframe ставится `pointerEvents: none`, чтобы курсор не «провалился». На pointerup transform снимается **до** применения нового corner — иначе наложился бы двойной сдвиг.
- Snap считается по `getBoundingClientRect()` кнопки относительно центра viewport. Свободное «куда угодно» сознательно не делали — иначе кнопка может уйти за край при ресайзе/повороте.
- localStorage обёрнут в try/catch (Safari Private Mode отключает запись) — fallback на `data-position` без падения.
- На `≤480px` viewport drag не активируется (early return из `pointerdown`), курсор остаётся `pointer` — обычное touch-нажатие открывает чат.

**Документация:** в `docs/embed-ai-chat-guide.md` добавлен раздел «Перетаскивание (только desktop)» сразу после таблицы параметров; уточнена формулировка `data-position` («**Начальный** угол»); в раздел диагностики «Виджет перекрывает кнопки сайта» добавлена подсказка про drag как индивидуальное решение для конкретного посетителя без глобальных изменений.

**Что НЕ делалось:**
- Drag floating-чата на самом портале (`AiChat.vue`) — пользователь подтвердил скоуп = только embed.
- Свободное позиционирование «в пиксели» — отказались сознательно (риск ухода за viewport).
- Reset-кнопка «вернуть к default» — не запрашивалась; чтобы сбросить, посетитель просто перетягивает обратно.
- Анимация transition при snap — мгновенный snap проще и не вызывает «лагающего» ощущения.

**Проверка:** `node -c frontend/public/chat-loader.js` — синтаксис валиден. Реальный smoke-test через Playwright не проводился, нужно вручную: открыть тестовую HTML-страницу с `<script src=…/chat-loader.js>`, проверить (1) drag в каждый из 4 углов с прилипанием, (2) перезагрузку — кнопка остаётся в выбранном углу, (3) drag с открытым чатом — окно перепривязывается к новому углу, (4) на viewport ≤480px drag не работает, обычный click.

**Файлы:** `frontend/public/chat-loader.js` (+95/-25 строк), `docs/embed-ai-chat-guide.md` (+27/-1 строк).

**Follow-up того же дня:** дефолтный `data-offset-y` поднят с `24` до `88`. На скриншоте от пользователя кнопка чата перекрывала «Сохранить» в sticky-футере формы — drag решает это индивидуально, но глобально дефолт должен сразу проскакивать sticky-футеры (типичная высота 56–72px). Затронуты только новые посетители без сохранённой позиции в localStorage; кто уже перетянул — увидит свой угол. iframe также сдвинулся: `frameOffsetY = 88+76 = 164px` от края, окно тоже выше sticky-футеров. Документация (`docs/embed-ai-chat-guide.md`) обновлена: в таблице параметров новый дефолт, удалён устаревший пример `data-offset-y="80"` для перекрытия (теперь это и есть дефолт-кейс), раздел диагностики переписан с акцентом на «дефолт уже это решает + drag для частных случаев».

---

### 2026-04-29 — fix(sla): бизнес-часы паузы + единая точка истины через `compute_sla_state` (ADR-017)

**Проблема (от пользователя):** SLA-полоски в UI к утру «красные» у тикетов, созданных ночью или в выходные. В статусах ожидания клиента полоска визуально продолжает течь, хотя по логике SLA на паузе. По факту — половина списка с утра выглядит просроченной, реальных просрочек нет.

**Корень:** на бэке бизнес-часы (`deadline_with_business_hours`) и пауза по статусу/reply уже работали, но `TicketRead` не отдавал готовых дедлайнов — фронт сам считал «осталось» через `Date.now() - created_at - sla_total_pause_seconds * 1000` в линейном времени. Плюс `sla_total_pause_seconds` копил линейные секунды, отчего пауза «дарила» нерабочее время.

**Решение** (см. ADR-017):
1. Бизнес-часы вынесены в `backend/tickets/business_hours.py` (без зависимостей от моделей; добавлена `deadline_with_business_minutes`).
2. Новый `backend/tickets/sla_service.py` — `compute_sla_state(ticket, now) → SlaState` (response/resolve/active due_at, response/resolve/active remaining_seconds, is_paused). `remaining_seconds` может быть отрицательным = просрочено на `abs(value)`.
3. `Ticket.recompute_sla_pause` теперь копит **бизнес-секунды** (`business_hours_between(sla_paused_at, now) * 3600`).
4. `_check_sla_breaches` переведён на `compute_sla_state` (явное `if state.is_paused: continue`, watcher теперь следит за активной фазой — response пока нет первого ответа, иначе resolve).
5. `TicketRead` отдаёт 6 computed-полей через `@model_validator`. Миграции БД для новых полей не нужны — всё в памяти.
6. Фронт: `frontend/src/utils/sla.ts` (`buildResponseProgress`/`buildResolveProgress`/`buildActiveProgress`/`getPauseLabel`) + composable `useSlaProgress.ts`. Все `Date.now()`-вычисления удалены. `TicketSlaProgress.vue` и `TicketsPage.vue` рефакторены. В `TicketsPage` добавлен polling `setInterval(loadTickets, 60_000)` чтобы полоска не «замораживалась» при идле.
7. Миграция 028 — обнуление `sla_total_pause_seconds` для активных тикетов без активной паузы (старая семантика была линейной, новая — бизнес-секунды).

**Изменённые файлы:**
- Backend: `backend/tickets/business_hours.py` (новый), `backend/tickets/sla_service.py` (новый), `backend/tickets/sla_watcher.py` (рефакторинг), `backend/tickets/models.py` (recompute_sla_pause), `backend/tickets/schemas.py` (TicketRead + 6 полей).
- Frontend: `frontend/src/utils/sla.ts` (новый), `frontend/src/composables/useSlaProgress.ts` (новый), `frontend/src/components/ticket/TicketSlaProgress.vue` (на composable), `frontend/src/pages/TicketsPage.vue` (polling + helper), `frontend/src/types/index.ts` (+6 полей в Ticket), `frontend/package.json` (vitest + jsdom + @vue/test-utils), `frontend/vite.config.ts` (test config).
- Tests: `tests/test_business_hours.py` (10 тестов), `tests/test_sla_service.py` (12 тестов), `tests/test_sla_watcher.py` (адаптирован), `frontend/src/composables/__tests__/useSlaProgress.test.ts` (17 тестов).
- Docs: ADR-017 в `agent_docs/adr.md`.
- DB: миграция `migrations/versions/028_sla_pause_business_seconds.py`.

**Тесты:**
- Backend: `pytest tests/test_business_hours.py tests/test_sla_service.py tests/test_sla_watcher.py::test_active_pause_extends_effective_deadline -v` → 23/23 зелёные.
- Frontend: `npx vitest run` → 17/17 зелёные. `npm run build` → без TS-ошибок.
- Интеграционный `test_check_sla_breaches_ignores_active_pause` требует БД и пакет `greenlet` (в локальном системном Python 3.9 не установлен) — не запускается локально, покрывается CI.

### 2026-04-28 — feat: авто-привязка guest-тикетов из embed-виджета к Customer по поддомену

Гостевые тикеты, создаваемые через AI-виджет на сайтах клиентов формата `bristol.pass24online.ru`, теперь автоматически связываются с компанией в реестре постоянных клиентов. Раньше `Ticket.customer_id` оставался `NULL` — оператор поддержки руками привязывал каждую заявку. Это закрывает «вторую половину» истории про постоянных клиентов: запись от 2026-04-25 добавила UI-индикацию (бейдж «Постоянный», фильтры, `customer_is_permanent` в `TicketRead`), но индикация работала только для тикетов с уже проставленным `customer_id` — теперь embed-виджет проставляет его автоматически.

**Поток:** `chat-loader.js` читает `window.location.hostname` host-страницы и пробрасывает в iframe через `?host=…`. `ChatWidgetPage.vue` тащит значение в payload `POST /tickets/guest` как `embed_host`. Backend в `backend/utils/embed_host.extract_subdomain` извлекает `"bristol"` из `"bristol.pass24online.ru"`, ищет `customers WHERE subdomain = ? AND is_permanent_client AND is_active`. Найден — заполняет `Ticket.customer_id`, `company` (= `Customer.name`), `object_name` (если payload не задал собственное значение).

**Изменения:**
- Backend: миграция 027 (новая колонка `customers.subdomain` + частичный unique-индекс паттерном из 026), новое поле `Customer.subdomain`, новое поле `GuestTicketCreate.embed_host`, мэтч-логика в `backend/tickets/router.py:create_guest_ticket`, хелпер `backend/utils/embed_host.py`.
- Backend: seed-скрипт `backend/scripts/seed_customer_subdomains.py` (CSV `subdomain,inn` → UPDATE customers; идемпотентен; --dry-run; пример CSV рядом). До прогона скрипта поле у всех Customer'ов NULL и фича не активна — это известный prerequisite.
- Frontend: `chat-loader.js` подмешивает `?host=…`, `ChatWidgetPage.vue` читает `route.query.host` и шлёт как `embed_host`. Обратная совместимость сохранена (без поля backend ведёт себя как раньше).
- Tests: `tests/test_embed_host.py` (13 unit-тестов, прошли локально), `tests/test_guest_ticket_subdomain_match.py` (6 интеграционных против запущенного backend, добавлены в `ops-run-tests.yml` allowlist).
- Doc: ADR-016, дополненный раздел в `docs/embed-ai-chat-guide.md`.

**Безопасность:** `embed_host` приходит от клиента и теоретически подделывается через DevTools. На этапе 1 принимаем на веру (последствие подделки = тикет привязан не к той компании, у guest'а нет доступа на чтение). TODO в коде на сверку с `Referer`.

### 2026-04-25 — Постоянные клиенты Bitrix24 в Tickets: устранение рассинхрона UI и расширение фичи

**Контекст:** интеграция синхронизации компаний из Bitrix24 (`Customer.is_permanent_client`, scheduler 03:00, спека 2026-04-09) уже работала в тикетах через `Ticket.customer_id` и редактирование объекта, но имела три проблемы: (1) `CustomerSelect` на создании тикета возвращал всех клиентов, а `TicketObjectInfo` при редактировании — только постоянных; (2) `CustomerRead` и `/customers/search` не возвращали `is_permanent_client`, фронт не мог визуально выделить постоянных; (3) в списке тикетов не было фильтра «только от постоянных», в карточке — бейджа.

**Что сделано:**
- Backend: в `CustomerRead` и `/customers/search` добавлен `is_permanent_client` + параметр `permanent_only`. Постоянные сортируются в начало выдачи. `/tickets/objects/suggest` теперь возвращает `is_permanent_client` (всегда `true`, единая логика с `customers.router`).
- Backend: в `GET /tickets/` добавлены параметры `customer_id` и `customer_only_permanent` (фильтрация через подзапрос по `Customer.is_permanent_client`).
- Backend: в `TicketRead` добавлено поле `customer_is_permanent: Optional[bool]`. `Ticket` не имеет ORM relationship на `Customer` (только FK на уровне БД, миграция 012), поэтому добавлены хелперы `_resolve_customer_permanent_map`, `ticket_to_read`, `tickets_to_read` — резолвят флаг батчем за один запрос. Все 10 endpoint'ов, возвращающих `TicketRead`, переведены на эти хелперы.
- Frontend: в `CustomerSelect.vue` карточка опции получила бейдж «Постоянный» (золотая звёздочка), результаты сортируются с постоянными вверх. В `TicketObjectInfo.vue` появился новый prop `customerIsPermanent` и тот же бейдж рядом с именем клиента; `TicketSidebar.vue` его прокидывает. На странице списка тикетов (`TicketsPage.vue`) — тогл «Постоянные клиенты / Все клиенты» (для staff) и бейдж в meta-блоке карточки.
- Тесты: добавлены интеграционные тесты в `tests/test_customers.py` — `is_permanent_client` в ответе `/customers/search`, `permanent_only=true`, сортировка постоянных вверх, `/tickets/objects/suggest` (только permanent), `customer_is_permanent` в `TicketRead` (true/false/null), `customer_only_permanent` в `GET /tickets/`.

**Контракт API изменён:**
- `GET /customers/search` — каждый элемент теперь содержит `is_permanent_client: boolean`.
- `GET /customers/` (`CustomerRead`) — дополнено полем `is_permanent_client`.
- `GET /tickets/` — новые query: `customer_id`, `customer_only_permanent`.
- `GET /tickets/{id}` (`TicketRead`) — новое поле `customer_is_permanent: bool | null`.
- `GET /tickets/objects/suggest` — каждый элемент содержит `is_permanent_client: boolean`.

**Не в этом релизе:**
- ORM relationship `Ticket.customer` — оставлено как есть, чтобы не плодить миграции; вместо этого батч-резолв.
- Верификация sync на проде (POST `/customers/sync` + SQL + сверка имени `UF_CRM_PERMANENT_CLIENT`) — пункт плана 4, ожидает следующего сеанса/админ-доступа.
- SLA-приоритизация для постоянных клиентов.

**Файлы:** `backend/customers/router.py`, `backend/tickets/router.py`, `backend/tickets/schemas.py`, `frontend/src/components/CustomerSelect.vue`, `frontend/src/components/ticket/TicketObjectInfo.vue`, `frontend/src/components/ticket/TicketSidebar.vue`, `frontend/src/pages/TicketsPage.vue`, `frontend/src/stores/tickets.ts`, `frontend/src/types/index.ts`, `tests/test_customers.py`.

**Верификация:** `vue-tsc -b` (frontend) — без ошибок. `python -m py_compile` для всех изменённых backend-файлов — без ошибок. Pytest интеграционных тестов требует запущенного backend на `localhost:8000`, прогон отложен до следующего сеанса.

---

### 2026-04-24 — chat-loader: опции позиционирования AI-виджета (устранение перекрытия кнопок сайта)

**Проблема:** жители ЖК не могли нажать «СОХРАНИТЬ» на формах клиентских сайтов — круглая кнопка AI-помощника в правом нижнем углу перекрывала её (скриншот от пользователя). Loader `frontend/public/chat-loader.js` поддерживал только `data-host` и `data-z-index`, позиции `right:24px; bottom:24px` были жёстко зашиты в CSS.

**Что сделано:** расширен `chat-loader.js` четырьмя новыми data-атрибутами: `data-position` (`bottom-right` | `bottom-left` | `top-right` | `top-left`), `data-offset-x`, `data-offset-y`, `data-frame-gap`. CSS переведён на динамическую генерацию через mapping угол→пара `{h, v}`; кнопка и iframe всегда привязаны к одному углу. Mobile bottom-sheet (`@media ≤480px`) теперь применяется только для `bottom-*` позиций. Обратная совместимость: без атрибутов поведение идентично прежнему (24/24 + 16/100).

**Workaround клиенту со скриншота:** `data-offset-y="80"` в `<script>` — кнопка поднимется над sticky-футером с «Отмена/Сохранить».

**Верификация (Playwright, локальный http.server):** 4 тестовых HTML-страницы — default, offset-y=80, bottom-left, top-right + mobile 375×667. Для offset-y=80 проверен overlap с кнопкой «СОХРАНИТЬ» (`false`, зазор 16px). Для top-right на mobile подтверждено отсутствие bottom-sheet (bottom: auto, все 4 угла border-radius:20px).

**Документация:** `docs/embed-ai-chat-guide.md` — расширена таблица параметров (+4 строки), добавлен раздел диагностики «Виджет перекрывает кнопки сайта» с тремя решениями, уточнён FAQ про два чата.

**Не в этом релизе:**
- `data-hide-on-url` / скрытие виджета по селекторам страниц — откладывается до конкретного запроса
- программное API `window.PASS24Chat.open()` — как FAQ обещает

**Файлы:** `frontend/public/chat-loader.js`, `docs/embed-ai-chat-guide.md`.

---

### 2026-04-24 — self-hosted telegram-bot-api для вложений >20 МБ (гибридный режим, без downtime)

**Что сделано:** развёрнут отдельный VPS на Hetzner CX23 Nuremberg (`178.104.228.43`) с Docker-контейнером `aiogram/telegram-bot-api:latest` в режиме `--local` (поднимает лимит `getFile` с 20 МБ до 2 ГБ). Caddy `:80` с IP-allowlist проксирует запросы и отдаёт файлы из `/var/lib/telegram-bot-api`. Код pass24-servicedesk обновлён (PR #22): `_download_tg_file` параметризован по `settings.telegram_api_base` + новый `settings.telegram_file_api_base`; бранчинг для `--local` absolute-paths; `_MAX_TG_FILE_SIZE` 20→100 МБ. Удалена iCloud-конфликтная копия `ticket_service 2.py`, паттерн в `.gitignore`.

**Ключевое решение (ADR-015):** гибридный режим **без `logOut`**. Webhook остаётся на `api.telegram.org` (zero downtime), pass24-api дополнительно ходит на self-hosted **только за `getFile`** больших файлов. Read-only операции Bot API не требуют session-lockа, два сервера сосуществуют для одного бота. Избежан FLOOD_WAIT 10 минут в рабочее время.

**Инциденты по пути:**
- Timeweb DNS зоны `pass24pro.ru` не применяет добавленную запись `tg-api`: SOAserial не инкрементируется, NXDOMAIN на всех NS. Workaround — работаем по IP `178.104.228.43` напрямую, HTTP без TLS между VPS-ами (allowlist на Caddy + UFW). Домен и Let's Encrypt сертификат — в следующую итерацию после перехода DNS на другого провайдера.
- CI-деплой `PR #22` упал дважды с GHCR 502 — временный сбой GitHub Container Registry. Третий retry прошёл успешно.

**Креденшалы:** `API_ID`/`API_HASH` получены на `my.telegram.org` через SSH SOCKS-тунель через сам VPS (ru-IP `my.telegram.org` не отвечал). Служебный Telegram-аккаунт, креды в 1Password + `/opt/telegram-bot-api/.env` (chmod 600).

**Не в этом релизе:**
- pytest-контракт для `_download_tg_file` с monkeypatch на httpx — отдельным PR
- Cron job для чистки `/opt/telegram-bot-api/data/` (TDLib не удаляет старые файлы)
- Переезд DNS pass24pro.ru на Cloudflare / возврат к `tg-api.pass24pro.ru` + Let's Encrypt

**Файлы:** `backend/config.py`, `backend/telegram/services/ticket_service.py`, `.env.example`, `.gitignore` + новые `agent_docs/adr.md` (ADR-015), `agent_docs/guides/telegram-bot-api-self-hosted.md`, обновлён `agent_docs/architecture.md`, `agent_docs/index.md`. PR: [#22](https://github.com/akhromovRT/pass24-servicedesk/pull/22).

---

### 2026-04-22 — design: pass24-dev-agent (Bitrix24-чат → Claude Code → PR), план готов

**Что сделано:** спроектирован отдельный сервис `pass24-dev-agent`, который
будет работать как daemon на VPS `5.42.101.27` рядом с PASS24 Service Desk и
автоматизировать мелкие доработки портала через чат Bitrix24.

**Как работает (в одной фразе):** сообщение с `#develop` в чате «Доработка
servicedesk» → отдельная git-ветка и PR через `claude` CLI в git worktree →
прогресс возвращается реплаями в чат, финальный merge — руками.

**Принятые решения:**
- Bitrix24 Messenger чат «Доработка servicedesk» (чат существует, нужно
  только получить `BITRIX_CHAT_ID`)
- Транспорт: входящий webhook + polling `im.dialog.messages.get`
- Цепочки задач: reply-треды Bitrix + короткий hex-ID (`#a7f2`)
- Целевой репо: только `pass24-servicedesk` (захардкожено)
- Исполнитель: `claude` CLI subprocess + git worktree (не SDK/Messages API)
- Автономность: PR + Codex review, merge в `main` — вручную
- Хостинг: тот же VPS, systemd-юнит
- Доступ: любой участник чата, но есть env-рычаг `ALLOWED_USER_IDS`

**Артефакты:**
- Дизайн: `agent_docs/specs/2026-04-22-bitrix-dev-agent-design.md` (470 строк,
  13 разделов, 4 открытых вопроса)
- План: `agent_docs/plans/2026-04-22-pass24-dev-agent-plan.md` (12 этапов,
  ~1600 строк, TDD-формат с bite-sized задачами)
- Репозиторий кода `akhromovRT/pass24-dev-agent` **ещё не создан** — это
  шаг 0.1 плана

**Что НЕ сделано (для будущих сессий):**
- Реализация — вся от Этапа 0 до Этапа 12 впереди
- 4 открытых вопроса спеки (chat_id, scope webhook, Codex в claude-ране,
  GitHub PAT) нужно закрыть до старта

**Как возобновить:** открыть этот репо в Claude Code, сказать «продолжаем
pass24-dev-agent по плану `agent_docs/plans/2026-04-22-pass24-dev-agent-plan.md`».
Ассистент найдёт первую незакрытую `- [ ]` и начнёт. В начале плана —
секция «Как возобновить работу позже».

---

### 2026-04-22 — fix: дубли email-тикетов после рестарта — расширение ADR-010 на Ticket

**Симптом (прод):** несколько тикетов с одинаковым `title + contact_email + source=email`, создавались в окне ~8 часов (пример: 3× «Запрос на апи» от одного отправителя, 2× «Требуется помощь» от другого). Все уже были закрыты. Пользователь: «будто синхронизацию зажевало и он начал генерить по 4-5 заявок».

**Корневые причины (две связанные):**
1. **Рассогласование нормализации title в pre-insert дедупликации** (`backend/notifications/inbound.py::_handle_new_ticket`). `title_to_check = subject[:200] if subject else f"Обращение от {from_name}"` — сырой subject, без `strip()` и с собственным fallback'ом на «Обращение от X». Сохраняемый `title = subject.strip() if subject.strip() else body[:100].strip()` — нормализованный, с другим fallback'ом на `body`. Любой пробел на границах subject или пустой/whitespace-only subject — и SELECT не находил существующий тикет.
2. **Отсутствие DB-уровня идемпотентности для Ticket.** Миграция 022 добавила `ticket_comments.email_message_id UNIQUE WHERE NOT NULL` (ADR-010), но модель `Ticket` осталась без поля. Защита держалась только на TOCTOU-SELECT из п.1.

Пусковой механизм: `_fetch_unseen_emails` использует `SINCE <2 дня>` вместо `UNSEEN` (Яндекс помечает письма прочитанными до обработки), in-memory LRU `_processed_message_ids` сбрасывается при рестарте процесса. `docker compose up -d` во время деплоя кратковременно держит старый+новый контейнер, и каждый раз с холодным LRU бажная pre-insert-проверка проскакивала. N деплоев за 8 часов = N дублей.

**Что сделано:**
- Миграция `026_ticket_email_message_id.py` — `tickets.email_message_id VARCHAR(998) NULL` + частичный уникальный индекс `uq_tickets_email_message_id WHERE email_message_id IS NOT NULL` (зеркало миграции 022).
- `backend/tickets/models.py` — поле `email_message_id` на `Ticket` с документацией.
- `_handle_new_ticket` переписан под паттерн `_handle_reply`: убрана рассогласованная TOCTOU-проверка, добавлен `ticket.email_message_id = mail_data["message_id"]`, `session.flush()` до записи вложений на диск, `except IntegrityError → rollback → return` — дубль больше не создаёт ни тикет, ни orphan-файлы. Title нормализуется один раз (`subject.strip() or body[:100].strip()`, `[:200]`) и используется и для legacy-fallback-check, и для сохранения.
- **Legacy-fallback:** для pre-migration тикетов (`email_message_id IS NULL`) оставлена дополнительная проверка по нормализованному `(title, contact_email, source='email', email_message_id IS NULL)` — чтобы email, всё ещё висящее в IMAP SINCE-окне, не создало новый дубль рядом со старым без message_id. Легитимные новые письма с тем же subject от того же отправителя не блокируются (разные message_id).
- Интеграционные тесты в `tests/test_inbound_email_integration.py::TestTicketDeduplication`: (1) один `message_id` ×3 вызова → 1 тикет; (2) разные пробелы в subject + тот же `message_id` → 1 тикет (прямой regression-guard на исходный баг нормализации); (3) разные `message_id` + одинаковый subject → 2 тикета (чтобы legacy-fallback не ложно-блокировал).

**Открытое (будет отдельным PR):** cleanup-скрипт для уже накопленных дублей в БД. Merge-логика не тривиальна (надо сливать комментарии/вложения), и операцию лучше гонять с подтверждением на проде.

**Архитектурно:** прямое расширение ADR-010 (та же идея «БД как авторитет идемпотентности через уникальный частичный индекс», тот же паттерн flush + IntegrityError + rollback). Отдельный ADR не заводил — это не новое решение, а его доведение до symmetric-покрытия обоих inbound-путей (reply и new-ticket).

**Файлы:** `migrations/versions/026_ticket_email_message_id.py`, `backend/tickets/models.py`, `backend/notifications/inbound.py`, `tests/test_inbound_email_integration.py`, `agent_docs/development-history.md`

### 2026-04-22 — feat: embeddable AI-chat widget + UI-полировка + постмортем прод-инцидента

**Embed AI-chat widget для 250+ облачных сайтов клиентов (коммиты `91bbad7`, `ccef17b`):**
- `frontend/public/chat-loader.js` — vanilla JS loader (~130 строк), раздаётся статикой с `support.pass24pro.ru`. Создаёт floating-кнопку + iframe с `/chat-widget`. SVG через DOM API без innerHTML (XSS-safe), postMessage для collapse, Esc closes, responsive bottom-sheet на мобильных ≤480px.
- `frontend/src/pages/ChatWidgetPage.vue` — standalone Vue-страница с UI по референсу (тёмно-синяя шапка `#0f172a` с градиентным AI-аватаром, серые/тёмные пузыри, круглая зелёная кнопка отправки, inline guest-форма тикета с email/name/phone).
- `frontend/src/App.vue` — `isEmbed = route.path === '/chat-widget'`, в embed-режиме рендерит только `router-view` без navbar/Toast/floating AiChat/HelpModal.
- `frontend/src/router/index.ts` — новый lazy-роут `/chat-widget`.
- `docs/embed-ai-chat-guide.md` — полная инструкция (337 строк): архитектура, установка на WordPress / Tilda / Webflow / 1С-Битрикс / React-Next / Vue-Nuxt / статические сайты, параметры кастомизации, безопасность/CSP, диагностика, FAQ.
- Backend не трогали: catch-all SPA-роут уже отдаёт `chat-loader.js` как статику (Vite `public/` → `static/`), а `/assistant/chat` и `/tickets/guest` уже работали без авторизации. Iframe same-origin к `support.pass24pro.ru` — CORS отсутствует.
- **ADR-014:** зафиксировано решение «loader + iframe» vs. Web Component / NPM-пакет.

**Переименование статуса UI (коммит `a7c36be`):** в staff-интерфейсе «Ожидает ответа» → «Ожидание ответа клиента» (TicketsPage filter tab + dropdown + row label, TicketStatusBadge, useTicketTransitions, TicketSlaProgress pause badge, AnalyticsPage chart, HelpModal). Клиентские словари (userStatusLabels, email STATUS_LABELS) оставлены без изменений — клиент себя клиентом не называет.

**Индикатор «кто ответил последним» (коммиты `c109530` → `9982a17` → `ee48c6c`):** в списке активных тикетов бейдж «Отв.: клиент» (синий) / «Отв.: оператор» (серый). Backend: `ticket_comments.author_is_staff` (миграция 024 + 025-backfill-fix), `TicketRead.last_public_reply_by` через `@model_validator`. Починен по дороге баг миграции 024 — сравнение Postgres enum `userrole` с lowercase bare string → `InvalidTextRepresentationError` → crash loop на 15 мин. Fix: `::text` cast + повторный backfill с uppercase (миграция 025). Чек-лист безопасных миграций зафиксирован в ADR-013.

**RFC 2606 SMTP guard (коммит `74f9646`):** `_send_email` молча пропускает `example.com/.net/.org`, `.example`, `.test`, `.invalid`, `.localhost`. Причина — утром 20 апреля WF `Ops — run pytest on prod` с расширенным target прогнал интеграционные тесты, создав десятки тикетов с `test-<hex>@example.com`, bounce'ы от timeweb засорили inbox на 36+ писем. Ужесточили workflow: allowlist конкретных файлов + запрет пустого target. ADR-012 закрепил правило.

**Прод-инцидент 21 апреля вечером (частично не наш):** после деплоя виджета вскрылось зависание sshd/HTTPS на системном уровне (SSH banner timeout, TLS handshake timeout, но ICMP 0.5ms, load 0.1, контейнеры up). Первопричина — `System restart required` + 48-дневный uptime + накопленные неприменённые обновления ядра. Решение: reboot VM → все контейнеры встали автоматом через `restart: unless-stopped`. **Профилактика:** включить `Unattended-Upgrade::Automatic-Reboot "true"` или планировать reboot раз в 30-60 дней.

**Файлы:**
- Виджет: `frontend/public/chat-loader.js`, `frontend/src/pages/ChatWidgetPage.vue`, `frontend/src/App.vue`, `frontend/src/router/index.ts`, `docs/embed-ai-chat-guide.md`
- Staff-label: `TicketsPage.vue`, `TicketStatusBadge.vue`, `useTicketTransitions.ts`, `TicketSlaProgress.vue`, `AnalyticsPage.vue`, `HelpModal.vue`
- Индикатор ответа: `backend/tickets/models.py`, `schemas.py`, `router.py`, `notifications/inbound.py`, `backend/telegram/services/ticket_service.py`, `backend/scripts/sync_email_replies.py`, `frontend/src/pages/TicketsPage.vue`, `frontend/src/types/index.ts`
- Миграции: `024_ticket_comment_author_is_staff.py`, `025_fix_author_is_staff_backfill.py`
- SMTP guard: `backend/notifications/email.py`, `tests/test_email_reserved_guard.py`, `.github/workflows/ops-run-tests.yml`
- ADR: `agent_docs/adr.md` (ADR-012, 013, 014)

### 2026-04-20 — hardening: Telegram Bot v2 post-rollout + user guide + все 4 follow-up TODO закрыты

Накопительная запись по серии мелких фиксов после мёрджа Telegram Bot v2 в main. Ссылки в формате `#<PR>`.

**Производственные баги, вскрытые сразу после мёрджа:**
- `#7` — `npm ci` падал, потому что Task 5 добавил `qrcode` / `@types/qrcode` в `package.json`, но не пересобрал `package-lock.json`. Ломало прод-деплой. Лок-файл пересобран локально, закоммичен.
- `#8` — QR-карточка исчезала через 0 секунд. Backend возвращал `expires_at.isoformat()` без суффикса `Z`, браузер в MSK (+3) интерпретировал naive-ISO как local time — «будущая» дата оказывалась в прошлом. Теперь всегда `isoformat() + "Z"`.
- `#11` — rate-limit `/auth/telegram/link-token` считал все токены с `expires_at > now-1h` (историческое окно ~70 мин). Юзер, несколько раз попробовавший из-за бага #8, блокировался на час. Заменён на подсчёт только **pending** (не истёкших и не использованных) — «max 5 одновременных invite-link на аккаунт»; истечение/потребление сразу освобождает слот.
- `#17` — `webhook` возвращал 500 при любом исключении в хендлере (пример — `TelegramBadRequest: chat not found` при ответе в фейковый chat_id из тестов). Telegram на 500 ретраит update экспоненциально до 24 ч. Теперь `try/except` + `logger.exception` + всегда 200. Фикс критичен для production-resilience.

**4 follow-up TODO закрыты:**
1. Producer-wiring уведомлений approval/milestone/risk (PR commit `19f7516`): helper `_get_linked_pm(project_id)` + `notify_pm_approval_request` / `notify_pm_milestone` / `notify_pm_risk` в `notify.py`. Вкручены в `projects/workspace_router.request_approval` + `create_risk` (await с try/except) и `projects/router.complete_phase` (через BackgroundTasks).
2. `ArticleFeedback` persistence из KB-кнопок 👍/👎 бота (`7853a7e`): `session_id=f"tg:{user.id}"` для идемпотентности per (user, article), `source="telegram"`, инкремент `article.helpful_count` / `not_helpful_count`.
3. CSAT scheduler через 24 ч после resolve (`8595618`): `backend/tickets/csat_scheduler.py` — async loop, интервал 1 ч. Использует существующее поле `satisfaction_requested_at` как sent-flag (SQL trick: `WHERE satisfaction_requested_at <= resolved_at` → scheduler после отправки продвигает timestamp, следующая итерация уже не выбирает тикет). Без schema change.
4. Shared FTS service (`837f2ba` + `a27f13c`): `backend/knowledge/services.py::search_articles_with_fts()` — одна реализация на `backend/knowledge/router.py::search_articles` + `backend/telegram/services/kb_service.py`. SQL больше не дублируется, удалено ~180 строк.

**Ops-инфраструктура для тестов на проде:**
- `#14` — `tests/` включены в docker image (раньше были в `.dockerignore`).
- `#16` — `pytest.ini` с `asyncio_default_{fixture,test}_loop_scope = session`. pytest-asyncio default = function-scope, kill'ит asyncpg-connections между тестами → "another operation in progress" на всех DB-тестах. Session scope — один event loop на сьюту, пул живёт.
- `#15` — workflow `ops/run-tests.yml` (`workflow_dispatch`, SSH в прод, `docker exec ... pytest`) с переменной `PYTEST_TARGET`. Изначально называлась `TARGET` — drone-ssh (подложка `appleboy/ssh-action`) клоббрит собственную `$TARGET`, переменная молча превращалась в путь к бинарю. Переименовано.
- `ops/diag-logs.yml` — `workflow_dispatch` для `docker logs` с allowlist на `--tail`.

**Тесты:** `tests/test_telegram_bot.py` + `tests/test_telegram_webhook.py` — **38/38 passed** на проде через `ops/run-tests`. Полная сьюта: 238 passed, 8 pre-existing failures (English-vs-Russian phase names в шаблонах проектов, FSM transition semantics, email signature cleaner — не связаны с telegram).

**User guide:** `agent_docs/telegram-bot-user-guide.md` — 14 разделов (~600 строк) покрывают весь UX: linking, wizard, list, reply/close/CSAT, KB, AI, PM projects/approvals, settings, push-notifications, FAQ. `agent_docs/screenshots/telegram/01-idle.png` + `02-qr.png` сняты автоматически через Playwright; 25 bot-скринов ждут ручного прохода по боту. Чеклист статусов в заголовке MD.

**Файлы (укрупнённо):** `backend/telegram/{webhook,services/notify,services/linking,services/kb_service}.py`, `backend/telegram/handlers/kb.py`, `backend/tickets/csat_scheduler.py`, `backend/knowledge/services.py`, `backend/main.py` (lifespan), `backend/projects/{router,workspace_router}.py`, `.github/workflows/{deploy,ops-run-tests,diag-logs}.yml`, `frontend/package-lock.json`, `Dockerfile`, `pytest.ini`, `agent_docs/telegram-bot-user-guide.md`.

### 2026-04-20 — fix: Telegram Bot API через reverse-proxy (RU-хостер блокирует 149.154.160.0/20)

**Инцидент:** Бот @PASS24bot перестал отвечать на `/start` и `/help`. Входящие апдейты Telegram **доходят** до webhook, но исходящий `sendMessage` из контейнера падает с `aiogram.exceptions.TelegramNetworkError: Request timeout error` (60 с, таймаут сессии по умолчанию). С контейнера `httpx.get("https://api.telegram.org")` → `[Errno 101] Network is unreachable` (DNS резолвит, TCP :443 блокируется). Google/GitHub доступны — блок избирательный по подсетям Telegram, специфика российских хостеров.

**Что сделано:**
- `backend/config.py` — добавлена `telegram_api_base: str = ""`.
- `backend/telegram/config.py` — экспорт `TELEGRAM_API_BASE`.
- `backend/telegram/bot.py` — если `TELEGRAM_API_BASE` задан, `Bot(session=AiohttpSession(api=TelegramAPIServer.from_base(TELEGRAM_API_BASE)))`. Иначе — дефолтный api.telegram.org.
- `backend/telegram/services/notify.py` — `_TG_API` теперь читает ту же переменную (push-уведомления идут напрямую через httpx, не через aiogram session).
- `.env.example` — задокументирована переменная вместе с `TELEGRAM_BOT_TOKEN`/`TELEGRAM_WEBHOOK_SECRET`/`APP_BASE_URL`.
- `agent_docs/architecture.md` — в разделе Telegram-канал описан reverse-proxy и требование сохранять `/bot<token>/<method>` + `/file/bot<token>/<path>`.

**Деплой:** на стороне существующего LLM-шлюза `45.82.15.28:8080` нужно добавить location `^/telegram/` с `proxy_pass https://api.telegram.org/`. В `docker-compose.yml` на VPS — `TELEGRAM_API_BASE: http://45.82.15.28:8080/telegram`. На стороне Telegram ничего не меняется: сам `setWebhook` уже выставлен и принимает апдейты.

**Файлы:** `backend/config.py`, `backend/telegram/config.py`, `backend/telegram/bot.py`, `backend/telegram/services/notify.py`, `.env.example`, `agent_docs/architecture.md`.

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

**Follow-up TODO:** все 4 закрыты в записи «2026-04-20 — hardening: Telegram Bot v2 post-rollout» (producer-wiring approval/milestone/risk, `ArticleFeedback` persistence, CSAT scheduler, shared FTS refactor).

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
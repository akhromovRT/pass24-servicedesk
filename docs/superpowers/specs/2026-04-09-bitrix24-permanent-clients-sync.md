# Bitrix24: синхронизация постоянных клиентов + привязка к заявкам

**Дата:** 2026-04-09
**Статус:** Approved

## Проблема

Объекты обслуживания (ЖК, БЦ) в Service Desk хранятся как свободный текст в тикетах. Нет связи с CRM, нет единого справочника. Агенты вручную вписывают названия, возникают дубли и ошибки.

## Решение

Синхронизировать постоянных клиентов из Bitrix24 (компании с флагом `UF_CRM_PERMANENT_CLIENT = true`) в таблицу `customers` Service Desk. Заявки привязываются к клиенту через `customer_id`. Синхронизация запускается автоматически каждый день в 03:00.

## Bitrix24 API

- **Портал:** `pass24pro.bitrix24.ru`
- **Webhook:** `BITRIX24_WEBHOOK_URL` (уже настроен)
- **Поле фильтра:** `UF_CRM_PERMANENT_CLIENT` (boolean, чекбокс "Постоянный клиент")
- **Метод:** `crm.company.list` с фильтром `{"UF_CRM_PERMANENT_CLIENT": true}`
- **Кол-во постоянных клиентов:** ~192

## Backend

### Миграция 020

Добавить поле `is_permanent_client BOOLEAN DEFAULT false` в таблицу `customers`.

### Обновление sync (`backend/customers/bitrix24_sync.py`)

Текущий `sync_companies()`:
- Тянет ВСЕ компании из Bitrix24
- Маппит INN через `crm.requisite.list`

Изменения:
- Дополнительно запрашивать поле `UF_CRM_PERMANENT_CLIENT` в `crm.company.list`
- При upsert в `customers` проставлять `is_permanent_client = True/False` из Bitrix24
- Логика upsert не меняется — по-прежнему ищем по INN

### Фоновая синхронизация (`backend/customers/sync_scheduler.py`)

Новый модуль с функцией `bitrix24_sync_loop()`:
- Запускается в `main.py` lifespan как `asyncio.create_task()`
- Бесконечный цикл: каждые 60 секунд проверяет текущее время
- Если время = 03:00 (и синхронизация ещё не запускалась сегодня) — вызывает `sync_companies()` + `sync_contacts()`
- Логирует результат

### Endpoint `GET /tickets/objects/suggest`

Переделать: вместо `SELECT DISTINCT object_name FROM tickets` — запрос к `customers WHERE is_permanent_client = true`. Поиск по `name` (ILIKE). Возвращает:

```json
[{"id": "uuid", "name": "ТСЖ Барвиха-2", "address": "...", "phone": "..."}]
```

### Endpoint `PUT /tickets/{id}/object`

Расширить payload:
```python
class TicketObjectUpdate(BaseModel):
    customer_id: Optional[str] = None  # NEW
    object_name: Optional[str] = None
    object_address: Optional[str] = None
    access_point: Optional[str] = None
```

При получении `customer_id` — записать в `ticket.customer_id`.

## Frontend

### `TicketObjectInfo.vue`

Переделать режим редактирования:
- AutoComplete ищет по `GET /tickets/objects/suggest?q=...`
- При выборе клиента: заполняет `customer_id`, `object_name` (из name), `object_address` (из address)
- Поля `object_address` и `access_point` остаются редактируемыми вручную
- Можно вписать объект вручную без привязки к клиенту (customer_id = null)
- В режиме просмотра: если привязан клиент — показывать имя + адрес + телефон

## Что не трогаем

- `CustomerSelect.vue` — используется при создании тикетов, другой контекст
- `POST /customers/sync` — оставляем для ручной синхронизации
- Контакты (`sync_contacts()`) — продолжают работать как раньше
- Текстовые поля `object_address`, `access_point` — остаются для ручных уточнений

---

## Changelog

### 2026-04-25 — расширение фичи в Tickets (рассинхрон UI устранён, бейдж и фильтр добавлены)

Что доделано относительно изначальной спеки:

**API:**
- `CustomerRead` и `GET /customers/search` теперь возвращают `is_permanent_client: boolean`. Постоянные сортируются в начало выдачи.
- `GET /customers/search` принимает `permanent_only: boolean` — для случаев, когда нужно ограничить выборку только постоянными.
- `GET /tickets/` принимает новые query: `customer_id` (фильтр по конкретной компании) и `customer_only_permanent` (только заявки от постоянных клиентов).
- `GET /tickets/{id}` (`TicketRead`) дополнен полем `customer_is_permanent: boolean | null`.
- `GET /tickets/objects/suggest` теперь возвращает `is_permanent_client` в каждом элементе (всегда `true` благодаря фильтру эндпоинта).

**Backend (`backend/tickets/router.py`):**
- Добавлены хелперы `_resolve_customer_permanent_map`, `ticket_to_read`, `tickets_to_read` — батч-резолв `customer_is_permanent` одним запросом (нет ORM relationship `Ticket.customer`, поэтому через подзапрос).
- Все 10 endpoint'ов, возвращающих `TicketRead`, переведены на эти хелперы (create, list, get, status update, priority, assignment, object, merge, apply-macro, satisfaction).

**Frontend:**
- `CustomerSelect.vue` — бейдж «Постоянный» в карточке опции автокомплита, сортировка постоянных в начало.
- `TicketObjectInfo.vue` — новый prop `customerIsPermanent` и тот же бейдж рядом с именем клиента; пробрасывается из `TicketSidebar.vue`.
- `TicketsPage.vue` — тогл «Постоянные клиенты / Все клиенты» в шапке (только для staff) и бейдж в meta-строке карточки.
- `stores/tickets.ts` — `TicketFilters` дополнен `customer_id` и `customer_only_permanent`, прокидываются в API.
- `types/index.ts` — `Ticket.customer_is_permanent: boolean | null`.

**Тесты (`tests/test_customers.py`):**
- Возврат `is_permanent_client` в `/customers/search`.
- `permanent_only=true` фильтрует не-постоянных.
- Сортировка постоянных в начало выдачи.
- `/tickets/objects/suggest` возвращает только постоянных.
- `customer_is_permanent` в `TicketRead`: true / false / null.
- `customer_only_permanent` в `GET /tickets/`.

**Документация:**
- Новый гид: `agent_docs/guides/permanent-clients.md` — что такое постоянный клиент, где видно, как фильтровать, API, FAQ.
- Обновлён `agent_docs/guides/support-operations.md` (раздел про фильтры и маркеры в строке заявки).
- В `HelpModal.vue` (встроенное руководство агента) добавлен раздел «🌟 Постоянные клиенты».
- Запись в `agent_docs/development-history.md` от 2026-04-25.

**Не вошло (оставлено на потом):**
- ORM relationship `Ticket.customer` (вместо батч-резолва).
- Отдельный селектор компании в фильтрах списка тикетов (сейчас только через API `customer_id`).
- SLA-приоритизация для постоянных клиентов.
- Верификация sync на проде (POST `/customers/sync` + SQL + сверка имени `UF_CRM_PERMANENT_CLIENT` через `crm.company.fields`).

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

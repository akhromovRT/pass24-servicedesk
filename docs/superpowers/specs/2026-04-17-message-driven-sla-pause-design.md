# Message-driven SLA pause — Design

**Статус:** Draft
**Дата:** 2026-04-17
**Автор:** Алексей Хромов (+ Claude)

## 1. Проблема

SLA-«решение» сейчас ставится на паузу **только** при ручном переводе тикета в статус `waiting_for_user` или `on_hold`. Если сотрудник поддержки ответил клиенту публичным комментарием, но статус не сменил (например, остался в `in_progress`, или первый ответ из `new` перевёл в `in_progress`), таймер продолжает идти и может «сгореть», пока мяч на стороне клиента.

Корневая причина: пауза state-driven (через статус), а не message-driven (по автору последней реплики). Регламент `support-operations.md` компенсирует это требованием ручного действия, но на практике агенты забывают переключать статус, особенно на первом ответе.

## 2. Цель

SLA-«решение» автоматически встаёт на паузу, когда последний **публичный** комментарий в тикете написан сотрудником (`support_agent` / `admin`), и снимается с паузы, когда следующий публичный комментарий написан клиентом. Статус тикета **не меняется автоматически** — им управляет агент.

## 3. Не-цели

- Не трогаем первое SLA (`sla_response_hours`) — оно фиксируется моментом `first_response_at` и не подвержено паузам.
- Не меняем ручные статусы `waiting_for_user` / `on_hold` / `engineer_visit` — пауза по статусу продолжает работать как сейчас.
- Не ретро-применяем новую паузу к историческим тикетам (backfill ставит `sla_paused_by_reply = false`, чтобы не «разморозить» задним числом статистику).
- Внутренние комментарии (`is_internal = true`) не участвуют в расчёте — клиент их не видит, значит по его ощущению оператор не отвечал.

## 4. Модель

### 4.1. Схема БД

Добавляем в `tickets` две boolean-колонки (миграция `019`):

| Поле | Тип | Default | Смысл |
|---|---|---|---|
| `sla_paused_by_status` | `bool` | `false` | Активна пауза по статусу (`waiting_for_user` или `on_hold`). |
| `sla_paused_by_reply` | `bool` | `false` | Активна пауза по последнему публичному комментарию от staff. |

Существующие `sla_paused_at` / `sla_total_pause_seconds` **оставляем без изменений** — они и так отражают сводную паузу, теперь её источников два.

**Backfill:**
- `sla_paused_by_status = (status IN ('waiting_for_user','on_hold'))` для всех тикетов.
- `sla_paused_by_reply = false` для всех тикетов (не ретроспективно).

Проверка: если у тикета `status = waiting_for_user` уже была активная пауза (`sla_paused_at IS NOT NULL`), — оставляем как есть (состояние согласовано).

### 4.2. OR-семантика паузы

Пауза считается активной, когда `sla_paused_by_status OR sla_paused_by_reply = true`. Переход активности в обе стороны делается **единым методом**:

```python
# Ticket.recompute_sla_pause(self, now: datetime) -> None
was_paused = self.sla_paused_at is not None
should_pause = self.sla_paused_by_status or self.sla_paused_by_reply

if should_pause and not was_paused:
    self.sla_paused_at = now
elif not should_pause and was_paused:
    self.sla_total_pause_seconds += int((now - self.sla_paused_at).total_seconds())
    self.sla_paused_at = None
# иначе (состояния совпадают) — no-op
```

Этот метод — **единственная точка** изменения `sla_paused_at` / `sla_total_pause_seconds`. Существующий код в `Ticket.transition()`, который делает то же самое вручную, упрощается: transition обновляет `sla_paused_by_status` и вызывает `recompute_sla_pause(now)`.

## 5. Точки интеграции

### 5.1. `Ticket.transition()` (backend/tickets/models.py)

```python
# вместо нынешней прямой работы с sla_paused_at:
self.sla_paused_by_status = new_status in (TicketStatus.WAITING_FOR_USER, TicketStatus.ON_HOLD)
self.recompute_sla_pause(now)
```

### 5.2. Новый метод `Ticket.on_public_comment_added(author_is_staff, now)`

```python
self.sla_paused_by_reply = bool(author_is_staff)
self.recompute_sla_pause(now)
```

Вызывается из **всех путей создания публичного комментария**:

| Файл | Строка | Источник | `author_is_staff` |
|---|---|---|---|
| `backend/tickets/router.py` | ~850 (`add_comment`) | Web UI | `current_user.role ∈ {support_agent, admin}` |
| `backend/tickets/router.py` | ~1579 (macros) | Web UI (массовое действие) | как выше |
| `backend/notifications/inbound.py` | ~527 (`_handle_reply`) | Email-ответ клиента | `false` (inbound = клиент) |
| `backend/notifications/inbound.py` | ~606 (`_handle_reply_by_subject`) | Email-ответ клиента | `false` |
| `backend/notifications/telegram.py` | ~270 | Telegram клиента | `false` |
| `backend/scripts/sync_email_replies.py` | ~256 | maintenance-скрипт | `false` (исторические ответы клиентов) |

`backend/projects/workspace_router.py:426` работает с `ProjectComment` (workspace проектов внедрения), а не с `TicketComment` — к SLA тикетов отношения не имеет и в схему интеграции не включается.

Internal-комментарии пропускаем (`if is_internal: skip recompute`).

### 5.3. SLA watcher (`backend/tickets/sla_watcher.py`)

Два изменения:

**A. Учесть активную паузу в расчёте дедлайна.** Сейчас:

```python
pause_sec = t.sla_total_pause_seconds or 0
deadline = deadline + timedelta(seconds=pause_sec)
```

Станет:

```python
pause_sec = t.sla_total_pause_seconds or 0
if t.sla_paused_at is not None:
    pause_sec += int((datetime.utcnow() - t.sla_paused_at).total_seconds())
deadline = deadline + timedelta(seconds=pause_sec)
```

Это фиксит **существующий** скрытый баг: при текущей активной паузе (например, `waiting_for_user`) `pause_sec` не растёт, и warning мог бы ложно сработать. Сейчас это маскируется фильтром `status IN (new, in_progress, engineer_visit)` — с message-driven паузой такие тикеты могут быть и в `in_progress`, поэтому защита ломается без этого фикса.

**B. Расширить фильтр тикетов.** Оставляем текущий `status IN (...)` без изменений — breach warning по-прежнему имеет смысл только для активно-рассматриваемых тикетов. Reply-пауза может возникать в этих же статусах, дедлайн корректно учтёт её через пункт A.

## 6. API и фронтенд

### 6.1. API-схема (`backend/tickets/schemas.py`)

В `TicketRead` добавить:

```python
sla_paused_by_status: bool = False
sla_paused_by_reply: bool = False
```

### 6.2. Frontend-тип (`frontend/src/types/index.ts`)

```typescript
sla_paused_by_status: boolean
sla_paused_by_reply: boolean
```

### 6.3. UI-подсказка (`TicketSlaProgress.vue`)

Над прогресс-баром «Решение» показывать бейдж, когда активна пауза:

- `sla_paused_by_reply && !sla_paused_by_status` → бейдж **«⏸ SLA на паузе — ждём ответ клиента»** (серый, с иконкой pause)
- `sla_paused_by_status` (в т.ч. в комбинации с reply) → бейдж **«⏸ SLA на паузе — статус «{label}»»** с `{label}` = «Ожидает ответа» / «Отложена» в зависимости от статуса.

Прогресс-бар в паузе окрашивается в серый (`#94a3b8`), `formatRemaining` подменяется на «На паузе». Существующая логика расчёта `calcElapsedHours` уже корректна — вычитает активную паузу из прошедшего времени.

## 7. Регламент

`agent_docs/guides/support-operations.md`, раздел «3.4. Решение заявки»:

- **Вариант A** — без изменений (быстрое решение).
- **Вариант B** — убрать предписание «переведите в Ожидает ответа»; заменить фразой: «SLA автоматически встанет на паузу, пока клиент не ответит. Статус «Ожидает ответа» используйте как явный маркер, если нужно».
- **Вариант C** — без изменений, но добавить примечание: «если написали клиенту сообщение — SLA автоматически на паузе до его ответа».
- **Вариант D** — без изменений (on_hold).

## 8. Тесты

### 8.1. Unit (`tests/test_tickets_models.py`)

- `test_recompute_sla_pause_transitions` — 4 кейса: none→reply, none→status, reply+status, → none.
- `test_transition_updates_paused_by_status` — переходы в WAITING_FOR_USER/ON_HOLD выставляют флаг, выход — снимает.
- `test_on_public_comment_added_staff_then_client` — staff → паузится, client → снимается, сумма накопилась.
- `test_internal_comment_does_not_change_reply_flag`.

### 8.2. Интеграция (`tests/test_inbound_email_integration.py`)

- Клиент отвечает по email → `sla_paused_by_reply = false`, `sla_paused_at = None`.
- Пре-условие: искусственно поставим `sla_paused_by_reply = true, sla_paused_at = now - 1h` → после обработки ответа `sla_total_pause_seconds` увеличится ~на 3600.

### 8.3. SLA watcher

- Новый `tests/test_sla_watcher.py` (или дополнение существующего): тикет в `in_progress` с `sla_paused_at = now - 1h`, sla_resolve_hours = 1, total_pause = 0 → watcher **не** должен отправлять warning (активная пауза сдвигает дедлайн).

## 9. Миграция

`migrations/versions/019_add_sla_pause_flags.py`:

- `upgrade`: добавить две колонки (`server_default='false'`), backfill `sla_paused_by_status`.
- `downgrade`: удалить колонки.

## 10. План реализации (верхнеуровнево)

1. Миграция + backfill.
2. Модель: поля, `recompute_sla_pause`, `on_public_comment_added`, рефакторинг `transition`.
3. Schema `TicketRead` + frontend-тип.
4. Все 6 точек вызова `on_public_comment_added` + internal-guard.
5. `sla_watcher`: учёт активной паузы.
6. UI: бейдж и серая раскраска прогресса.
7. Тесты (unit + интеграция + watcher).
8. Правки `agent_docs/guides/support-operations.md`.
9. Запись в `agent_docs/development-history.md`.

Детальный плановый документ — следующим шагом через skill `writing-plans`.

## 11. Риски и открытые вопросы

- **Одновременность событий** — если статус и комментарий меняются одним HTTP-запросом (макрос), порядок вызовов `on_public_comment_added` и `transition` должен быть детерминирован. Соглашение: сначала `on_public_comment_added` (если есть комментарий), затем `transition` (если есть смена статуса); оба вызывают `recompute_sla_pause`, последний победит — это корректно.
- **Обратная совместимость фронтенда** — новые поля `sla_paused_by_*` будут `optional` в TypeScript-типе на случай кэшей/старых билдов.
- **Маленькое окно гонки** при сохранении флагов: `recompute_sla_pause` читает `sla_paused_at`, поэтому все вызовы в рамках одной сессии должны происходить последовательно до `session.commit()`. Это соблюдено во всех точках — комментарий и тикет коммитятся атомарно.

## 12. Оценка

- Backend: ~150 строк (миграция + модель + 6 интеграций + watcher).
- Frontend: ~30 строк в `TicketSlaProgress.vue` + тип.
- Тесты: ~100 строк.
- Документация: 10–20 строк правок `support-operations.md`.

Суммарно 1 импл-сессия.

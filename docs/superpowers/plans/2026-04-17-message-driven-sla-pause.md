# Message-driven SLA pause — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Автоматически ставить SLA-«решение» на паузу, когда последний публичный комментарий в тикете — от сотрудника поддержки, и снимать паузу при ответе клиента. Статус тикета при этом не меняется автоматически.

**Architecture:** Двa булевых флага (`sla_paused_by_status`, `sla_paused_by_reply`) на `tickets` объединяются OR-семантикой. Единый метод `Ticket.recompute_sla_pause(now)` конвертирует комбинацию флагов в установку/снятие существующих `sla_paused_at` / `sla_total_pause_seconds`. Новый метод `Ticket.on_public_comment_added(is_staff, now)` вызывается из всех 5 путей создания публичного комментария (web, web-макрос, email×2, telegram). SLA watcher учитывает активную паузу при расчёте дедлайна.

**Tech Stack:** Python 3.12, FastAPI, SQLModel, Alembic, PostgreSQL 16, pytest-asyncio, Vue 3, TypeScript, PrimeVue.

**Spec:** `docs/superpowers/specs/2026-04-17-message-driven-sla-pause-design.md`

---

## Сводка файлов

**Создаются:**
- `migrations/versions/021_add_sla_pause_flags.py` — миграция двух колонок + backfill
- `tests/test_sla_watcher.py` — юнит-тесты watcher с активной паузой

**Изменяются (backend):**
- `backend/tickets/models.py` — два поля на `Ticket`, `recompute_sla_pause`, `on_public_comment_added`, рефакторинг `transition`
- `backend/tickets/schemas.py` — два поля в `TicketRead`
- `backend/tickets/router.py` — интеграция в `add_comment` и macros-эндпоинт
- `backend/tickets/sla_watcher.py` — учёт активной паузы в дедлайне
- `backend/notifications/inbound.py` — интеграция в `_handle_reply` и `_handle_reply_by_subject`
- `backend/notifications/telegram.py` — интеграция в обработчик сообщений клиента

**Изменяются (frontend):**
- `frontend/src/types/index.ts` — два `optional` поля в `Ticket`
- `frontend/src/components/ticket/TicketSlaProgress.vue` — бейдж «SLA на паузе»

**Изменяются (тесты):**
- `tests/test_tickets_models.py` — тесты `recompute_sla_pause`, `on_public_comment_added`, рефактор transition
- `tests/test_inbound_email_integration.py` — проверка снятия reply-паузы при ответе клиента

**Изменяются (документация):**
- `agent_docs/guides/support-operations.md` — Варианты A/B/C
- `agent_docs/development-history.md` — запись 2026-04-17

---

## Task 1: Unit-тесты на `recompute_sla_pause` (red)

**Files:**
- Test: `tests/test_tickets_models.py`

- [ ] **Step 1: Добавить failing-тесты в конец файла**

```python
# ---------------------------------------------------------------------------
# SLA pause — OR-семантика двух источников
# ---------------------------------------------------------------------------

from datetime import datetime, timedelta


def test_recompute_sla_pause_reply_flag_starts_pause():
    ticket = _make_ticket()
    now = datetime(2026, 4, 17, 12, 0, 0)
    ticket.sla_paused_by_reply = True
    ticket.recompute_sla_pause(now)
    assert ticket.sla_paused_at == now
    assert ticket.sla_total_pause_seconds == 0


def test_recompute_sla_pause_status_flag_starts_pause():
    ticket = _make_ticket()
    now = datetime(2026, 4, 17, 12, 0, 0)
    ticket.sla_paused_by_status = True
    ticket.recompute_sla_pause(now)
    assert ticket.sla_paused_at == now


def test_recompute_sla_pause_both_false_ends_pause_and_accumulates():
    ticket = _make_ticket()
    start = datetime(2026, 4, 17, 12, 0, 0)
    end = start + timedelta(hours=1)
    ticket.sla_paused_by_reply = True
    ticket.recompute_sla_pause(start)

    ticket.sla_paused_by_reply = False
    ticket.recompute_sla_pause(end)

    assert ticket.sla_paused_at is None
    assert ticket.sla_total_pause_seconds == 3600


def test_recompute_sla_pause_one_flag_active_keeps_pause():
    """Если reply-флаг снят, но статус-флаг ещё активен — пауза продолжается."""
    ticket = _make_ticket()
    start = datetime(2026, 4, 17, 12, 0, 0)
    ticket.sla_paused_by_status = True
    ticket.sla_paused_by_reply = True
    ticket.recompute_sla_pause(start)

    # reply снят, status ещё активен
    ticket.sla_paused_by_reply = False
    ticket.recompute_sla_pause(start + timedelta(minutes=30))

    assert ticket.sla_paused_at == start  # не обнулили
    assert ticket.sla_total_pause_seconds == 0  # ничего не накопили


def test_recompute_sla_pause_noop_when_state_unchanged():
    ticket = _make_ticket()
    now = datetime(2026, 4, 17, 12, 0, 0)
    ticket.sla_paused_by_reply = True
    ticket.recompute_sla_pause(now)
    # повторный вызов без изменения флагов не должен ничего портить
    ticket.recompute_sla_pause(now + timedelta(hours=2))
    assert ticket.sla_paused_at == now
    assert ticket.sla_total_pause_seconds == 0
```

- [ ] **Step 2: Запустить тесты — должны упасть**

Run: `docker exec site-pass24-servicedesk python -m pytest tests/test_tickets_models.py::test_recompute_sla_pause_reply_flag_starts_pause -v`
Expected: FAIL — `AttributeError: 'Ticket' object has no attribute 'sla_paused_by_reply'` или `recompute_sla_pause`.

- [ ] **Step 3: Коммит failing-тестов**

```bash
git add tests/test_tickets_models.py
git commit -m "test: red — Ticket.recompute_sla_pause OR-semantics"
```

---

## Task 2: Добавить поля и `recompute_sla_pause` в модель (green)

**Files:**
- Modify: `backend/tickets/models.py`

- [ ] **Step 1: Добавить два поля в класс `Ticket`**

Найти блок (строки ~200-203):
```python
    sla_breached: bool = Field(default=False)
    # SLA pause: когда тикет в WAITING_FOR_USER — часы не тикают
    sla_paused_at: Optional[datetime] = Field(default=None)
    sla_total_pause_seconds: int = Field(default=0)
```

Заменить на:
```python
    sla_breached: bool = Field(default=False)
    # SLA pause: сводное состояние — устанавливается, когда активен хотя бы
    # один из флагов sla_paused_by_status / sla_paused_by_reply.
    sla_paused_at: Optional[datetime] = Field(default=None)
    sla_total_pause_seconds: int = Field(default=0)
    # Источники паузы. recompute_sla_pause() конвертирует OR-комбинацию
    # флагов в установку/снятие sla_paused_at.
    sla_paused_by_status: bool = Field(default=False)
    sla_paused_by_reply: bool = Field(default=False)
```

- [ ] **Step 2: Добавить метод `recompute_sla_pause` в класс `Ticket`**

Вставить перед методом `transition` (строка ~330):

```python
    def recompute_sla_pause(self, now: datetime) -> None:
        """Синхронизирует sla_paused_at/sla_total_pause_seconds с флагами источников.

        OR-семантика: пауза активна, если sla_paused_by_status или sla_paused_by_reply.
        Безопасно вызывается повторно (no-op, если состояние совпадает с флагами).
        """
        was_paused = self.sla_paused_at is not None
        should_pause = bool(self.sla_paused_by_status or self.sla_paused_by_reply)

        if should_pause and not was_paused:
            self.sla_paused_at = now
        elif not should_pause and was_paused:
            elapsed = int((now - self.sla_paused_at).total_seconds())
            self.sla_total_pause_seconds += max(0, elapsed)
            self.sla_paused_at = None
```

- [ ] **Step 3: Запустить тесты — должны пройти**

Run: `docker exec site-pass24-servicedesk python -m pytest tests/test_tickets_models.py -k recompute_sla_pause -v`
Expected: 5 passed.

- [ ] **Step 4: Коммит**

```bash
git add backend/tickets/models.py
git commit -m "feat: Ticket.recompute_sla_pause with OR-semantics over two source flags"
```

---

## Task 3: Рефакторинг `Ticket.transition` на новый механизм

**Files:**
- Modify: `backend/tickets/models.py`
- Test: `tests/test_tickets_models.py`

- [ ] **Step 1: Добавить failing-тест, что `transition` выставляет `sla_paused_by_status`**

```python
def test_transition_to_waiting_sets_paused_by_status_flag():
    ticket = _make_ticket()
    ticket.transition(actor_id="agent-1", new_status=TicketStatus.IN_PROGRESS)
    ticket.transition(actor_id="agent-1", new_status=TicketStatus.WAITING_FOR_USER)
    assert ticket.sla_paused_by_status is True
    assert ticket.sla_paused_at is not None


def test_transition_out_of_waiting_clears_paused_by_status_flag():
    ticket = _make_ticket()
    ticket.transition(actor_id="agent-1", new_status=TicketStatus.IN_PROGRESS)
    ticket.transition(actor_id="agent-1", new_status=TicketStatus.WAITING_FOR_USER)
    ticket.transition(actor_id="agent-1", new_status=TicketStatus.IN_PROGRESS)
    assert ticket.sla_paused_by_status is False
    assert ticket.sla_paused_at is None
    assert ticket.sla_total_pause_seconds >= 0


def test_transition_on_hold_also_pauses():
    ticket = _make_ticket()
    ticket.transition(actor_id="agent-1", new_status=TicketStatus.ON_HOLD)
    assert ticket.sla_paused_by_status is True
    assert ticket.sla_paused_at is not None
```

Run: `docker exec site-pass24-servicedesk python -m pytest tests/test_tickets_models.py::test_transition_to_waiting_sets_paused_by_status_flag -v`
Expected: FAIL — `sla_paused_by_status` остаётся `False`.

- [ ] **Step 2: Заменить старый блок SLA pause в `transition` на использование `recompute_sla_pause`**

Найти в `Ticket.transition` (строки ~359-366):

```python
        # SLA pause: при входе в WAITING_FOR_USER или ON_HOLD — ставим на паузу
        if new_status in (TicketStatus.WAITING_FOR_USER, TicketStatus.ON_HOLD) and self.sla_paused_at is None:
            self.sla_paused_at = now
        # При выходе из WAITING_FOR_USER или ON_HOLD — суммируем паузу и сбрасываем
        if prev_status in (TicketStatus.WAITING_FOR_USER, TicketStatus.ON_HOLD) and self.sla_paused_at is not None:
            pause_seconds = int((now - self.sla_paused_at).total_seconds())
            self.sla_total_pause_seconds += pause_seconds
            self.sla_paused_at = None
```

Заменить на:
```python
        # Источник паузы «статус»: обновляем флаг и пересчитываем сводное состояние.
        # Пауза также может быть активна по reply-флагу, поэтому централизованный
        # recompute_sla_pause решает, нужно ли сейчас держать sla_paused_at.
        self.sla_paused_by_status = new_status in (
            TicketStatus.WAITING_FOR_USER,
            TicketStatus.ON_HOLD,
        )
        self.recompute_sla_pause(now)
```

- [ ] **Step 3: Запустить все тесты модели — должны пройти**

Run: `docker exec site-pass24-servicedesk python -m pytest tests/test_tickets_models.py -v`
Expected: все тесты зелёные, включая новые на `sla_paused_by_status`.

- [ ] **Step 4: Коммит**

```bash
git add backend/tickets/models.py tests/test_tickets_models.py
git commit -m "refactor: Ticket.transition delegates SLA pause to recompute_sla_pause"
```

---

## Task 4: Метод `on_public_comment_added` (TDD)

**Files:**
- Modify: `backend/tickets/models.py`
- Test: `tests/test_tickets_models.py`

- [ ] **Step 1: Failing-тест**

```python
def test_on_public_comment_added_staff_starts_reply_pause():
    ticket = _make_ticket()
    now = datetime(2026, 4, 17, 12, 0, 0)
    ticket.on_public_comment_added(is_staff=True, now=now)
    assert ticket.sla_paused_by_reply is True
    assert ticket.sla_paused_at == now


def test_on_public_comment_added_client_ends_reply_pause_and_accumulates():
    ticket = _make_ticket()
    start = datetime(2026, 4, 17, 12, 0, 0)
    ticket.on_public_comment_added(is_staff=True, now=start)
    ticket.on_public_comment_added(is_staff=False, now=start + timedelta(hours=2))
    assert ticket.sla_paused_by_reply is False
    assert ticket.sla_paused_at is None
    assert ticket.sla_total_pause_seconds == 7200


def test_on_public_comment_added_then_status_waiting_keeps_pause():
    """Агент написал → reply-пауза. Затем перевёл в waiting → статус-пауза добавляется.
    Затем клиент ответил → reply снят, но статус держит паузу."""
    ticket = _make_ticket()
    t0 = datetime(2026, 4, 17, 12, 0, 0)
    ticket.on_public_comment_added(is_staff=True, now=t0)
    ticket.transition(actor_id="agent-1", new_status=TicketStatus.IN_PROGRESS)
    ticket.transition(actor_id="agent-1", new_status=TicketStatus.WAITING_FOR_USER)
    assert ticket.sla_paused_at is not None
    ticket.on_public_comment_added(is_staff=False, now=t0 + timedelta(hours=1))
    # reply=false, но status=true → пауза не снимается
    assert ticket.sla_paused_by_reply is False
    assert ticket.sla_paused_by_status is True
    assert ticket.sla_paused_at is not None
```

Run: `docker exec site-pass24-servicedesk python -m pytest tests/test_tickets_models.py::test_on_public_comment_added_staff_starts_reply_pause -v`
Expected: FAIL — `AttributeError: 'Ticket' object has no attribute 'on_public_comment_added'`.

- [ ] **Step 2: Добавить метод в `Ticket`**

Вставить сразу после `recompute_sla_pause`:

```python
    def on_public_comment_added(self, is_staff: bool, now: datetime) -> None:
        """Вызывается после создания публичного (не internal) комментария.

        Message-driven SLA pause: если комментарий от сотрудника поддержки —
        ставим флаг reply-паузы; если от клиента — снимаем. Сводное состояние
        пересчитывается через recompute_sla_pause (OR с флагом статуса).

        Internal-комментарии этот метод вызывать не должны.
        """
        self.sla_paused_by_reply = bool(is_staff)
        self.recompute_sla_pause(now)
```

- [ ] **Step 3: Запустить новые тесты — green**

Run: `docker exec site-pass24-servicedesk python -m pytest tests/test_tickets_models.py -k on_public_comment -v`
Expected: 3 passed.

- [ ] **Step 4: Коммит**

```bash
git add backend/tickets/models.py tests/test_tickets_models.py
git commit -m "feat: Ticket.on_public_comment_added — message-driven SLA pause"
```

---

## Task 5: Миграция 021 — две колонки + backfill

**Files:**
- Create: `migrations/versions/021_add_sla_pause_flags.py`

- [ ] **Step 1: Создать файл миграции**

```python
"""Add sla_paused_by_status / sla_paused_by_reply flags.

Revision ID: 021
Revises: 020
Create Date: 2026-04-17
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "021"
down_revision: Union[str, None] = "020"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "tickets",
        sa.Column("sla_paused_by_status", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.add_column(
        "tickets",
        sa.Column("sla_paused_by_reply", sa.Boolean(), nullable=False, server_default="false"),
    )
    # Backfill: статус-флаг derive-им из текущего статуса. Reply-флаг оставляем
    # false — не ретроактивно применяем новую паузу к исторической переписке.
    op.execute(
        "UPDATE tickets "
        "SET sla_paused_by_status = TRUE "
        "WHERE status IN ('waiting_for_user', 'on_hold')"
    )


def downgrade() -> None:
    op.drop_column("tickets", "sla_paused_by_reply")
    op.drop_column("tickets", "sla_paused_by_status")
```

- [ ] **Step 2: Применить миграцию**

Run: `docker exec site-pass24-servicedesk alembic upgrade head`
Expected: `INFO [alembic.runtime.migration] Running upgrade 020 -> 021, Add sla_paused_by_status / sla_paused_by_reply flags.`

- [ ] **Step 3: Проверить схему**

Run: `docker exec site-pass24-servicedesk-db psql -U pass24 -d pass24 -c "\d tickets" | grep sla_paused`
Expected: три строки — `sla_paused_at`, `sla_paused_by_reply`, `sla_paused_by_status`.

- [ ] **Step 4: Коммит**

```bash
git add migrations/versions/021_add_sla_pause_flags.py
git commit -m "migration: 021 add sla_paused_by_status / sla_paused_by_reply flags"
```

---

## Task 6: Обновить схему API и тип фронтенда

**Files:**
- Modify: `backend/tickets/schemas.py`
- Modify: `frontend/src/types/index.ts`

- [ ] **Step 1: Найти `TicketRead` и добавить два поля рядом с `sla_*`**

Открыть `backend/tickets/schemas.py`, найти в `TicketRead` блок SLA полей (рядом с `sla_breached`, `sla_paused_at`). Добавить:

```python
    sla_paused_by_status: bool = False
    sla_paused_by_reply: bool = False
```

- [ ] **Step 2: Найти интерфейс `Ticket` во frontend и добавить поля**

Открыть `frontend/src/types/index.ts`, найти интерфейс `Ticket` (рядом с `sla_paused_at`). Добавить опциональные поля:

```typescript
  sla_paused_by_status?: boolean
  sla_paused_by_reply?: boolean
```

- [ ] **Step 3: Проверить, что TypeScript не ругается**

Run: `cd frontend && npm run typecheck` (если есть скрипт) либо `npx vue-tsc --noEmit`
Expected: без ошибок типов.

- [ ] **Step 4: Коммит**

```bash
git add backend/tickets/schemas.py frontend/src/types/index.ts
git commit -m "feat: expose sla_paused_by_status / sla_paused_by_reply in API + FE type"
```

---

## Task 7: Интеграция в web-эндпоинт `add_comment`

**Files:**
- Modify: `backend/tickets/router.py`

- [ ] **Step 1: Импортировать `datetime` и `UserRole`**

В `backend/tickets/router.py` убедиться, что импорты доступны (обычно уже есть: `from datetime import datetime` и `from backend.auth.models import UserRole` — если нет, добавить).

- [ ] **Step 2: Добавить вызов `on_public_comment_added` в `add_comment`**

Найти блок (строки ~846-896):
```python
    # Внутренние комментарии — только для агентов и админов
    from backend.auth.models import UserRole
    is_staff = current_user.role in (UserRole.SUPPORT_AGENT, UserRole.ADMIN)
    is_internal = payload.is_internal and is_staff

    comment = TicketComment(
        ticket_id=ticket_id,
        author_id=str(current_user.id),
        author_name=current_user.full_name or "",
        text=payload.text,
        is_internal=is_internal,
    )
    session.add(comment)

    # Авто-переход статуса + флаг unread
    if not is_internal:
```

Вставить между `session.add(comment)` и `# Авто-переход статуса`:

```python
    # Message-driven SLA pause. Internal-комментарии не влияют — клиент их не видит.
    if not is_internal:
        ticket.on_public_comment_added(is_staff=is_staff, now=datetime.utcnow())
```

- [ ] **Step 3: Убедиться, что `session.add(ticket)` вызывается** (уже есть на строке ~896 — `session.add(ticket)` внутри `if not is_internal`).

- [ ] **Step 4: Ручная проверка через curl**

Создать новый тестовый тикет, получить его id. От имени агента добавить публичный комментарий:

```bash
TOKEN="<agent-jwt>"
TICKET_ID="<id>"
curl -s -X POST "https://support.pass24pro.ru/api/tickets/$TICKET_ID/comments" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"text": "Проверьте, работает ли доступ теперь", "is_internal": false}'
```

Затем проверить БД:
```bash
docker exec site-pass24-servicedesk-db psql -U pass24 -d pass24 \
  -c "SELECT id, status, sla_paused_by_reply, sla_paused_by_status, sla_paused_at FROM tickets WHERE id = '$TICKET_ID'"
```
Expected: `sla_paused_by_reply = true`, `sla_paused_at` не `NULL`.

- [ ] **Step 5: Коммит**

```bash
git add backend/tickets/router.py
git commit -m "feat: add_comment triggers message-driven SLA pause recompute"
```

---

## Task 8: Интеграция в web-макрос эндпоинт

**Files:**
- Modify: `backend/tickets/router.py`

- [ ] **Step 1: Найти macros-эндпоинт**

Блок в `backend/tickets/router.py` около строки 1578:
```python
    if actions.get("comment"):
        comment = TicketComment(
            ticket_id=ticket.id,
            author_id=str(current_user.id),
            author_name=current_user.full_name or "",
            text=actions["comment"],
            is_internal=bool(actions.get("is_internal_comment")),
        )
        session.add(comment)
```

- [ ] **Step 2: Добавить вызов сразу после `session.add(comment)`**

```python
        # Message-driven SLA pause (internal-комментарий не влияет).
        if not comment.is_internal:
            from backend.auth.models import UserRole
            is_staff = current_user.role in (UserRole.SUPPORT_AGENT, UserRole.ADMIN)
            ticket.on_public_comment_added(is_staff=is_staff, now=datetime.utcnow())
```

Если `datetime` и `UserRole` уже импортированы вверху файла, inline-импорт `UserRole` можно опустить.

- [ ] **Step 3: Коммит**

```bash
git add backend/tickets/router.py
git commit -m "feat: macros endpoint triggers message-driven SLA pause"
```

---

## Task 9: Интеграция в inbound email

**Files:**
- Modify: `backend/notifications/inbound.py`
- Test: `tests/test_inbound_email_integration.py`

- [ ] **Step 1: Добавить failing-тест «клиент ответил → reply-пауза снята»**

В `tests/test_inbound_email_integration.py` в классе `TestReplyByTag` (после `test_reply_with_attachment`):

```python
    async def test_reply_clears_sla_reply_pause(self):
        """Клиент ответил по email → sla_paused_by_reply = false, пауза накопилась."""
        from datetime import datetime, timedelta
        from backend.notifications.inbound import _handle_reply
        from backend.database import async_session_factory
        from backend.tickets.models import Ticket

        user = await _get_or_create_user("test-inbound@example.com", "Тест Ответ")
        ticket = await _create_ticket(str(user.id), "Проверка снятия reply-паузы")

        # Искусственно ставим reply-паузу на 1 час назад
        async with async_session_factory() as s:
            t = await s.get(Ticket, ticket.id)
            t.sla_paused_by_reply = True
            t.sla_paused_at = datetime.utcnow() - timedelta(hours=1)
            s.add(t)
            await s.commit()

        try:
            mail_data = {
                "subject": f"Re: [PASS24-{ticket.id[:8]}] Тест",
                "from_email": "test-inbound@example.com",
                "from_name": "Тест Ответ",
                "body": "Отвечаю",
                "attachments": [],
            }
            await _handle_reply(mail_data, ticket.id[:8])

            updated = await _get_ticket(ticket.id)
            assert updated.sla_paused_by_reply is False, "reply-флаг должен сняться"
            assert updated.sla_paused_at is None, "сводная пауза должна сняться"
            assert updated.sla_total_pause_seconds >= 3500, (
                f"пауза должна накопиться (~3600), получено {updated.sla_total_pause_seconds}"
            )
        finally:
            await _cleanup_ticket(ticket.id)
```

Run: `docker exec site-pass24-servicedesk python -m pytest tests/test_inbound_email_integration.py::TestReplyByTag::test_reply_clears_sla_reply_pause -v`
Expected: FAIL — `sla_paused_by_reply` остаётся `True`.

- [ ] **Step 2: Внедрить вызов в `_handle_reply`**

В `backend/notifications/inbound.py` найти блок (уже исправленный под фикс прошлого коммита):
```python
        body = mail_data["body"]
        attachments = mail_data.get("attachments", [])
        comment_id: Optional[str] = None
        if body.strip() or attachments:
            comment = TicketComment(
                ticket_id=ticket.id,
                author_id=author_id,
                author_name=author_name,
                text=body,
            )
            session.add(comment)
            comment_id = comment.id
```

Сразу после `comment_id = comment.id` добавить:
```python
            # Message-driven SLA pause: ответ клиента снимает reply-паузу.
            ticket.on_public_comment_added(is_staff=False, now=datetime.utcnow())
```

Убедиться, что `from datetime import datetime` импортирован в начале файла (он уже там, строка 6-я области импортов).

- [ ] **Step 3: Аналогично для `_handle_reply_by_subject`**

Найти симметричный блок в `_handle_reply_by_subject`:
```python
        if body.strip() or attachments:
            comment = TicketComment(
                ticket_id=ticket.id,
                author_id=str(user.id),
                author_name=author_name,
                text=body,
            )
            session.add(comment)
            comment_id = comment.id
```

Добавить аналогичную строку:
```python
            ticket.on_public_comment_added(is_staff=False, now=datetime.utcnow())
```

- [ ] **Step 4: Запустить интеграционный тест — green**

Run: `docker exec site-pass24-servicedesk python -m pytest tests/test_inbound_email_integration.py::TestReplyByTag::test_reply_clears_sla_reply_pause -v`
Expected: PASS.

- [ ] **Step 5: Коммит**

```bash
git add backend/notifications/inbound.py tests/test_inbound_email_integration.py
git commit -m "feat: inbound email reply clears SLA reply pause"
```

---

## Task 10: Интеграция в Telegram

**Files:**
- Modify: `backend/notifications/telegram.py`

- [ ] **Step 1: Найти обработчик комментария клиента (строки ~270-295)**

Блок:
```python
        if active_ticket:
            # Добавляем как комментарий
            if text:
                comment = TicketComment(
                    ticket_id=active_ticket.id,
                    author_id=str(user.id),
                    author_name=tg_name,
                    text=text,
                )
                session.add(comment)
```

- [ ] **Step 2: Добавить вызов сразу после `session.add(comment)`**

```python
                # Message-driven SLA pause: клиент ответил → reply-флаг снимается.
                active_ticket.on_public_comment_added(is_staff=False, now=datetime.utcnow())
```

Убедиться, что `datetime` импортирован в файле (проверить `from datetime import datetime` в начале). Если нет — добавить.

- [ ] **Step 3: Коммит**

```bash
git add backend/notifications/telegram.py
git commit -m "feat: telegram client reply clears SLA reply pause"
```

---

## Task 11: Fix `sla_watcher` — учёт активной паузы в дедлайне

**Files:**
- Modify: `backend/tickets/sla_watcher.py`
- Create: `tests/test_sla_watcher.py`

- [ ] **Step 1: Failing-тест**

Создать `tests/test_sla_watcher.py`:

```python
"""Юнит-тесты логики расчёта дедлайна в SLA watcher."""
from __future__ import annotations

from datetime import datetime, timedelta

from backend.tickets.models import Ticket, TicketStatus


def _ticket_with_paused_sla(resolve_hours: int, created_at: datetime, paused_at: datetime | None) -> Ticket:
    t = Ticket(
        creator_id="u",
        title="t",
        description="",
        status=TicketStatus.IN_PROGRESS,
        sla_resolve_hours=resolve_hours,
        created_at=created_at,
    )
    t.sla_paused_at = paused_at
    t.sla_paused_by_reply = paused_at is not None
    return t


def test_active_pause_extends_effective_deadline():
    """Если сейчас активна пауза длительностью 2 часа, дедлайн сдвинут на 2 часа вперёд."""
    from backend.tickets.sla_watcher import deadline_with_business_hours

    # created 5 часов назад, sla = 4 часа, paused 2 часа назад
    now = datetime(2026, 4, 17, 16, 0, 0)  # вт, рабочее время
    created = now - timedelta(hours=5)
    paused = now - timedelta(hours=2)
    t = _ticket_with_paused_sla(resolve_hours=4, created_at=created, paused_at=paused)

    base_deadline = deadline_with_business_hours(t.created_at, t.sla_resolve_hours)
    pause_sec = t.sla_total_pause_seconds or 0
    if t.sla_paused_at is not None:
        pause_sec += int((now - t.sla_paused_at).total_seconds())
    deadline = base_deadline + timedelta(seconds=pause_sec)

    # Без учёта активной паузы тикет был бы "просрочен" (4 часа прошло + базовая пауза 0).
    # С учётом активной паузы (2ч) effective deadline должен быть в будущем.
    assert deadline > now, f"Активная пауза должна двигать дедлайн за now, deadline={deadline}"
```

Запускаем:
```bash
docker exec site-pass24-servicedesk python -m pytest tests/test_sla_watcher.py -v
```
Expected: PASS (это пока формула без багов — тест валидирует сам расчёт, который мы заложим в watcher).

- [ ] **Step 2: Failing-интеграционный тест для `_check_sla_breaches`**

Дополнить файл `tests/test_sla_watcher.py`:

```python
import pytest

pytestmark = pytest.mark.asyncio


async def test_check_sla_breaches_ignores_active_pause():
    """Тикет в in_progress с активной reply-паузой не должен получать breach warning,
    если с учётом паузы дедлайн далеко в будущем."""
    from backend.database import async_session_factory
    from backend.tickets.sla_watcher import _check_sla_breaches
    from backend.tickets.models import Ticket, TicketStatus

    async with async_session_factory() as s:
        # SLA 1 час, создан 1ч 29 мин назад, reply-пауза активна 1 час.
        # Без учёта активной паузы: до breach 31 мин (< 30 мин warn не сработает, но близко).
        # С учётом активной паузы (1ч): до breach 1ч 31мин — warning явно не должен.
        now = datetime.utcnow()
        ticket = Ticket(
            creator_id="u",
            title="Test watcher pause",
            description="",
            status=TicketStatus.IN_PROGRESS,
            sla_resolve_hours=1,
            created_at=now - timedelta(minutes=89),
        )
        ticket.sla_paused_by_reply = True
        ticket.sla_paused_at = now - timedelta(hours=1)
        s.add(ticket)
        await s.commit()
        ticket_id = ticket.id

    try:
        warned = await _check_sla_breaches()
        async with async_session_factory() as s:
            fresh = await s.get(Ticket, ticket_id)
            assert fresh.sla_breach_warned is False, (
                "Watcher не должен warn-ить тикет с активной паузой"
            )
    finally:
        async with async_session_factory() as s:
            t = await s.get(Ticket, ticket_id)
            if t:
                await s.delete(t)
                await s.commit()
```

Запускаем:
```bash
docker exec site-pass24-servicedesk python -m pytest tests/test_sla_watcher.py::test_check_sla_breaches_ignores_active_pause -v
```
Expected: FAIL — watcher пометит тикет warned (не учитывает активную паузу).

- [ ] **Step 3: Внести фикс в `_check_sla_breaches`**

Открыть `backend/tickets/sla_watcher.py`, найти блок (строки ~93-100):

```python
        for t in tickets:
            if not t.sla_resolve_hours:
                continue
            pause_sec = t.sla_total_pause_seconds or 0
            # Дедлайн с учётом рабочих часов + пауз в WAITING_FOR_USER
            deadline = deadline_with_business_hours(t.created_at, t.sla_resolve_hours)
            deadline = deadline + timedelta(seconds=pause_sec)
            time_to_breach = deadline - now
```

Заменить на:
```python
        for t in tickets:
            if not t.sla_resolve_hours:
                continue
            pause_sec = t.sla_total_pause_seconds or 0
            # Учёт активной паузы (любой источник: статус или reply): без этого
            # при paused_at != None дедлайн не растёт и warning срабатывает ложно.
            if t.sla_paused_at is not None:
                pause_sec += int((now - t.sla_paused_at).total_seconds())
            deadline = deadline_with_business_hours(t.created_at, t.sla_resolve_hours)
            deadline = deadline + timedelta(seconds=pause_sec)
            time_to_breach = deadline - now
```

- [ ] **Step 4: Зелёный тест**

Run: `docker exec site-pass24-servicedesk python -m pytest tests/test_sla_watcher.py -v`
Expected: PASS.

- [ ] **Step 5: Коммит**

```bash
git add backend/tickets/sla_watcher.py tests/test_sla_watcher.py
git commit -m "fix: sla_watcher includes active pause duration in deadline calculation"
```

---

## Task 12: UI — бейдж «SLA на паузе» в `TicketSlaProgress.vue`

**Files:**
- Modify: `frontend/src/components/ticket/TicketSlaProgress.vue`

- [ ] **Step 1: Добавить computed-свойство `pauseInfo` в `<script setup>`**

Вставить после объявления `resolveProgress` (строка ~63):

```typescript
type PauseSource = 'reply' | 'status'

interface PauseInfo {
  source: PauseSource
  label: string
}

const pauseInfo = computed<PauseInfo | null>(() => {
  const t = props.ticket
  // Статус-пауза имеет приоритет в тексте (точнее описывает причину).
  if (t.sla_paused_by_status) {
    const statusLabel = t.status === 'on_hold' ? 'Отложена' : 'Ожидает ответа'
    return { source: 'status', label: `⏸ SLA на паузе — статус «${statusLabel}»` }
  }
  if (t.sla_paused_by_reply) {
    return { source: 'reply', label: '⏸ SLA на паузе — ждём ответ клиента' }
  }
  return null
})
```

- [ ] **Step 2: Отрисовать бейдж в шаблоне**

Найти блок «Решение» в `<template>` (строки ~82-95):

```vue
    <div v-if="resolveProgress" class="sla-item">
      <div class="sla-header">
        <span class="sla-label">Решение</span>
        <span class="sla-remaining" :style="{ color: resolveProgress.completed ? '#10b981' : resolveProgress.color }">
          {{ resolveProgress.remaining }}
        </span>
      </div>
      <ProgressBar
        :value="resolveProgress.pct"
        :showValue="false"
        :style="{ height: '6px' }"
        :pt="{ value: { style: { backgroundColor: resolveProgress.color } } }"
      />
    </div>
```

Заменить на:
```vue
    <div v-if="resolveProgress" class="sla-item">
      <div class="sla-header">
        <span class="sla-label">Решение</span>
        <span class="sla-remaining" :style="{ color: pauseInfo ? '#94a3b8' : (resolveProgress.completed ? '#10b981' : resolveProgress.color) }">
          {{ pauseInfo ? 'На паузе' : resolveProgress.remaining }}
        </span>
      </div>
      <ProgressBar
        :value="resolveProgress.pct"
        :showValue="false"
        :style="{ height: '6px' }"
        :pt="{ value: { style: { backgroundColor: pauseInfo ? '#94a3b8' : resolveProgress.color } } }"
      />
      <div v-if="pauseInfo" class="sla-pause-badge">{{ pauseInfo.label }}</div>
    </div>
```

- [ ] **Step 3: Добавить CSS для бейджа**

В блок `<style scoped>`, после `.sla-empty`:

```css
.sla-pause-badge {
  margin-top: 4px;
  font-size: 0.75rem;
  color: #64748b;
  background: #f1f5f9;
  padding: 4px 8px;
  border-radius: 4px;
  font-weight: 500;
}
```

- [ ] **Step 4: Сборка фронтенда**

Run: `cd frontend && npm run build`
Expected: успешно без ошибок типов.

- [ ] **Step 5: Визуальная проверка**

- Открыть dev-сервер (`cd frontend && npm run dev`).
- В БД временно выставить `sla_paused_by_reply = true, sla_paused_at = NOW()` на тестовом тикете.
- Обновить страницу тикета — убедиться, что под прогресс-баром «Решение» виден серый бейдж «⏸ SLA на паузе — ждём ответ клиента», а прогресс-бар серый.
- Выставить `sla_paused_by_reply = false, sla_paused_at = NULL` — бейдж исчезает, цвет возвращается.

- [ ] **Step 6: Коммит**

```bash
git add frontend/src/components/ticket/TicketSlaProgress.vue
git commit -m "feat(ui): SLA pause badge on ticket progress indicator"
```

---

## Task 13: Обновить регламент `support-operations.md`

**Files:**
- Modify: `agent_docs/guides/support-operations.md`

- [ ] **Step 1: Изменить Вариант B (строки ~200-203)**

Найти:
```markdown
Вариант B — **Нужна дополнительная информация от клиента:**
1. Напишите клиенту в чате вопросы (адрес объекта, номер пропуска, скриншот и т.д.)
2. В правой панели нажмите на статус и выберите **«Ожидать ответа»** → статус станет «Ожидает ответа»
3. Клиент получит email с вашим вопросом
```

Заменить на:
```markdown
Вариант B — **Нужна дополнительная информация от клиента:**
1. Напишите клиенту в чате вопросы (адрес объекта, номер пропуска, скриншот и т.д.)
2. Клиент получит email с вашим вопросом
3. SLA «Решение» автоматически встанет на паузу, пока клиент не ответит
4. Статус **«Ожидает ответа»** можно выставить вручную — как явный маркер для коллег, но он больше не обязателен для паузы SLA
```

- [ ] **Step 2: Дополнить Вариант C (строки ~205-209)**

Найти:
```markdown
Вариант C — **Нужен выезд инженера:**
1. Напишите клиенту, что для решения проблемы требуется выезд на объект
2. В правой панели нажмите на статус и выберите **«Выезд инженера»**
3. Заявка появится во вкладке **«Выезды»** в списке заявок
4. Таймер срока реакции продолжает идти — обновляйте клиента о ходе работ
```

Заменить строку 4 на:
```markdown
4. Пока ваше сообщение было последним в переписке — SLA «Решение» автоматически на паузе. Как только клиент ответит — таймер продолжит тикать.
```

- [ ] **Step 3: Коммит**

```bash
git add agent_docs/guides/support-operations.md
git commit -m "docs: support-operations reflects message-driven SLA pause"
```

---

## Task 14: Запись в `development-history.md`

**Files:**
- Modify: `agent_docs/development-history.md`

- [ ] **Step 1: Добавить запись в начало раздела «## Записи»**

Найти строку `## Записи` и сразу после неё вставить:

```markdown
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
```

- [ ] **Step 2: Коммит**

```bash
git add agent_docs/development-history.md
git commit -m "docs: development-history entry for message-driven SLA pause"
```

---

## Task 15: Финальная верификация и push

- [ ] **Step 1: Применить миграцию на staging/prod docker**

Run: `docker exec site-pass24-servicedesk alembic upgrade head`
Expected: миграция 021 применена, без ошибок.

- [ ] **Step 2: Прогнать весь тест-сьют**

Run: `docker exec site-pass24-servicedesk python -m pytest tests/ -v`
Expected: все тесты зелёные. Убедиться, что добавленные:
- `test_recompute_sla_pause_*` (5 тестов)
- `test_transition_*paused_by_status*` (3 теста)
- `test_on_public_comment_added_*` (3 теста)
- `test_reply_clears_sla_reply_pause` (1 тест)
- `test_sla_watcher.py` (2 теста)

- [ ] **Step 3: End-to-end smoke через UI**

Сценарий:
1. Создать тикет от имени клиента (email-источник или веб).
2. Агент добавляет публичный комментарий → UI показывает бейдж «⏸ SLA на паузе — ждём ответ клиента», прогресс серый.
3. В БД: `sla_paused_by_reply = true`, `sla_paused_at != NULL`.
4. Клиент отвечает (email или UI) → бейдж исчезает, прогресс снова цветной и продолжает ползти с учётом накопленной паузы.
5. В БД: `sla_paused_by_reply = false`, `sla_paused_at = NULL`, `sla_total_pause_seconds` увеличился.

- [ ] **Step 4: Push в main**

```bash
git push origin main
```

- [ ] **Step 5: Убедиться, что prod-контейнер подхватил миграцию**

Run: `ssh pass24-prod "docker exec site-pass24-servicedesk alembic current"`
Expected: `021 (head)`.

---

## Self-review чеклист для исполнителя

Перед `Step 4: Push`:

- [ ] **Spec coverage:** каждая секция `docs/superpowers/specs/2026-04-17-message-driven-sla-pause-design.md` покрыта задачей.
- [ ] **TDD:** каждый код-изменение имеет предшествующий failing-тест.
- [ ] **Idempotency:** `recompute_sla_pause` вызывается >1 раза в одной сессии (например, при обновлении и флагов статуса, и reply-флагов одновременно) и даёт корректный результат.
- [ ] **No duplicate pause accumulation:** в старом коде `transition` сам накапливал паузу — убедиться, что после рефактора накопление идёт только через `recompute_sla_pause`.
- [ ] **Гонка статусов:** если агент одним макросом добавил комментарий И сменил статус — результирующее состояние флагов корректно (reply=true от comment, status=true от transition → пауза активна).
- [ ] **Internal comments skip:** интеграционные точки НЕ вызывают `on_public_comment_added` для `is_internal = true`.

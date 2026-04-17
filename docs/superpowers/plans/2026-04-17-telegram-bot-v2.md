# Telegram Bot v2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the minimal 390-line Telegram webhook with a full-featured, menu-driven bot covering tickets, KB, AI, projects, and approvals for residents and property managers.

**Architecture:** aiogram 3 integrated into existing FastAPI via `Dispatcher.feed_update()` in a single webhook endpoint. PostgreSQL-backed FSM storage for wizard state. Deep link account binding with ghost-user migration. All business logic delegated to existing service modules.

**Tech Stack:** aiogram 3, FastAPI, SQLModel, PostgreSQL 16 (asyncpg), httpx, Vue 3 + PrimeVue (frontend link card)

**Spec:** `docs/superpowers/specs/2026-04-16-telegram-bot-v2-design.md`

---

## File Map

### New files (backend/telegram/)

| File | Responsibility |
|---|---|
| `backend/telegram/__init__.py` | Package marker |
| `backend/telegram/config.py` | Bot token, webhook secret, deep link base URL from settings |
| `backend/telegram/bot.py` | `Bot()` + `Dispatcher()` singletons, router registration |
| `backend/telegram/webhook.py` | FastAPI `APIRouter`: `POST /telegram/webhook/{secret}` → `dp.feed_update()` |
| `backend/telegram/storage.py` | `PostgresStorage(BaseStorage)` — aiogram FSM over `telegram_fsm_state` table |
| `backend/telegram/exceptions.py` | `TelegramAuthError`, `TelegramRateLimit` |
| `backend/telegram/formatters.py` | `format_ticket()`, `format_article()`, `format_project()` → HTML for TG |
| `backend/telegram/middlewares/auth.py` | Loads `User` by `chat_id` into handler `data["user"]` |
| `backend/telegram/middlewares/throttle.py` | 10 msg/min per chat_id rate limit |
| `backend/telegram/middlewares/logging.py` | Structured log for each update |
| `backend/telegram/keyboards/common.py` | `cancel_kb()`, `back_kb()`, `pagination_kb()` builders |
| `backend/telegram/keyboards/main_menu.py` | `main_menu_kb(user, counts)` with role-based buttons |
| `backend/telegram/keyboards/ticket_wizard.py` | Product, category, impact/urgency, confirm keyboards |
| `backend/telegram/keyboards/ticket_detail.py` | Ticket card action buttons |
| `backend/telegram/keyboards/kb.py` | Search results, article view, feedback buttons |
| `backend/telegram/keyboards/projects.py` | Project list, card, approval buttons |
| `backend/telegram/handlers/__init__.py` | `register_all_routers(dp)` |
| `backend/telegram/handlers/start.py` | `/start` with deep link + plain |
| `backend/telegram/handlers/menu.py` | Main menu display + free-text fallback |
| `backend/telegram/handlers/tickets_create.py` | `CreateTicketStates` FSM wizard |
| `backend/telegram/handlers/tickets_list.py` | My tickets, ticket card, pagination |
| `backend/telegram/handlers/tickets_reply.py` | Reply, attachments, close ticket |
| `backend/telegram/handlers/csat.py` | CSAT rating flow |
| `backend/telegram/handlers/kb.py` | KB search + article view |
| `backend/telegram/handlers/ai.py` | AI chat mode |
| `backend/telegram/handlers/projects.py` | My projects (PM only) |
| `backend/telegram/handlers/approvals.py` | Approve/reject phases (PM only) |
| `backend/telegram/handlers/settings.py` | Notification toggles, unlink |
| `backend/telegram/services/linking.py` | `generate_token()`, `verify_token()`, `link_account()`, `migrate_ghost()` |
| `backend/telegram/services/ticket_service.py` | `create_ticket()`, `list_my_tickets()`, `add_comment()`, `close_ticket()` |
| `backend/telegram/services/kb_service.py` | `search_articles()`, `get_article()`, `record_feedback()` |
| `backend/telegram/services/ai_service.py` | `ask(query, session_id)` wrapping `assistant/rag.py` |
| `backend/telegram/services/project_service.py` | `list_projects()`, `get_project()`, `pending_approvals()` |
| `backend/telegram/services/notify.py` | `notify_comment()`, `notify_status()`, `notify_sla()`, `notify_csat()`, `notify_approval()` — replaces old telegram.py |
| `backend/telegram/deflection.py` | `suggest_articles()` + deflection tracking |

### New files (other)

| File | Responsibility |
|---|---|
| `migrations/versions/019_telegram_bot_v2.py` | `telegram_fsm_state`, `telegram_link_tokens` tables + user columns |
| `frontend/src/components/TelegramLinkCard.vue` | QR code, polling, link/unlink UI |
| `tests/test_telegram_bot.py` | Unit tests for services, storage, keyboards |
| `tests/test_telegram_webhook.py` | Integration tests: real update payloads → webhook → DB |

### Modified files

| File | Change |
|---|---|
| `requirements.txt` | Add `aiogram>=3.15` |
| `backend/main.py` | Import new webhook router, create Bot/Dp in lifespan |
| `backend/config.py` | No change needed (token + secret already exist) |
| `backend/auth/models.py` | Add `telegram_linked_at`, `telegram_preferences` fields |
| `backend/auth/router.py` | Add `POST /auth/telegram/link-token`, `DELETE /auth/telegram/link` |
| `backend/tickets/router.py` | Change `notify_*` imports from `notifications.telegram` → `telegram.services.notify` |
| `backend/tickets/sla_watcher.py` | Add telegram notification branch |
| `backend/projects/router.py` | Extract approval logic to services |
| `backend/projects/services.py` | Add `approve_phase()`, `reject_phase()` |
| `backend/knowledge/router.py` | Extract FTS search logic to `knowledge/services.py` |
| `frontend/src/pages/SettingsPage.vue` | Add `<TelegramLinkCard>` section |
| `frontend/src/api/auth.ts` | Add `generateTelegramLinkToken()`, `unlinkTelegram()` |

### Deleted files

| File | Reason |
|---|---|
| `backend/notifications/telegram.py` | Replaced by `backend/telegram/` package |

---

## Task 1: Foundation — Dependencies + Migration + Storage

**Files:**
- Modify: `requirements.txt`
- Create: `migrations/versions/019_telegram_bot_v2.py`
- Modify: `backend/auth/models.py` (add 2 fields)
- Create: `backend/telegram/__init__.py`
- Create: `backend/telegram/config.py`
- Create: `backend/telegram/storage.py`
- Create: `backend/telegram/exceptions.py`
- Test: `tests/test_telegram_bot.py` (storage tests)

**What this task produces:** aiogram installed, DB tables created, PostgresStorage working.

- [ ] **Step 1:** Add `aiogram>=3.15` to `requirements.txt`. Run `pip install aiogram>=3.15` to verify it installs.

- [ ] **Step 2:** Add fields to `backend/auth/models.py` on the `User` model:
```python
telegram_linked_at: Optional[datetime] = Field(default=None)
telegram_preferences: dict = Field(default={}, sa_column=Column(JSON, server_default="{}"))
```
Note: import `JSON` from `sqlalchemy` and `Column` from `sqlmodel`.

- [ ] **Step 3:** Create migration `migrations/versions/019_telegram_bot_v2.py`:
- Table `telegram_fsm_state`: columns `key VARCHAR PK`, `state VARCHAR NULL`, `data JSONB DEFAULT '{}'`, `updated_at TIMESTAMPTZ DEFAULT now()`
- Table `telegram_link_tokens`: columns `token VARCHAR(64) PK`, `user_id UUID FK users.id NOT NULL`, `expires_at TIMESTAMPTZ NOT NULL`, `used_at TIMESTAMPTZ NULL`
- Index on `telegram_fsm_state(updated_at)` for TTL cleanup
- Index on `telegram_link_tokens(user_id)` for lookup
- Add column `telegram_linked_at TIMESTAMPTZ NULL` to `users`
- Add column `telegram_preferences JSONB DEFAULT '{}'` to `users`
- Downgrade: drop tables + columns

Follow the pattern of existing migrations (e.g., `016_project_approvals.py`). Use `op.create_table()`, `op.add_column()`.

- [ ] **Step 4:** Create `backend/telegram/__init__.py` (empty), `backend/telegram/config.py`:
```python
from backend.config import settings

BOT_TOKEN = settings.telegram_bot_token
WEBHOOK_SECRET = settings.telegram_webhook_secret
APP_BASE_URL = settings.app_base_url
DEEP_LINK_BASE = f"https://t.me/PASS24bot?start="
LINK_TOKEN_TTL_MINUTES = 10
LINK_TOKEN_MAX_PER_HOUR = 5
```

- [ ] **Step 5:** Create `backend/telegram/exceptions.py`:
```python
class TelegramAuthError(Exception):
    """User not linked or token invalid."""

class TelegramRateLimit(Exception):
    """Too many requests from this chat_id."""
```

- [ ] **Step 6:** Create `backend/telegram/storage.py` — `PostgresStorage` class implementing aiogram `BaseStorage` interface:
- `set_state(key, state)` → `INSERT ... ON CONFLICT (key) DO UPDATE SET state = :state, updated_at = now()`
- `get_state(key)` → `SELECT state FROM telegram_fsm_state WHERE key = :key`
- `set_data(key, data)` → `INSERT ... ON CONFLICT (key) DO UPDATE SET data = :data, updated_at = now()`
- `get_data(key)` → `SELECT data FROM telegram_fsm_state WHERE key = :key` (return `{}` if not found)
- `close()` → no-op (session managed per-call)
- Use `async_session_factory` from `backend.database` for each operation. Each method opens and closes its own session.
- Key format: `StorageKey` from aiogram has `bot_id`, `chat_id`, `user_id` → serialize as `"{bot_id}:{chat_id}:{user_id}"`.

- [ ] **Step 7:** Write tests in `tests/test_telegram_bot.py`:
```python
class TestPostgresStorage:
    async def test_set_get_state(self): ...
    async def test_set_get_data(self): ...
    async def test_get_state_not_found_returns_none(self): ...
    async def test_get_data_not_found_returns_empty_dict(self): ...
    async def test_update_overwrites(self): ...
```
These are integration tests requiring a live PG database. Use the same `async_session_factory` pattern as `test_full_suite.py`. Run: `pytest tests/test_telegram_bot.py::TestPostgresStorage -v`

- [ ] **Step 8:** Commit: `feat: telegram bot v2 foundation — aiogram dep, migration 019, PG storage`

---

## Task 2: Bot + Dispatcher + Webhook Router

**Files:**
- Create: `backend/telegram/bot.py`
- Create: `backend/telegram/webhook.py`
- Create: `backend/telegram/handlers/__init__.py`
- Modify: `backend/main.py`

**What this task produces:** Webhook receives Telegram updates and routes them through aiogram Dispatcher. No handlers yet (they're added in subsequent tasks).

- [ ] **Step 1:** Create `backend/telegram/bot.py`:
```python
from aiogram import Bot, Dispatcher
from backend.telegram.config import BOT_TOKEN
from backend.telegram.storage import PostgresStorage

bot: Bot | None = None
dp: Dispatcher | None = None

def create_bot_and_dispatcher() -> tuple[Bot, Dispatcher]:
    global bot, dp
    if not BOT_TOKEN:
        return None, None
    bot = Bot(token=BOT_TOKEN)
    storage = PostgresStorage()
    dp = Dispatcher(storage=storage)
    # Handlers will be registered via register_all_routers(dp) in handlers/__init__.py
    from backend.telegram.handlers import register_all_routers
    register_all_routers(dp)
    return bot, dp
```

- [ ] **Step 2:** Create `backend/telegram/handlers/__init__.py`:
```python
from aiogram import Dispatcher

def register_all_routers(dp: Dispatcher) -> None:
    # Each handler module will be imported and included here as tasks are completed.
    # For now, empty — webhook works but does nothing.
    pass
```

- [ ] **Step 3:** Create `backend/telegram/webhook.py`:
```python
from aiogram.types import Update
from fastapi import APIRouter, HTTPException, Request
from backend.telegram.config import WEBHOOK_SECRET
from backend.telegram.bot import bot, dp

router = APIRouter(prefix="/telegram", tags=["telegram"])

@router.post("/webhook/{secret}")
async def telegram_webhook(secret: str, request: Request):
    if not WEBHOOK_SECRET or secret != WEBHOOK_SECRET:
        raise HTTPException(status_code=403, detail="Forbidden")
    if not bot or not dp:
        raise HTTPException(status_code=503, detail="Bot not configured")
    update = Update.model_validate(await request.json())
    await dp.feed_update(bot, update)
    return {"ok": True}
```

- [ ] **Step 4:** Modify `backend/main.py`:
- In lifespan, add `create_bot_and_dispatcher()` call before yield
- Replace import: `from .notifications.telegram import router as telegram_router` → `from .telegram.webhook import router as telegram_router`
- Keep `app.include_router(telegram_router)` as-is (same variable name, no other change)

IMPORTANT: Do NOT delete `backend/notifications/telegram.py` yet — `tickets/router.py` still imports `notify_telegram_comment` and `notify_telegram_status` from it. That migration happens in Task 13.

- [ ] **Step 5:** Test manually: send a POST to webhook endpoint with a minimal TG update JSON. Verify 200 response (update gets processed, no handlers match = silent OK). Run: `pytest tests/test_full_suite.py -v -k "health"` to verify app still starts.

- [ ] **Step 6:** Commit: `feat: aiogram bot/dispatcher + webhook router integration`

---

## Task 3: Auth Middleware + Common Keyboards + Formatters

**Files:**
- Create: `backend/telegram/middlewares/__init__.py` (empty)
- Create: `backend/telegram/middlewares/auth.py`
- Create: `backend/telegram/middlewares/throttle.py`
- Create: `backend/telegram/middlewares/logging.py`
- Create: `backend/telegram/keyboards/__init__.py` (empty)
- Create: `backend/telegram/keyboards/common.py`
- Create: `backend/telegram/keyboards/main_menu.py`
- Create: `backend/telegram/formatters.py`
- Modify: `backend/telegram/bot.py` (register middlewares)

**What this task produces:** Every incoming update gets user lookup, rate limiting, and logging. Keyboard builders and HTML formatters ready for handlers.

- [ ] **Step 1:** Create `backend/telegram/middlewares/auth.py`:
- Implement aiogram outer middleware (subclass `BaseMiddleware`)
- On each update: extract `chat_id` from message or callback_query
- Query `SELECT * FROM users WHERE telegram_chat_id = :chat_id`
- If found: `data["user"] = user`, `data["is_linked"] = user.telegram_linked_at is not None`
- If not found: `data["user"] = None`, `data["is_linked"] = False`
- Always call `await handler(event, data)` — do NOT block unlinked users (ghost flow needs to work)

- [ ] **Step 2:** Create `backend/telegram/middlewares/throttle.py`:
- Simple in-memory dict: `{chat_id: [timestamp, ...]}` with 60s window, max 10 messages
- If exceeded: respond with "Слишком много сообщений, подождите минуту" and skip handler
- Use `defaultdict(list)` + prune old entries on each call

- [ ] **Step 3:** Create `backend/telegram/middlewares/logging.py`:
- Log: `chat_id`, `user_id` (if linked), handler name, callback_data (if callback), latency_ms
- Use `time.perf_counter()` around `await handler(event, data)`

- [ ] **Step 4:** Create `backend/telegram/keyboards/common.py`:
```python
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

def cancel_kb() -> InlineKeyboardMarkup: ...          # [✕ Отмена] cb=mm:main
def back_cancel_kb(back_cb: str) -> InlineKeyboardMarkup: ...  # [⬅ Назад][✕ Отмена]
def pagination_kb(prefix: str, page: int, total_pages: int, filter_val: str = "") -> InlineKeyboardMarkup: ...
    # [◀ Пред] Стр N/M [След ▶]  cb=prefix:page:N:filter
```

- [ ] **Step 5:** Create `backend/telegram/keyboards/main_menu.py`:
```python
def main_menu_kb(user, *, active_tickets: int = 0, pending_approvals: int = 0) -> InlineKeyboardMarkup:
    # Builds buttons based on user.role:
    # Always: [📝 Новая заявка] [📋 Мои заявки •N] [📚 База знаний] [🤖 Спросить AI] [⚙ Настройки]
    # PM only: [🏗 Мои проекты •N⏳]
```

- [ ] **Step 6:** Create `backend/telegram/formatters.py`:
```python
from backend.tickets.models import Ticket, TicketStatus, TicketPriority

STATUS_EMOJI = {"new": "🔵", "in_progress": "🟡", "waiting_for_user": "🟠", ...}
PRIORITY_EMOJI = {"critical": "🔴", "high": "🟠", "normal": "🔵", "low": "🟢"}

def format_ticket_card(ticket: Ticket) -> str: ...     # HTML for TG: header + description + SLA
def format_ticket_list_item(ticket: Ticket) -> str: ... # One-line summary for list
def format_article_preview(article) -> str: ...         # Title + truncated body (4000 chars max)
def format_project_card(project) -> str: ...            # Name, type, progress bar, current phase
def escape_html(text: str) -> str: ...                  # Escape <, >, & for TG HTML parse_mode
```
Use `html.escape()` from stdlib for `escape_html()`.

- [ ] **Step 7:** Register middlewares in `backend/telegram/bot.py` — inside `create_bot_and_dispatcher()`, after creating Dispatcher:
```python
from backend.telegram.middlewares.auth import AuthMiddleware
from backend.telegram.middlewares.throttle import ThrottleMiddleware
from backend.telegram.middlewares.logging import LoggingMiddleware
dp.message.outer_middleware(AuthMiddleware())
dp.callback_query.outer_middleware(AuthMiddleware())
dp.message.outer_middleware(ThrottleMiddleware())
dp.message.outer_middleware(LoggingMiddleware())
dp.callback_query.outer_middleware(LoggingMiddleware())
```

- [ ] **Step 8:** Add tests for formatters and keyboards (pure unit tests, no DB):
```python
class TestFormatters:
    def test_escape_html(self): ...
    def test_format_ticket_list_item(self): ...

class TestKeyboards:
    def test_main_menu_resident_no_projects(self): ...
    def test_main_menu_pm_shows_projects(self): ...
    def test_pagination_first_page(self): ...
    def test_pagination_last_page(self): ...
```
Run: `pytest tests/test_telegram_bot.py -v -k "Formatters or Keyboards"`

- [ ] **Step 9:** Commit: `feat: telegram middlewares (auth, throttle, logging) + keyboards + formatters`

---

## Task 4: Account Linking Service + Auth Endpoints + /start Handler

**Files:**
- Create: `backend/telegram/services/__init__.py` (empty)
- Create: `backend/telegram/services/linking.py`
- Modify: `backend/auth/router.py` (add 2 endpoints)
- Create: `backend/telegram/handlers/start.py`
- Modify: `backend/telegram/handlers/__init__.py` (register start router)
- Test: `tests/test_telegram_bot.py` (linking tests)

**What this task produces:** Users can generate deep link tokens in portal, open `/start <token>` in bot, and get their account linked. Ghost migration works.

- [ ] **Step 1:** Create `backend/telegram/services/linking.py`:
```python
import secrets
from datetime import datetime, timedelta
from sqlmodel import select, update
from backend.database import async_session_factory
from backend.auth.models import User
from backend.tickets.models import Ticket, TicketComment, TicketEvent
from backend.telegram.config import LINK_TOKEN_TTL_MINUTES, LINK_TOKEN_MAX_PER_HOUR

async def generate_token(user_id: str) -> dict:
    """Returns {token, deeplink, expires_at}. Raises ValueError if rate limited."""

async def verify_token(token: str) -> dict | None:
    """Returns {user: User, token_row} or None if invalid/expired/used."""

async def link_account(token: str, chat_id: int) -> User:
    """Links user, marks token used, migrates ghost. Returns linked User."""

async def migrate_ghost(real_user_id: str, chat_id: int, session) -> int:
    """Moves ghost user's tickets/comments/events to real user. Returns count migrated."""

async def unlink_account(user_id: str) -> None:
    """Clears telegram_chat_id and telegram_linked_at."""
```

Key implementation details for `migrate_ghost()`:
- Find ghost: `SELECT * FROM users WHERE telegram_chat_id = :chat_id AND email LIKE '%@telegram.pass24.local' AND id != :real_user_id`
- Update tickets: `UPDATE tickets SET creator_id = :real_id WHERE creator_id = :ghost_id`
- Update comments: `UPDATE ticket_comments SET author_id = :real_id WHERE author_id = :ghost_id`
- Update events: `UPDATE ticket_events SET actor_id = :real_id WHERE actor_id = :ghost_id`
- Deactivate ghost: `ghost.telegram_chat_id = None, ghost.is_active = False, ghost.email = f"deleted_{ghost.id}@telegram.pass24.local"`

- [ ] **Step 2:** Add endpoints to `backend/auth/router.py`:

```python
@router.post("/telegram/link-token")
async def generate_telegram_link_token(
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Generate one-time deep link token for Telegram bot binding."""
    from backend.telegram.services.linking import generate_token
    result = await generate_token(str(current_user.id))
    return result

@router.delete("/telegram/link")
async def unlink_telegram(
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Unlink Telegram from user account."""
    from backend.telegram.services.linking import unlink_account
    await unlink_account(str(current_user.id))
    return {"ok": True}
```

- [ ] **Step 3:** Create `backend/telegram/handlers/start.py`:
- Handle `/start` command with `CommandStart` filter
- If `command.args` (deep link token): `verify_token()` → preview → confirm callback → `link_account()` → show main menu
- If no args and user linked: show main menu
- If no args and user not linked: welcome message + `[🔗 Привязать аккаунт]` URL button pointing to `{APP_BASE_URL}/settings#telegram`

Use aiogram `CommandStart(deep_link=True)` filter for the token case and plain `CommandStart()` for the no-token case. Two separate handlers with priority.

- [ ] **Step 4:** Register start router in `backend/telegram/handlers/__init__.py`:
```python
from backend.telegram.handlers.start import router as start_router
dp.include_router(start_router)
```

- [ ] **Step 5:** Write linking tests:
```python
class TestLinking:
    async def test_generate_token_creates_record(self): ...
    async def test_generate_token_rate_limit(self): ...
    async def test_verify_valid_token(self): ...
    async def test_verify_expired_token_returns_none(self): ...
    async def test_verify_used_token_returns_none(self): ...
    async def test_link_account_sets_chat_id_and_linked_at(self): ...
    async def test_link_account_marks_token_used(self): ...
    async def test_migrate_ghost_transfers_tickets(self): ...
    async def test_migrate_ghost_deactivates_ghost(self): ...
    async def test_unlink_clears_fields(self): ...
```
Run: `pytest tests/test_telegram_bot.py::TestLinking -v`

- [ ] **Step 6:** Commit: `feat: account linking — deep link tokens, /start handler, ghost migration`

---

## Task 5: TelegramLinkCard Frontend Component

**Files:**
- Create: `frontend/src/components/TelegramLinkCard.vue`
- Modify: `frontend/src/pages/SettingsPage.vue`
- Modify: `frontend/src/api/auth.ts` (or equivalent API module)

**What this task produces:** Settings page shows "Telegram Bot" section with QR code + link button. Auto-detects when linking completes.

- [ ] **Step 1:** Add API methods to `frontend/src/api/auth.ts` (or the appropriate API file):
```typescript
export async function generateTelegramLinkToken(): Promise<{token: string, deeplink: string, expires_at: string}> {
  const res = await api.post('/auth/telegram/link-token')
  return res.data
}
export async function unlinkTelegram(): Promise<void> {
  await api.delete('/auth/telegram/link')
}
```

- [ ] **Step 2:** Create `frontend/src/components/TelegramLinkCard.vue`:
Three states:
1. **Not linked** — button "Привязать Telegram" → calls `generateTelegramLinkToken()` → shows QR code (npm package `qrcode.vue` or generate via canvas) + "Открыть Telegram" button + countdown timer (10 min) + polling `authStore.fetchUser()` every 3s until `user.telegram_chat_id` appears
2. **Linked** — shows date, "Открыть бота" link button, "Отвязать" button → `unlinkTelegram()` + `authStore.fetchUser()`
3. **Loading/Error** — standard states

QR generation: use a lightweight approach — either inline SVG via a small library, or a simple `<img>` tag pointing to a QR API (but we want to avoid external deps for privacy). Recommend: `qrcode` npm package rendered to canvas. If too heavy, fallback to just the clickable link without QR.

- [ ] **Step 3:** Add `<TelegramLinkCard />` to `frontend/src/pages/SettingsPage.vue` in the settings sections area. Import and place after existing sections. Guard with `v-if="authStore.user"`.

- [ ] **Step 4:** Test manually in browser: go to Settings → see Telegram section → click "Привязать" → see QR + link → verify polling works (after actual linking, card switches to "Linked" state).

- [ ] **Step 5:** Commit: `feat: TelegramLinkCard component for account binding in Settings`

---

## Task 6: Main Menu + Free-Text Fallback

**Files:**
- Create: `backend/telegram/handlers/menu.py`
- Modify: `backend/telegram/handlers/__init__.py`
- Create: `backend/telegram/services/ticket_service.py` (count query only for now)

**What this task produces:** Linked users see the main menu. Unlinked users get guided to link. Free text shows action choices.

- [ ] **Step 1:** Create `backend/telegram/services/ticket_service.py` with a single function for now:
```python
async def count_active_tickets(user_id: str) -> int:
    """Count tickets where creator_id=user_id and status != closed."""
```

- [ ] **Step 2:** Create `backend/telegram/handlers/menu.py`:
- `show_main_menu(message_or_callback, user)` — reusable function that:
  - Fetches `count_active_tickets(user.id)`
  - If PM: fetches `pending_approvals_count(user.customer_id)` (stub returning 0 for now)
  - Sends/edits message with menu text + `main_menu_kb(user, counts)`
- Callback handler for `mm:main` → `show_main_menu(callback)`
- Message handler (catch-all, lowest priority) for free text when no FSM state active:
  - Save text in FSM data as `pending_text`
  - Show: "💬 Что сделать с этим?" + buttons `[📝 Создать заявку] [🤖 AI] [📚 KB] [🏠 Меню]`
  - Callbacks: `ft:ticket`, `ft:ai`, `ft:kb`, `ft:menu`

- [ ] **Step 3:** Register in `handlers/__init__.py`. Order matters — menu router must be LAST (catch-all).

- [ ] **Step 4:** Test: send `/start` as linked user → see main menu. Type free text → see action choices. Click [🏠 Меню] → back to menu.

- [ ] **Step 5:** Commit: `feat: main menu with counters + free-text fallback handler`

---

## Task 7: Ticket Wizard — Product + Category + Description

**Files:**
- Create: `backend/telegram/keyboards/ticket_wizard.py`
- Create: `backend/telegram/handlers/tickets_create.py` (partial — steps 1-3 of wizard)
- Modify: `backend/telegram/handlers/__init__.py`

**What this task produces:** User can start ticket creation, pick product and category, enter description with attachments.

- [ ] **Step 1:** Create `backend/telegram/keyboards/ticket_wizard.py`:
```python
PRODUCT_LABELS = {
    "pass24_online": "🏠 PASS24.online", "mobile_app": "📱 Мобильное приложение",
    "pass24_key": "🔑 PASS24 Key", "pass24_control": "📷 Распознавание",
    "pass24_auto": "🚗 PASS24 Auto", "equipment": "🔌 Оборудование",
    "integration": "🔗 Интеграции", "other": "❓ Другое",
}
PRODUCT_CATEGORIES = {
    "mobile_app": ["app_issues", "passes", "recognition", "registration", "consultation", "other"],
    # ... mappings for each product
}
CATEGORY_LABELS = { ... }
IMPACT_LABELS = {"high": "🌐 Все / весь объект", "medium": "👥 Группа", "low": "👤 Только я"}
URGENCY_LABELS = {"high": "🔴 Немедленно", "medium": "🟡 Сегодня", "low": "🟢 Может подождать"}

def product_kb() -> InlineKeyboardMarkup: ...
def category_kb(product: str) -> InlineKeyboardMarkup: ...
def description_status_kb(char_count: int, attachment_count: int) -> InlineKeyboardMarkup: ...
def impact_urgency_kb(impact: str | None = None, urgency: str | None = None) -> InlineKeyboardMarkup: ...
def confirm_kb() -> InlineKeyboardMarkup: ...
```

- [ ] **Step 2:** Create `backend/telegram/handlers/tickets_create.py`:
```python
from aiogram.fsm.state import State, StatesGroup

class CreateTicketStates(StatesGroup):
    product = State()
    category = State()
    description = State()
    kb_deflection = State()
    impact_urgency = State()
    confirm = State()
```

Implement handlers:
- `mm:tc` callback → set state `product`, edit message to product keyboard
- `tc:prod:<value>` callback → save product in state data, set state `category`, show category keyboard
- `tc:cat:<value>` callback → save category, set state `description`, show "Опиши проблему" prompt
- In `description` state: accumulate text messages into `state.data["description"]`, photo/doc/video/voice into `state.data["attachments"]` list (store `file_id`, `filename`, `content_type`). After each message, edit a status message showing char count + attachment count + `[➡ Далее]` button (visible when `len(desc) >= 10 or attachments`)
- `tc:back` callbacks at each step → go back one state, restore previous keyboard

- [ ] **Step 3:** Register `tickets_create` router in `handlers/__init__.py` — before `menu` router (more specific).

- [ ] **Step 4:** Test: start ticket creation → pick product → pick category → type description → see status update → add photo → see attachment count increase.

- [ ] **Step 5:** Commit: `feat: ticket wizard — product, category, description steps`

---

## Task 8: KB Deflection + Impact/Urgency + Confirm + Create Ticket

**Files:**
- Create: `backend/telegram/services/kb_service.py`
- Create: `backend/telegram/deflection.py`
- Modify: `backend/telegram/handlers/tickets_create.py` (add steps 4-6)
- Expand: `backend/telegram/services/ticket_service.py` (add `create_ticket()`)

**What this task produces:** Full ticket creation wizard working end-to-end. KB deflection suggests articles before creating a ticket.

- [ ] **Step 1:** Create `backend/telegram/services/kb_service.py`:
```python
async def search_articles(query: str, limit: int = 3) -> list[dict]:
    """FTS search over knowledge base. Returns [{id, title, slug, category, helpful_percent}]."""
```
Implementation: extract the FTS logic from `backend/knowledge/router.py:158-256` into a standalone async function. Use `async_session_factory()`. Return dicts, not ORM objects.

Also create `backend/knowledge/services.py` if it doesn't exist, move the search logic there, and have both the existing knowledge router endpoint and this new function call the shared service.

- [ ] **Step 2:** Create `backend/telegram/deflection.py`:
```python
async def suggest_articles(description: str) -> list[dict]:
    """Search KB for description text. Returns top-3 articles or empty list."""
    from backend.telegram.services.kb_service import search_articles
    return await search_articles(description, limit=3)
```

- [ ] **Step 3:** Add handlers in `tickets_create.py`:
- `tc:desc_done` callback → call `suggest_articles(description)`:
  - If articles found → set state `kb_deflection`, show articles with `[📄 Статья 1] [📄 Статья 2] ... [➡ Не помогло, создать заявку]`
  - If no articles → skip to `impact_urgency` state
- `tc:defl:view:<slug>` → show article text (truncated to 4000 chars) + `[👍 Помогло] [👎 Не помогло] [⬅ Назад к заявке]`
- `tc:defl:helpful:<slug>` → record `article_feedback(helpful=True)`, clear FSM state, show "Отлично! Рады что помогло" + main menu button — **DEFLECTION: ticket NOT created**
- `tc:defl:nope` → proceed to impact_urgency

- [ ] **Step 4:** Impact/urgency handler:
- Show `impact_urgency_kb()` with 6 buttons (2 rows × 3) + `[⏭ Пропустить]`
- `tc:imp:<value>` → save impact, update keyboard to highlight selection
- `tc:urg:<value>` → save urgency, if both set → show `[➡ Далее]`
- `tc:iu:skip` → proceed to confirm without impact/urgency

- [ ] **Step 5:** Confirm handler:
- Build preview text using `formatters.py`
- Show `[✅ Отправить] [✏ Изменить описание] [✕ Отмена]`
- `tc:confirm` → call `ticket_service.create_ticket(state_data, user)`

- [ ] **Step 6:** Implement `create_ticket()` in `ticket_service.py`:
```python
async def create_ticket(data: dict, user: User) -> Ticket:
    """Create ticket from wizard state data. Downloads TG attachments, applies auto-priority."""
```
Logic:
1. Create `Ticket(source=TELEGRAM, creator_id=user.id, title=data["description"][:100], description=data["description"], product=data["product"], category=data["category"], ...)`
2. If impact/urgency provided: set them, call `ticket.recalculate_priority()`
3. Else: call `ticket.auto_detect_category()`, `ticket.assign_priority_based_on_context()`
4. Call `ticket.auto_assign_group()`
5. Check default assignee via `get_default_assignee_id()`
6. Create `TicketEvent`
7. For each attachment in `data["attachments"]`: download from TG using `_tg_download_file(file_id)`, save to disk + create `Attachment` record (reuse pattern from old `telegram.py:108-139`)
8. If deflection articles were shown: create `TicketArticleLink(relationship="related")` for each
9. Commit, return ticket

- [ ] **Step 7:** After ticket creation, show confirmation message:
```
✅ Заявка #{ticket.id[:8]} создана
🔵 NORMAL • Новая
SLA ответа: до HH:MM (через Xч Yм)

[📋 Открыть карточку]  [🏠 Меню]
```

- [ ] **Step 8:** Test full wizard flow end-to-end. Verify ticket appears in DB with correct fields.

- [ ] **Step 9:** Commit: `feat: ticket wizard — KB deflection, impact/urgency, confirm, create`

---

## Task 9: My Tickets List + Ticket Card

**Files:**
- Create: `backend/telegram/keyboards/ticket_detail.py`
- Create: `backend/telegram/handlers/tickets_list.py`
- Expand: `backend/telegram/services/ticket_service.py` (add `list_my_tickets()`, `get_ticket()`)

**What this task produces:** Users can view their tickets, see details, browse comments with pagination.

- [ ] **Step 1:** Add to `ticket_service.py`:
```python
async def list_my_tickets(user_id: str, filter: str = "active", page: int = 1, per_page: int = 5) -> tuple[list[Ticket], int]:
    """Returns (tickets, total_count). Filter: 'active'|'all'|'closed'."""

async def get_ticket_with_comments(ticket_id_prefix: str, user_id: str, comments_limit: int = 10, comments_offset: int = 0) -> dict | None:
    """Returns {ticket, comments, total_comments} or None if not found/not owned."""
```

- [ ] **Step 2:** Create `backend/telegram/keyboards/ticket_detail.py`:
```python
def ticket_actions_kb(ticket_id: str, status: str) -> InlineKeyboardMarkup:
    # [💬 Ответить] [📎 Вложение] — always
    # [✕ Закрыть] — if not closed/resolved
    # [⭐ Оценить] — if status == resolved
    # [⬅ К списку] [🏠 Меню]
```

- [ ] **Step 3:** Create `backend/telegram/handlers/tickets_list.py`:
- `mm:tl` callback → show ticket list with `active` filter
- `tl:filter:<value>` → switch filter (active/all/closed), page 1
- `tl:page:<n>:<filter>` → show page N
- `tl:open:<id8>` → show ticket card (header, description, last comments, actions)
- `tl:history:<id8>:<offset>` → paginate comments

Format ticket list using `formatters.format_ticket_list_item()`. Use `edit_text()` for all transitions.

- [ ] **Step 4:** Register router in `handlers/__init__.py`.

- [ ] **Step 5:** Test: create a ticket via wizard → go to My Tickets → see it listed → open card → see details and comments.

- [ ] **Step 6:** Commit: `feat: my tickets list with filters, pagination, and ticket card view`

---

## Task 10: Reply to Ticket + Close + CSAT

**Files:**
- Create: `backend/telegram/handlers/tickets_reply.py`
- Create: `backend/telegram/handlers/csat.py`
- Expand: `backend/telegram/services/ticket_service.py` (add `add_comment()`, `close_ticket()`, `rate_csat()`)

**What this task produces:** Users can reply to tickets, close them, and rate CSAT.

- [ ] **Step 1:** Add to `ticket_service.py`:
```python
async def add_comment(ticket_id: str, user: User, text: str, attachments: list[dict] | None = None) -> TicketComment:
    """Add comment + optional attachments. Sets has_unread_reply, transitions WAITING→IN_PROGRESS."""

async def close_ticket(ticket_id: str, user: User) -> Ticket:
    """Transition ticket to CLOSED. Raises ValueError if not allowed."""

async def rate_csat(ticket_id: str, user_id: str, rating: int, comment: str | None = None) -> None:
    """Set satisfaction_score and optionally satisfaction_comment. Close ticket if resolved."""
```

- [ ] **Step 2:** Create `backend/telegram/handlers/tickets_reply.py`:
- `tl:reply:<id8>` callback → set FSM state `ReplyStates.typing`, store ticket_id in state data
- In `typing` state: accumulate text + attachments (same pattern as description step in wizard)
- `tl:reply_done:<id8>` → call `add_comment()`, show confirmation, return to ticket card
- `tl:close:<id8>` → confirmation prompt "Точно закрыть?" → `[✅ Да] [✕ Нет]` → `close_ticket()`

- [ ] **Step 3:** Create `backend/telegram/handlers/csat.py`:
- `tl:csat:<id8>` callback (from ticket card when RESOLVED) → show 5 star buttons
- `csat:rate:<id8>:<n>` → if n <= 3: set FSM state asking for improvement comment → `rate_csat()`; if n >= 4: `rate_csat()` immediately + "Спасибо!"
- Also handle push-triggered CSAT (callback from notification message — same `csat:rate:*` pattern)

- [ ] **Step 4:** Register both routers.

- [ ] **Step 5:** Test: open ticket card → Reply → type text → send → verify comment in DB. Open resolved ticket → rate 5 stars → verify `satisfaction_score=5`.

- [ ] **Step 6:** Commit: `feat: ticket reply, close, and CSAT rating in telegram bot`

---

## Task 11: KB Search + AI Chat

**Files:**
- Create: `backend/telegram/keyboards/kb.py`
- Create: `backend/telegram/handlers/kb.py`
- Create: `backend/telegram/services/ai_service.py`
- Create: `backend/telegram/handlers/ai.py`

**What this task produces:** Users can search KB, view articles, give feedback. AI chat mode with RAG.

- [ ] **Step 1:** Create `backend/telegram/keyboards/kb.py`:
```python
def kb_search_results_kb(articles: list[dict]) -> InlineKeyboardMarkup: ...
def kb_article_kb(slug: str) -> InlineKeyboardMarkup: ...  # [👍] [👎] [📝 Создать заявку] [⬅ Назад]
```

- [ ] **Step 2:** Create `backend/telegram/handlers/kb.py`:
- `mm:kb` callback → "Напиши, что ищешь", set FSM `KBStates.awaiting_query`
- Text in `awaiting_query` → `kb_service.search_articles(text, limit=5)` → show results
- `kb:open:<slug>` → `kb_service.get_article(slug)` → format and show (split to multiple messages if > 4000 chars)
- `kb:helpful:<slug>:yes/no` → `kb_service.record_feedback(slug, helpful)` → ack
- `kb:mkticket:<slug>` → start wizard with auto-link `created_from`

- [ ] **Step 3:** Create `backend/telegram/services/ai_service.py`:
```python
from backend.assistant.rag import search_knowledge

async def ask(query: str, history: list[dict] | None = None) -> dict:
    """Returns {answer: str, sources: [{title, slug}]}."""
```
Implementation: call `search_knowledge(query)` to get context docs, then call Claude API with context + query + history. Return answer + sources. If Qdrant/Anthropic not configured → return fallback message "AI-ассистент временно недоступен".

- [ ] **Step 4:** Create `backend/telegram/handlers/ai.py`:
- `mm:ai` callback → set FSM `AIChatStates.chatting`, show welcome message
- Text in `chatting` → `ai_service.ask(text, history_from_state)` → format response with sources
- Show buttons: `[📝 Создать заявку] [📄 Article links] [⬅ Выйти]`
- `ai:exit` → clear state, show main menu
- `ai:mkticket` → start wizard with prefilled description from conversation

- [ ] **Step 5:** Register both routers.

- [ ] **Step 6:** Commit: `feat: KB search/article view + AI chat mode in telegram bot`

---

## Task 12: PM Workspace — Projects + Approvals

**Files:**
- Modify: `backend/projects/router.py` (extract approval logic)
- Modify: `backend/projects/services.py` (add approve/reject functions)
- Create: `backend/telegram/keyboards/projects.py`
- Create: `backend/telegram/services/project_service.py`
- Create: `backend/telegram/handlers/projects.py`
- Create: `backend/telegram/handlers/approvals.py`

**What this task produces:** PM users see their projects, current phases, and can approve/reject phases directly in Telegram.

- [ ] **Step 1:** Extract approval logic from `backend/projects/router.py` into `backend/projects/services.py`:
```python
async def approve_phase(session, approval_id: str, user_id: str) -> dict:
    """Approve a pending ProjectApproval. Returns {approval, phase, project}."""

async def reject_phase(session, approval_id: str, user_id: str, reason: str) -> dict:
    """Reject a pending ProjectApproval with reason. Returns {approval, phase, project}."""
```
The router endpoints should then call these service functions instead of having inline logic. This is a refactor — behavior stays identical, just extraction.

- [ ] **Step 2:** Create `backend/telegram/services/project_service.py`:
```python
async def list_user_projects(customer_id: str) -> list[dict]: ...
async def get_project_summary(project_id_prefix: str) -> dict | None: ...
async def pending_approvals(customer_id: str) -> list[dict]: ...
async def pending_approvals_count(customer_id: str) -> int: ...
```

- [ ] **Step 3:** Create `backend/telegram/keyboards/projects.py`:
```python
def project_list_kb(projects: list[dict]) -> InlineKeyboardMarkup: ...
def project_card_kb(project_id: str) -> InlineKeyboardMarkup: ...
    # [🏗 Фазы] [📎 Документы] [⚠ Риски] [💬 Комментарии] [⬅ Назад]
def approval_kb(approval_id: str) -> InlineKeyboardMarkup: ...
    # [✅ Утвердить] [❌ Отклонить]
```

- [ ] **Step 4:** Create `backend/telegram/handlers/projects.py`:
- `mm:pr` → show project list (PM check via `data["user"].role`)
- `pr:open:<id8>` → project card with phases, progress, current phase
- `pr:approvals:<id8>` → list pending approvals for this project
- Sub-menus for phases, documents (show file names with `sendDocument`), risks (severity-colored cards)

- [ ] **Step 5:** Create `backend/telegram/handlers/approvals.py`:
- `ap:approve:<id8>` → confirmation → call `projects.services.approve_phase()` → ack
- `ap:reject:<id8>` → FSM state asking for reason → text input → `reject_phase(reason)` → ack
- Guard: verify `user.role == property_manager` in handler

- [ ] **Step 6:** Register routers. Update main menu to show `pending_approvals_count()` for PM users.

- [ ] **Step 7:** Commit: `feat: PM workspace — projects list, card, approvals in telegram bot`

---

## Task 13: Notify Service + Push Notifications + Settings

**Files:**
- Create: `backend/telegram/services/notify.py`
- Create: `backend/telegram/handlers/settings.py`
- Modify: `backend/tickets/router.py` (update imports)
- Modify: `backend/tickets/sla_watcher.py` (add TG branch)

**What this task produces:** Push notifications with inline keyboards. Notification toggles in settings. SLA watcher sends TG warnings.

- [ ] **Step 1:** Create `backend/telegram/services/notify.py`:
```python
import asyncio
import httpx
import logging
from backend.telegram.config import BOT_TOKEN

async def _tg_send_with_retry(chat_id: int, payload: dict, *, max_attempts: int = 3) -> bool: ...
async def _tg_send_message(chat_id: int, text: str, reply_markup: dict | None = None) -> bool: ...
async def _tg_send_document(chat_id: int, file_path, caption: str = "") -> bool: ...
async def _check_preferences(user, pref_key: str) -> bool: ...
async def _auto_unlink_on_403(chat_id: int) -> None: ...

async def notify_telegram_comment(chat_id, ticket_id, ticket_title, comment_text, author_name, attachment_paths=None): ...
async def notify_telegram_status(chat_id, ticket_id, ticket_title, old_status, new_status): ...
async def notify_telegram_sla_warning(chat_id, ticket_id, ticket_title, deadline): ...
async def notify_telegram_csat_request(chat_id, ticket_id, ticket_title): ...
async def notify_telegram_approval_request(chat_id, ticket_id, phase_name, project_name, approval_id): ...
async def notify_telegram_milestone(chat_id, project_name, phase_name): ...
async def notify_telegram_risk(chat_id, project_name, risk_description, severity): ...
```

Key differences from old `notifications/telegram.py`:
- Each function checks `telegram_preferences` before sending
- Each function includes inline keyboards (e.g., comment notification has `[💬 Ответить] [📋 Открыть]`)
- `_tg_send_with_retry()` with exponential backoff + 403 auto-unlink
- CSAT notification includes 5 star buttons inline
- Approval notification includes `[✅ Утвердить] [❌ Отклонить]` inline

- [ ] **Step 2:** Modify `backend/tickets/router.py`:
Change imports at lines ~786-790 and ~907-917:
```python
# OLD: from backend.notifications.telegram import notify_telegram_status
# NEW: from backend.telegram.services.notify import notify_telegram_status
# Same for notify_telegram_comment
```
Function signatures are identical — just change import path.

- [ ] **Step 3:** Add TG branch to `backend/tickets/sla_watcher.py`:
After the email warning block, add:
```python
if creator.telegram_chat_id:
    prefs = creator.telegram_preferences or {}
    if prefs.get("notify_sla", True):
        from backend.telegram.services.notify import notify_telegram_sla_warning
        await notify_telegram_sla_warning(
            chat_id=creator.telegram_chat_id,
            ticket_id=ticket.id,
            ticket_title=ticket.title,
            deadline=deadline,
        )
```

- [ ] **Step 4:** Create `backend/telegram/handlers/settings.py`:
- `mm:st` callback → show settings screen: account info, notification toggles, unlink button
- `st:toggle:<key>` → flip `user.telegram_preferences[key]`, update message
- `st:unlink` → confirmation → `linking.unlink_account()` → farewell message

- [ ] **Step 5:** Register settings router.

- [ ] **Step 6:** Commit: `feat: telegram push notifications with inline keyboards + settings handler`

---

## Task 14: Compat Mode + Cleanup + Integration Tests + Docs

**Files:**
- Delete: `backend/notifications/telegram.py`
- Modify: `backend/telegram/middlewares/auth.py` (add compat mode)
- Create: `tests/test_telegram_webhook.py`
- Modify: `agent_docs/architecture.md`
- Modify: `agent_docs/adr.md` (add ADR-008)
- Modify: `agent_docs/development-history.md`

**What this task produces:** Compat mode for unlinked users. Old telegram module removed. Integration tests passing. Documentation updated.

- [ ] **Step 1:** Add compat mode logic to `backend/telegram/middlewares/auth.py`:
```python
# In the middleware, if user is None (not linked):
#   Check if we're in "compat mode" (first 2 weeks after deploy)
#   If compat mode is ON and message has text:
#     Fall through to a compat handler that creates ghost user + ticket (old behavior)
#   If compat mode is OFF:
#     Show "Привяжи аккаунт" message
```
Compat mode flag: `TELEGRAM_COMPAT_MODE = True` in `backend/telegram/config.py`. Set to `False` manually after 2 weeks.

Create a compat handler in `backend/telegram/handlers/start.py` that replicates the old ghost-user + ticket-creation flow from `notifications/telegram.py` for unlinked users.

- [ ] **Step 2:** Delete `backend/notifications/telegram.py`. Verify no remaining imports:
```bash
grep -r "from backend.notifications.telegram" backend/ --include="*.py"
grep -r "notifications.telegram" backend/ --include="*.py"
```
All references should now point to `backend.telegram.services.notify` (done in Task 13).

- [ ] **Step 3:** Create `tests/test_telegram_webhook.py` — integration tests:
```python
class TestWebhook:
    async def test_webhook_rejects_wrong_secret(self): ...
    async def test_webhook_accepts_valid_update(self): ...

class TestStartFlow:
    async def test_start_without_token_unlinked_shows_welcome(self): ...
    async def test_start_with_valid_token_links_account(self): ...
    async def test_start_with_expired_token_shows_error(self): ...

class TestTicketWizardFlow:
    async def test_full_wizard_creates_ticket(self): ...
    async def test_wizard_cancel_clears_state(self): ...

class TestCompatMode:
    async def test_unlinked_text_creates_ghost_ticket(self): ...
```
Send realistic Telegram update JSON payloads to the webhook endpoint via test client. Verify DB state after each flow.

- [ ] **Step 4:** Update `agent_docs/adr.md` — add ADR-008:
```markdown
## ADR-008: Telegram Bot v2 — aiogram 3 + PG FSM + отдельный домен (2026-04-17)

**Контекст:** Минимальный бот (390 строк, raw httpx) не поддерживает inline keyboards, wizard'ы, FSM, account linking.

**Решение:** aiogram 3 через FastAPI webhook (feed_update), PostgreSQL FSM storage, deep link account binding, отдельный пакет `backend/telegram/`.

**Альтернативы отклонены:** raw httpx (слишком много boilerplate для wizard'ов), python-telegram-bot (тяжелее, async хуже), Redis FSM (Redis не используется в проекте).

**Последствия:** +1 зависимость (aiogram), +2 таблицы в БД, полная замена notifications/telegram.py.
```

- [ ] **Step 5:** Update `agent_docs/architecture.md`:
- Replace "Telegram (@PASS24bot): webhook, двусторонняя переписка" with expanded section
- Add new tables to migration list
- Update backend structure diagram

- [ ] **Step 6:** Update `agent_docs/development-history.md` with new entry.

- [ ] **Step 7:** Run full test suite:
```bash
pytest tests/test_telegram_bot.py tests/test_telegram_webhook.py -v
pytest tests/test_full_suite.py -v  # verify no regressions
```

- [ ] **Step 8:** Commit: `feat: telegram bot v2 — compat mode, cleanup, integration tests, docs`

- [ ] **Step 9:** Push to main. Verify CI deploys successfully. Apply migration 019 on prod:
```bash
docker exec site-pass24-servicedesk python -m alembic upgrade head
```

- [ ] **Step 10:** Smoke test on prod with real Telegram:
- [ ] Link account via QR
- [ ] Create ticket with wizard + attachment
- [ ] KB deflection: find article → "Помогло" → no ticket created
- [ ] My tickets: list, open card, reply
- [ ] CSAT after resolve
- [ ] AI chat: ask question, get answer
- [ ] Projects list + approve phase (if PM)
- [ ] Settings: toggle notifications, unlink
- [ ] Compat mode: unlinked user sends text → ghost ticket created + "привяжи аккаунт" prompt

---

## Summary

| Task | Description | Est. Files | Depends on |
|---|---|---|---|
| 1 | Foundation: deps + migration + storage | 7 | — |
| 2 | Bot + Dispatcher + Webhook | 4 | 1 |
| 3 | Middlewares + Keyboards + Formatters | 10 | 2 |
| 4 | Account Linking + /start | 5 | 3 |
| 5 | TelegramLinkCard (frontend) | 3 | 4 |
| 6 | Main Menu + Free-text | 3 | 3 |
| 7 | Ticket Wizard (steps 1-3) | 3 | 6 |
| 8 | KB Deflection + Confirm + Create | 4 | 7 |
| 9 | My Tickets + Card | 3 | 6 |
| 10 | Reply + Close + CSAT | 3 | 9 |
| 11 | KB Search + AI Chat | 5 | 6 |
| 12 | PM Projects + Approvals | 6 | 6 |
| 13 | Notify Service + Push + Settings | 4 | 4 |
| 14 | Compat + Cleanup + Tests + Docs | 6 | ALL |

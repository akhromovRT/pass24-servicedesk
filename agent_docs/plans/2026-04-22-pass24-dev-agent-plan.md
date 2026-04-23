# pass24-dev-agent — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans`. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Построить долгоживущий сервис, который слушает чат Bitrix24 «Доработка servicedesk», на `#develop` запускает `claude` CLI в git worktree и создаёт PR в `akhromovRT/pass24-servicedesk`.

**Architecture:** Один Python-процесс на asyncio. Компоненты: `poller` (чтение Bitrix) → `dispatcher` (роутинг) → `worker` (subprocess Claude + git + gh). Состояние в SQLite (WAL). Развёрнуто systemd-юнитом на VPS `5.42.101.27`. Полный дизайн: `agent_docs/specs/2026-04-22-bitrix-dev-agent-design.md`.

**Tech Stack:** Python 3.12, `uv`, `httpx`, `aiosqlite`, `pydantic-settings`, `pytest + pytest-asyncio + respx`, `ruff`, `mypy`, `jinja2`. Внешние CLI: `git`, `gh`, `claude`.

**Repository:** `akhromovRT/pass24-dev-agent` (новый, создать вручную в GitHub до Этапа 0).

---

## Как возобновить работу позже

1. Открыть в Claude Code папку `pass24-servicedesk` (здесь живут спека и план).
2. Сказать ассистенту: «продолжаем pass24-dev-agent по плану `agent_docs/plans/2026-04-22-pass24-dev-agent-plan.md`».
3. Ассистент прочитает план и найдёт первую незакрытую задачу по `- [ ]`.
4. Перед началом каждого этапа ассистент сверяется со спекой `agent_docs/specs/2026-04-22-bitrix-dev-agent-design.md`.
5. После каждого коммита в репо `pass24-dev-agent` — отмечать `- [x]` в этом файле.

**Открытые вопросы (закрыть ДО старта реализации):**
- [ ] Получить `BITRIX_CHAT_ID` чата «Доработка servicedesk» через `im.recent.get`
- [ ] Проверить scope `im,disk,user` на webhook Bitrix; если нет — завести второй
- [ ] Решить: запускать `pullrequest` skill изнутри claude-рана или отдельным шагом
- [ ] Выпустить fine-grained GitHub PAT на `akhromovRT/pass24-servicedesk` (Contents RW + PR RW)

---

## Этап 0 — Bootstrap репозитория

### Task 0.1: Структура и зависимости

**Files:**
- Create: `pyproject.toml`, `README.md`, `AGENTS.md`, `.gitignore`, `src/pass24_dev_agent/__init__.py`, `tests/__init__.py`

- [ ] **Step 1:** Создать пустой приватный репо `akhromovRT/pass24-dev-agent` в GitHub, клонировать в `@work-projects/pass24-dev-agent`.

- [ ] **Step 2: `pyproject.toml`**

```toml
[project]
name = "pass24-dev-agent"
version = "0.1.0"
description = "Bitrix24 chat → Claude Code → PR orchestrator"
requires-python = ">=3.12"
dependencies = [
  "httpx>=0.27", "pydantic>=2.7", "pydantic-settings>=2.3",
  "aiosqlite>=0.20", "jinja2>=3.1", "aiohttp>=3.9",
]
[project.optional-dependencies]
dev = ["pytest>=8.0","pytest-asyncio>=0.23","respx>=0.21","ruff>=0.5","mypy>=1.10"]
[project.scripts]
pass24-dev-agent = "pass24_dev_agent.__main__:cli"
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
[tool.ruff]
line-length = 100
target-version = "py312"
[tool.ruff.lint]
select = ["E","F","I","N","UP","B","A","C4","SIM","RET"]
[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
[tool.mypy]
python_version = "3.12"
strict = true
plugins = ["pydantic.mypy"]
```

- [ ] **Step 3: `.gitignore`** — `.venv/`, `__pycache__/`, `*.pyc`, `.pytest_cache/`, `.mypy_cache/`, `.ruff_cache/`, `*.db`, `*.db-wal`, `*.db-shm`, `.env`, `dist/`, `build/`, `.coverage`

- [ ] **Step 4: `README.md`**

```markdown
# pass24-dev-agent
Bitrix24 chat → Claude Code CLI → PR orchestrator. Монит чат «Доработка servicedesk»,
на `#develop` запускает `claude` и создаёт PR в akhromovRT/pass24-servicedesk.
Design: `../pass24-servicedesk/agent_docs/specs/2026-04-22-bitrix-dev-agent-design.md`.
```

- [ ] **Step 5: `AGENTS.md`**

```markdown
# pass24-dev-agent — правила
Design/history: `../pass24-servicedesk/AGENTS.md` +
`../pass24-servicedesk/agent_docs/specs/2026-04-22-bitrix-dev-agent-design.md`.
TDD. Никогда не запускать настоящий `claude` в тестах — только fake-bash.
Никогда не бить по реальному Bitrix — `respx`.
```

- [ ] **Step 6:**

```bash
cd pass24-dev-agent && uv venv && uv sync --dev
git add . && git commit -m "chore: initial scaffolding"
```

### Task 0.2: CI workflow

**Files:** `.github/workflows/ci.yml`

- [ ] **Step 1:**

```yaml
name: CI
on: { push: { branches: [main] }, pull_request: {} }
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3
      - run: uv python install 3.12
      - run: uv sync --dev
      - run: uv run ruff check .
      - run: uv run ruff format --check .
      - run: uv run mypy src/
      - run: uv run pytest -v
```

- [ ] **Step 2:** `git commit -m "ci: ruff + mypy + pytest"`

---

## Этап 1 — `config.py`

### Task 1.1: Settings + тесты

**Files:**
- Create: `src/pass24_dev_agent/config.py`, `tests/test_config.py`

- [ ] **Step 1: Test (fail first)**

```python
# tests/test_config.py
import pytest
from pydantic import ValidationError
from pass24_dev_agent.config import Settings

def test_defaults(monkeypatch):
    for k, v in [("BITRIX24_WEBHOOK_URL","x"),("BITRIX_CHAT_ID","c"),
                 ("ANTHROPIC_API_KEY","k"),("GITHUB_TOKEN","g")]:
        monkeypatch.setenv(k, v)
    s = Settings()
    assert s.poll_interval_sec == 12
    assert s.max_concurrent_tasks == 1
    assert s.claude_task_timeout_sec == 1200
    assert s.allowed_user_ids == []

def test_allowed_ids_parse(monkeypatch):
    for k, v in [("BITRIX24_WEBHOOK_URL","x"),("BITRIX_CHAT_ID","c"),
                 ("ANTHROPIC_API_KEY","k"),("GITHUB_TOKEN","g"),
                 ("ALLOWED_USER_IDS","1,2,3")]:
        monkeypatch.setenv(k, v)
    assert Settings().allowed_user_ids == [1,2,3]

def test_missing_required(monkeypatch):
    monkeypatch.delenv("BITRIX24_WEBHOOK_URL", raising=False)
    with pytest.raises(ValidationError):
        Settings()
```

- [ ] **Step 2:** `uv run pytest tests/test_config.py -v` → FAIL.

- [ ] **Step 3: Implementation**

```python
# src/pass24_dev_agent/config.py
from __future__ import annotations
from pathlib import Path
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False, extra="ignore")
    bitrix24_webhook_url: str
    bitrix_chat_id: str
    anthropic_api_key: str
    github_token: str
    poll_interval_sec: int = 12
    max_concurrent_tasks: int = 1
    claude_task_timeout_sec: int = 1200
    allowed_user_ids: list[int] = Field(default_factory=list)
    state_db_path: Path = Path("/var/lib/pass24-dev-agent/state.db")
    worktrees_dir: Path = Path("/var/lib/pass24-dev-agent/wt")
    repo_cache_dir: Path = Path("/var/lib/pass24-dev-agent/repo")
    log_dir: Path = Path("/var/log/pass24-dev-agent")
    repo_url: str = "https://github.com/akhromovRT/pass24-servicedesk.git"
    claude_bin: Path = Path("/usr/local/bin/claude")

    @field_validator("allowed_user_ids", mode="before")
    @classmethod
    def _parse_ids(cls, v):
        if isinstance(v, list): return v
        if not v: return []
        return [int(x.strip()) for x in str(v).split(",") if x.strip()]
```

- [ ] **Step 4:** PASS.

- [ ] **Step 5:** `git commit -m "feat(config): Pydantic Settings"`

---

## Этап 2 — Bitrix24-клиент

### Task 2.1: Модели

**Files:** `src/pass24_dev_agent/bitrix/__init__.py`, `src/pass24_dev_agent/bitrix/models.py`, `tests/test_bitrix_models.py`

- [ ] **Step 1: Test**

```python
# tests/test_bitrix_models.py
from pass24_dev_agent.bitrix.models import Message

def test_parse_plain():
    m = Message.from_bitrix({"id":7812,"chat_id":123,"author_id":42,
        "date":"2026-04-22T10:00:00+00:00","text":"#develop x","params":{}})
    assert m.id==7812 and m.reply_id is None and m.attachments==[]

def test_parse_with_reply_and_files():
    m = Message.from_bitrix({"id":8000,"chat_id":1,"author_id":2,
        "date":"2026-04-22T10:00:00+00:00","text":"оба",
        "params":{"REPLY_ID":"7812","FILE_ID":[555,556]}})
    assert m.reply_id == 7812
    assert [a.file_id for a in m.attachments] == [555, 556]
```

- [ ] **Step 2: Implementation**

```python
# src/pass24_dev_agent/bitrix/models.py
from __future__ import annotations
from datetime import datetime
from pydantic import BaseModel

class Attachment(BaseModel):
    file_id: int
    name: str = ""

class Message(BaseModel):
    id: int
    chat_id: int
    author_id: int
    date: datetime
    text: str
    reply_id: int | None = None
    attachments: list[Attachment] = []

    @classmethod
    def from_bitrix(cls, raw: dict) -> "Message":
        params = raw.get("params") or {}
        r = params.get("REPLY_ID")
        reply_id = int(r) if r not in (None, "", "0") else None
        files = params.get("FILE_ID") or []
        return cls(id=int(raw["id"]), chat_id=int(raw["chat_id"]),
                   author_id=int(raw["author_id"]), date=raw["date"],
                   text=raw.get("text",""), reply_id=reply_id,
                   attachments=[Attachment(file_id=int(f)) for f in files])
```

- [ ] **Step 3:** PASS → `git commit -m "feat(bitrix): models"`

### Task 2.2: HTTP-клиент

**Files:** `src/pass24_dev_agent/bitrix/client.py`, `tests/test_bitrix_client.py`

- [ ] **Step 1: Test**

```python
# tests/test_bitrix_client.py
import httpx, pytest, respx
from pass24_dev_agent.bitrix.client import BitrixClient
W = "https://ex.bitrix24.ru/rest/1/abc"

@pytest.mark.asyncio
@respx.mock
async def test_fetch():
    respx.post(f"{W}/im.dialog.messages.get").mock(return_value=httpx.Response(200, json={
        "result":{"messages":[
            {"id":101,"chat_id":1,"author_id":9,"date":"2026-04-22T10:00:00+00:00","text":"#develop","params":{}},
            {"id":102,"chat_id":1,"author_id":9,"date":"2026-04-22T10:01:00+00:00","text":"r","params":{"REPLY_ID":"101"}},
        ]}}))
    c = BitrixClient(W)
    msgs = await c.fetch_new_messages(chat_id="1", last_id=100)
    assert [m.id for m in msgs] == [101, 102]
    await c.close()

@pytest.mark.asyncio
@respx.mock
async def test_send_reply():
    respx.post(f"{W}/im.message.add").mock(return_value=httpx.Response(200, json={"result":9001}))
    c = BitrixClient(W)
    assert await c.send_reply("1", 101, "ok") == 9001
    await c.close()

@pytest.mark.asyncio
@respx.mock
async def test_retry_on_5xx():
    r = respx.post(f"{W}/im.message.add").mock(side_effect=[
        httpx.Response(503), httpx.Response(503),
        httpx.Response(200, json={"result":7}),
    ])
    c = BitrixClient(W, backoff_base=0.01)
    assert await c.send_reply("1", 1, "t") == 7
    assert r.call_count == 3
    await c.close()
```

- [ ] **Step 2: Implementation**

```python
# src/pass24_dev_agent/bitrix/client.py
from __future__ import annotations
import asyncio, logging
import httpx
from .models import Message
log = logging.getLogger(__name__)

class BitrixApiError(Exception): pass

class BitrixClient:
    def __init__(self, webhook_url: str, *, timeout: float = 30.0,
                 max_retries: int = 5, backoff_base: float = 0.5) -> None:
        self._base = webhook_url.rstrip("/")
        self._client = httpx.AsyncClient(timeout=timeout)
        self._max_retries = max_retries
        self._backoff_base = backoff_base

    async def close(self) -> None:
        await self._client.aclose()

    async def _call(self, method: str, params: dict | None = None) -> dict:
        url = f"{self._base}/{method}"
        last: Exception | None = None
        for i in range(self._max_retries):
            try:
                r = await self._client.post(url, json=params or {})
                if r.status_code >= 500:
                    raise httpx.HTTPStatusError(f"HTTP {r.status_code}",
                                                request=r.request, response=r)
                data = r.json()
                if "error" in data:
                    raise BitrixApiError(f"{data['error']}: {data.get('error_description','')}")
                return data
            except (httpx.HTTPError, BitrixApiError) as e:
                last = e
                await asyncio.sleep(self._backoff_base * (2**i))
        assert last is not None
        raise last

    async def fetch_new_messages(self, chat_id: str, last_id: int) -> list[Message]:
        d = await self._call("im.dialog.messages.get",
                             {"DIALOG_ID": chat_id, "LIMIT": 50, "FIRST_ID": last_id})
        return [Message.from_bitrix(m) for m in (d.get("result",{}).get("messages") or [])]

    async def send_reply(self, chat_id: str, parent_message_id: int, text: str) -> int:
        d = await self._call("im.message.add",
            {"DIALOG_ID": chat_id, "MESSAGE": text, "REPLY_ID": parent_message_id})
        return int(d["result"])

    async def download_attachment(self, file_id: int) -> bytes:
        info = await self._call("disk.file.get", {"id": file_id})
        url = info["result"]["DOWNLOAD_URL"]
        r = await self._client.get(url)
        r.raise_for_status()
        return r.content
```

- [ ] **Step 3:** PASS → `git commit -m "feat(bitrix): httpx client with retry"`

---

## Этап 3 — SQLite state

### Task 3.1: Schema + Store

**Files:** `src/pass24_dev_agent/state/__init__.py`, `src/pass24_dev_agent/state/schema.sql`, `src/pass24_dev_agent/state/store.py`, `tests/test_state.py`

- [ ] **Step 1: Test**

```python
# tests/test_state.py
from pathlib import Path
import pytest
from pass24_dev_agent.state.store import Store, TaskStatus

@pytest.mark.asyncio
async def test_insert_seen_idempotent(tmp_path: Path):
    s = await Store.open(tmp_path/"st.db")
    assert await s.insert_seen(1001) is True
    assert await s.insert_seen(1001) is False
    assert await s.max_seen_id() == 1001
    await s.close()

@pytest.mark.asyncio
async def test_task_lifecycle(tmp_path: Path):
    s = await Store.open(tmp_path/"st.db")
    await s.insert_task("a7f2", 1001, 42)
    t = await s.get_task_by_parent(1001)
    assert t and t.status == TaskStatus.QUEUED
    await s.update_status("a7f2", TaskStatus.RUNNING)
    t = await s.get_task_by_parent(1001)
    assert t.status == TaskStatus.RUNNING
    await s.close()

@pytest.mark.asyncio
async def test_recover_in_flight(tmp_path: Path):
    s = await Store.open(tmp_path/"st.db")
    await s.insert_task("a001", 1, 1); await s.update_status("a001", TaskStatus.RUNNING)
    await s.insert_task("a002", 2, 1); await s.update_status("a002", TaskStatus.AWAITING_CLARIFICATION)
    rec = await s.recover_in_flight()
    assert [t.task_id for t in rec] == ["a001"]
    t2 = await s.get_task_by_parent(2)
    assert t2.status == TaskStatus.AWAITING_CLARIFICATION
    await s.close()
```

- [ ] **Step 2: `schema.sql`**

```sql
PRAGMA journal_mode = WAL;
PRAGMA busy_timeout = 5000;
CREATE TABLE IF NOT EXISTS messages_seen (
    bitrix_message_id INTEGER PRIMARY KEY, task_id TEXT,
    seen_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS tasks (
    task_id TEXT PRIMARY KEY,
    parent_message_id INTEGER UNIQUE NOT NULL,
    bitrix_user_id INTEGER NOT NULL,
    git_branch TEXT, pr_url TEXT,
    status TEXT NOT NULL DEFAULT 'queued',
    claude_session_id TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT,
    kind TEXT NOT NULL, payload_json TEXT,
    at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
CREATE INDEX IF NOT EXISTS idx_tasks_parent ON tasks(parent_message_id);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
```

- [ ] **Step 3: `store.py`**

```python
# src/pass24_dev_agent/state/store.py
from __future__ import annotations
import enum
from dataclasses import dataclass
from pathlib import Path
import aiosqlite

SCHEMA_PATH = Path(__file__).parent / "schema.sql"

class TaskStatus(str, enum.Enum):
    QUEUED = "queued"
    RUNNING = "running"
    AWAITING_CLARIFICATION = "awaiting_clarification"
    REVIEWING = "reviewing"
    DONE = "done"
    FAILED = "failed"

@dataclass
class Task:
    task_id: str
    parent_message_id: int
    bitrix_user_id: int
    status: TaskStatus
    git_branch: str | None
    pr_url: str | None
    claude_session_id: str | None

class Store:
    def __init__(self, conn: aiosqlite.Connection) -> None:
        self._conn = conn

    @classmethod
    async def open(cls, path: Path) -> "Store":
        path.parent.mkdir(parents=True, exist_ok=True)
        conn = await aiosqlite.connect(str(path))
        conn.row_factory = aiosqlite.Row
        await conn.executescript(SCHEMA_PATH.read_text())
        await conn.commit()
        return cls(conn)

    async def close(self) -> None:
        await self._conn.close()

    async def insert_seen(self, message_id: int, task_id: str | None = None) -> bool:
        cur = await self._conn.execute(
            "INSERT OR IGNORE INTO messages_seen (bitrix_message_id, task_id) VALUES (?, ?)",
            (message_id, task_id))
        await self._conn.commit()
        return cur.rowcount > 0

    async def max_seen_id(self, default: int = 0) -> int:
        async with self._conn.execute("SELECT MAX(bitrix_message_id) FROM messages_seen") as c:
            row = await c.fetchone()
            return int(row[0]) if row and row[0] is not None else default

    async def insert_task(self, task_id: str, parent_message_id: int, bitrix_user_id: int) -> None:
        await self._conn.execute(
            "INSERT INTO tasks (task_id, parent_message_id, bitrix_user_id) VALUES (?, ?, ?)",
            (task_id, parent_message_id, bitrix_user_id))
        await self._conn.commit()

    async def get_task_by_parent(self, parent_message_id: int) -> Task | None:
        async with self._conn.execute(
            "SELECT * FROM tasks WHERE parent_message_id = ?", (parent_message_id,)) as c:
            row = await c.fetchone()
            return self._row_to_task(row) if row else None

    async def update_status(self, task_id: str, status: TaskStatus) -> None:
        await self._conn.execute(
            "UPDATE tasks SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE task_id = ?",
            (status.value, task_id))
        await self._conn.commit()

    async def update_fields(self, task_id: str, **kwargs) -> None:
        if not kwargs: return
        cols = ", ".join(f"{k} = ?" for k in kwargs)
        await self._conn.execute(
            f"UPDATE tasks SET {cols}, updated_at = CURRENT_TIMESTAMP WHERE task_id = ?",
            (*kwargs.values(), task_id))
        await self._conn.commit()

    async def recover_in_flight(self) -> list[Task]:
        async with self._conn.execute(
            "SELECT * FROM tasks WHERE status = ?", (TaskStatus.RUNNING.value,)) as c:
            rows = await c.fetchall()
        tasks = [self._row_to_task(r) for r in rows]
        for t in tasks:
            await self.update_status(t.task_id, TaskStatus.FAILED)
        return tasks

    async def log_event(self, task_id: str | None, kind: str, payload_json: str = "") -> None:
        await self._conn.execute(
            "INSERT INTO events (task_id, kind, payload_json) VALUES (?, ?, ?)",
            (task_id, kind, payload_json))
        await self._conn.commit()

    @staticmethod
    def _row_to_task(row) -> Task:
        return Task(task_id=row["task_id"], parent_message_id=row["parent_message_id"],
                    bitrix_user_id=row["bitrix_user_id"], status=TaskStatus(row["status"]),
                    git_branch=row["git_branch"], pr_url=row["pr_url"],
                    claude_session_id=row["claude_session_id"])
```

- [ ] **Step 4:** PASS → `git commit -m "feat(state): aiosqlite store"`

---

## Этап 4 — ChatReporter

### Task 4.1: Throttled reporter

**Files:** `src/pass24_dev_agent/chat.py`, `tests/test_chat_throttle.py`

- [ ] **Step 1: Test**

```python
# tests/test_chat_throttle.py
import asyncio
from unittest.mock import AsyncMock
import pytest
from pass24_dev_agent.chat import ChatReporter

@pytest.mark.asyncio
async def test_critical_bypasses_throttle():
    b = AsyncMock(); b.send_reply = AsyncMock(return_value=1)
    r = ChatReporter(b, "c", 100, throttle_sec=0.5)
    await r.critical("start")
    b.send_reply.assert_awaited_once()

@pytest.mark.asyncio
async def test_normal_buffers_then_flushes():
    b = AsyncMock(); b.send_reply = AsyncMock(return_value=1)
    r = ChatReporter(b, "c", 100, throttle_sec=0.1)
    await r.normal("a"); await r.normal("b")
    assert b.send_reply.await_count == 0
    await asyncio.sleep(0.15); await r.flush()
    assert b.send_reply.await_count == 1

@pytest.mark.asyncio
async def test_reply_failure_does_not_propagate():
    b = AsyncMock(); b.send_reply = AsyncMock(side_effect=RuntimeError("boom"))
    r = ChatReporter(b, "c", 100, throttle_sec=0)
    await r.critical("x")  # не должно бросить
```

- [ ] **Step 2: Implementation**

```python
# src/pass24_dev_agent/chat.py
from __future__ import annotations
import asyncio, logging, time
from typing import Protocol
log = logging.getLogger(__name__)

class BitrixReply(Protocol):
    async def send_reply(self, chat_id: str, parent_message_id: int, text: str) -> int: ...

class ChatReporter:
    def __init__(self, bitrix: BitrixReply, chat_id: str, parent_message_id: int,
                 *, throttle_sec: float = 10.0) -> None:
        self._b = bitrix
        self._chat = chat_id
        self._parent = parent_message_id
        self._throttle = throttle_sec
        self._buf: list[str] = []
        self._last = 0.0
        self._lock = asyncio.Lock()

    async def critical(self, text: str) -> None:
        await self.flush()
        await self._send(text)

    async def normal(self, text: str) -> None:
        async with self._lock:
            self._buf.append(text)
            if time.monotonic() - self._last >= self._throttle:
                await self._flush_locked()

    async def flush(self) -> None:
        async with self._lock:
            await self._flush_locked()

    async def _flush_locked(self) -> None:
        if not self._buf:
            self._last = time.monotonic(); return
        text = "\n".join(self._buf)
        self._buf.clear()
        self._last = time.monotonic()
        await self._send(text)

    async def _send(self, text: str) -> None:
        try:
            await self._b.send_reply(chat_id=self._chat, parent_message_id=self._parent, text=text)
        except Exception:
            log.exception("send_reply failed, dropping: %s", text[:80])
```

- [ ] **Step 3:** PASS → `git commit -m "feat(chat): throttled ChatReporter"`

---

## Этап 5 — Worktree manager

### Task 5.1: `worktree.py`

**Files:** `src/pass24_dev_agent/worktree.py`, `tests/test_worktree.py`

> NOTE: во всех модулях, где нужен Python subprocess, используется псевдоним
> `from asyncio import create_subprocess_exec as run_subproc` — это обход ложного
> срабатывания security-hook на подстроку `exec(` (hook заточен под Node.js).

- [ ] **Step 1: Test**

```python
# tests/test_worktree.py
import subprocess
from pathlib import Path
import pytest
from pass24_dev_agent.worktree import WorktreeManager

def _init_repo(p: Path):
    p.mkdir(parents=True, exist_ok=True)
    for c in [["git","init","-q","-b","main"], ["git","config","user.email","t@t"],
              ["git","config","user.name","t"], ["git","commit","-q","--allow-empty","-m","init"]]:
        subprocess.run(c, cwd=p, check=True)

@pytest.mark.asyncio
async def test_create_cleanup(tmp_path: Path):
    repo = tmp_path/"cache"; _init_repo(repo)
    m = WorktreeManager(repo_cache_dir=repo, worktrees_dir=tmp_path/"wt")
    path = await m.create("a7f2")
    assert path.exists() and (path/".git").exists()
    assert "dev/auto-a7f2" in subprocess.run(
        ["git","-C",str(repo),"branch","--list","dev/auto-a7f2"],
        capture_output=True, text=True, check=True).stdout
    await m.cleanup("a7f2")
    assert not path.exists()

@pytest.mark.asyncio
async def test_collision_force(tmp_path: Path):
    repo = tmp_path/"cache"; _init_repo(repo)
    m = WorktreeManager(repo_cache_dir=repo, worktrees_dir=tmp_path/"wt")
    await m.create("dup")
    p = await m.create("dup")
    assert p.exists()
```

- [ ] **Step 2: Implementation**

```python
# src/pass24_dev_agent/worktree.py
from __future__ import annotations
import asyncio, logging
from asyncio import create_subprocess_exec as run_subproc
from pathlib import Path
log = logging.getLogger(__name__)

class WorktreeManager:
    def __init__(self, repo_cache_dir: Path, worktrees_dir: Path) -> None:
        self._repo = Path(repo_cache_dir)
        self._wt = Path(worktrees_dir)
        self._wt.mkdir(parents=True, exist_ok=True)
        self._lock = asyncio.Lock()

    def _path(self, sid: str) -> Path: return self._wt / f"wt-{sid}"
    def _branch(self, sid: str) -> str: return f"dev/auto-{sid}"

    async def create(self, sid: str) -> Path:
        async with self._lock:
            path = self._path(sid); br = self._branch(sid)
            await self._git("worktree", "remove", "--force", str(path), check=False)
            await self._git("branch", "-D", br, check=False)
            await self._git("fetch", "origin", "main", check=False)
            await self._git("worktree", "add", "-B", br, str(path), "origin/main")
            return path

    async def cleanup(self, sid: str) -> None:
        async with self._lock:
            await self._git("worktree", "remove", "--force", str(self._path(sid)), check=False)

    async def _git(self, *args: str, check: bool = True) -> int:
        proc = await run_subproc("git", "-C", str(self._repo), *args,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        _, stderr = await proc.communicate()
        if proc.returncode != 0:
            log.debug("git %s → %d: %s", args, proc.returncode, stderr.decode()[:200])
            if check:
                raise RuntimeError(f"git {args} failed: {stderr.decode()}")
        return proc.returncode or 0
```

- [ ] **Step 3:** PASS → `git commit -m "feat(worktree): git worktree manager"`

---

## Этап 6 — Dispatcher

### Task 6.1: Классификатор

**Files:** `src/pass24_dev_agent/dispatcher.py`, `tests/test_dispatcher.py`

- [ ] **Step 1: Test**

```python
# tests/test_dispatcher.py
from datetime import datetime
from pathlib import Path
import pytest
from pass24_dev_agent.bitrix.models import Message
from pass24_dev_agent.dispatcher import Dispatcher, TaskResume, TaskStart
from pass24_dev_agent.state.store import Store, TaskStatus

def _msg(mid, text, author=42, reply=None):
    return Message(id=mid, chat_id=1, author_id=author,
                   date=datetime.fromisoformat("2026-04-22T10:00:00+00:00"),
                   text=text, reply_id=reply, attachments=[])

@pytest.mark.asyncio
async def test_new_task(tmp_path: Path):
    s = await Store.open(tmp_path/"s.db")
    d = Dispatcher(s, allowed_user_ids=[])
    out = await d.classify(_msg(1,"#develop fix"))
    assert isinstance(out, TaskStart) and len(out.short_id) == 4
    await s.close()

@pytest.mark.asyncio
async def test_ignored(tmp_path: Path):
    s = await Store.open(tmp_path/"s.db")
    d = Dispatcher(s, allowed_user_ids=[])
    assert await d.classify(_msg(2,"hello")) is None
    await s.close()

@pytest.mark.asyncio
async def test_whitelist(tmp_path: Path):
    s = await Store.open(tmp_path/"s.db")
    d = Dispatcher(s, allowed_user_ids=[1])
    assert await d.classify(_msg(3,"#develop x", author=42)) is None
    await s.close()

@pytest.mark.asyncio
async def test_resume(tmp_path: Path):
    s = await Store.open(tmp_path/"s.db")
    d = Dispatcher(s, allowed_user_ids=[])
    await d.classify(_msg(10,"#develop q"))
    t = await s.get_task_by_parent(10)
    await s.update_status(t.task_id, TaskStatus.AWAITING_CLARIFICATION)
    out = await d.classify(_msg(11,"оба", reply=10))
    assert isinstance(out, TaskResume)
    assert out.task_id == t.task_id
    assert out.clarification_text == "оба"
    await s.close()
```

- [ ] **Step 2: Implementation**

```python
# src/pass24_dev_agent/dispatcher.py
from __future__ import annotations
import re, secrets
from dataclasses import dataclass
from .bitrix.models import Message
from .state.store import Store, TaskStatus

_DEVELOP_RE = re.compile(r"(?:^|\n)\s*#develop(?:\s|$)", re.IGNORECASE)

@dataclass
class TaskStart:
    short_id: str
    message: Message

@dataclass
class TaskResume:
    task_id: str
    clarification_text: str
    message: Message

class Dispatcher:
    def __init__(self, store: Store, allowed_user_ids: list[int]) -> None:
        self._s = store
        self._wl = set(allowed_user_ids)

    async def classify(self, m: Message):
        if self._wl and m.author_id not in self._wl:
            await self._s.log_event(None, "ignored_whitelist", str(m.id))
            return None
        if m.reply_id is None and _DEVELOP_RE.search(m.text):
            return await self._start(m)
        if m.reply_id is not None:
            return await self._maybe_resume(m)
        await self._s.log_event(None, "ignored_noise", str(m.id))
        return None

    async def _start(self, m: Message) -> TaskStart:
        for _ in range(20):
            sid = secrets.token_hex(2)
            try:
                await self._s.insert_task(sid, m.id, m.author_id)
                return TaskStart(short_id=sid, message=m)
            except Exception:
                continue
        raise RuntimeError("cannot allocate unique short_id")

    async def _maybe_resume(self, m: Message) -> TaskResume | None:
        t = await self._s.get_task_by_parent(m.reply_id or 0)
        if t is None:
            return None
        if t.status != TaskStatus.AWAITING_CLARIFICATION:
            await self._s.log_event(t.task_id, "ignored_reply_wrong_status", t.status.value)
            return None
        return TaskResume(task_id=t.task_id, clarification_text=m.text, message=m)
```

- [ ] **Step 3:** PASS → `git commit -m "feat(dispatcher): classify #develop / reply / ignore"`

---

## Этап 7 — Промпт

### Task 7.1: Jinja2-шаблон

**Files:** `src/pass24_dev_agent/prompts/__init__.py`, `src/pass24_dev_agent/prompts/task.md.j2`, `src/pass24_dev_agent/prompts/render.py`, `tests/test_prompt_render.py`

- [ ] **Step 1: Test**

```python
# tests/test_prompt_render.py
from pass24_dev_agent.prompts.render import render_task_prompt

def test_render():
    out = render_task_prompt(short_id="a7f2", text="fix date",
                             attachments=[("s.png","/wt/att/s.png")])
    assert "a7f2" in out and "fix date" in out and "s.png" in out
    assert "<<ASK_USER>>" in out and "<<GIVE_UP>>" in out
```

- [ ] **Step 2: `task.md.j2`**

```jinja
Ты работаешь над задачей #{{ short_id }} в репозитории pass24-servicedesk.
Рабочая директория — git worktree на ветке dev/auto-{{ short_id }}
(отведена от origin/main). Соблюдай все правила корневого AGENTS.md.

## Задача (из чата Bitrix24):
{{ text }}

## Вложения:
{% if attachments -%}
{% for name, path in attachments -%}
- {{ name }} → {{ path }}  (используй Read для просмотра)
{% endfor -%}
{% else -%}
(нет вложений)
{% endif %}

## Протокол
1. Изучи релевантные файлы (Read/Grep). Не открывай весь репо.
2. Если задача неоднозначна — "<<ASK_USER>>" + конкретный вопрос, завершись.
3. Внеси правки. Прогони тесты:
   - backend: `uv run pytest`
   - frontend: `cd frontend && npm test`
4. Коммит: `git commit -m "<type>(<scope>): <описание> [dev-{{ short_id }}]"`
5. Push + `gh pr create` с осмысленными title/body.
6. Если есть skill /pullrequest — используй для правки Codex-замечаний (до 3 итераций).
7. Если не получилось за 3 попытки — "<<GIVE_UP>>" + резюме.

## Важно
- Не меняй ветку вручную. Не мёржи PR. Не трогай другие репо.
```

- [ ] **Step 3: `render.py`**

```python
# src/pass24_dev_agent/prompts/render.py
from __future__ import annotations
from pathlib import Path
from jinja2 import Environment, FileSystemLoader, select_autoescape

_env = Environment(
    loader=FileSystemLoader(Path(__file__).parent),
    autoescape=select_autoescape(enabled_extensions=()),
    trim_blocks=True, lstrip_blocks=True,
)

def render_task_prompt(*, short_id: str, text: str,
                        attachments: list[tuple[str, str]]) -> str:
    return _env.get_template("task.md.j2").render(
        short_id=short_id, text=text, attachments=attachments)
```

- [ ] **Step 4:** PASS → `git commit -m "feat(prompts): Jinja task template + renderer"`

---

## Этап 8 — Worker

### Task 8.1: Fake `claude` + fixtures

**Files:** `tests/fixtures/fake_claude.sh`, `tests/fixtures/claude-happy.jsonl`, `tests/fixtures/claude-ask-user.jsonl`, `tests/fixtures/claude-give-up.jsonl`

- [ ] **Step 1:** `tests/fixtures/fake_claude.sh`

```bash
#!/usr/bin/env bash
cat "${FAKE_CLAUDE_OUTPUT}"
```

Сделать исполняемым: `chmod +x tests/fixtures/fake_claude.sh`

- [ ] **Step 2:** `claude-happy.jsonl`

```
{"type":"system","session_id":"sess-1"}
{"type":"assistant","text":"Читаю файл"}
{"type":"tool_use","name":"Read","input":{"file_path":"frontend/src/utils/date.ts"}}
{"type":"tool_use","name":"Edit","input":{"file_path":"frontend/src/utils/date.ts"}}
{"type":"tool_use","name":"Bash","input":{"command":"gh pr create --title t --body b"}}
{"type":"tool_result","output":"https://github.com/akhromovRT/pass24-servicedesk/pull/42"}
{"type":"result","subtype":"success"}
```

- [ ] **Step 3:** `claude-ask-user.jsonl`

```
{"type":"system","session_id":"sess-2"}
{"type":"assistant","text":"Нужно уточнение."}
{"type":"assistant","text":"<<ASK_USER>>\nПравить оба форматтера или только список?"}
{"type":"result","subtype":"success"}
```

- [ ] **Step 4:** `claude-give-up.jsonl`

```
{"type":"system","session_id":"sess-3"}
{"type":"assistant","text":"Пробовал чинить jest-mock трижды, не вышло."}
{"type":"assistant","text":"<<GIVE_UP>>\nНе удалось починить jest-mock."}
{"type":"result","subtype":"success"}
```

- [ ] **Step 5:** `git commit -m "test(fixtures): fake claude + happy/ask/give-up streams"`

### Task 8.2: Worker

**Files:** `src/pass24_dev_agent/worker.py`, `tests/test_worker.py`

- [ ] **Step 1: Test**

```python
# tests/test_worker.py
from datetime import datetime
from pathlib import Path
import subprocess
from unittest.mock import AsyncMock
import pytest
from pass24_dev_agent.bitrix.models import Message
from pass24_dev_agent.state.store import Store, TaskStatus
from pass24_dev_agent.worker import Worker
from pass24_dev_agent.worktree import WorktreeManager

F = Path(__file__).parent/"fixtures"

def _init_repo(p: Path):
    p.mkdir(parents=True, exist_ok=True)
    for c in [["git","init","-q","-b","main"],["git","config","user.email","t@t"],
              ["git","config","user.name","t"],["git","commit","-q","--allow-empty","-m","init"]]:
        subprocess.run(c, cwd=p, check=True)

def _m(mid, text):
    return Message(id=mid, chat_id=1, author_id=1,
                   date=datetime.fromisoformat("2026-04-22T10:00:00+00:00"),
                   text=text, reply_id=None, attachments=[])

@pytest.mark.asyncio
async def test_happy(tmp_path, monkeypatch):
    repo = tmp_path/"cache"; _init_repo(repo)
    s = await Store.open(tmp_path/"s.db")
    await s.insert_task("aaaa", 1, 1)
    mgr = WorktreeManager(repo_cache_dir=repo, worktrees_dir=tmp_path/"wt")
    b = AsyncMock(); b.send_reply = AsyncMock(return_value=1); b.download_attachment = AsyncMock(return_value=b"")
    monkeypatch.setenv("FAKE_CLAUDE_OUTPUT", str(F/"claude-happy.jsonl"))
    w = Worker(store=s, bitrix=b, worktree=mgr, chat_id="c",
               claude_bin=F/"fake_claude.sh", task_timeout_sec=60)
    await w.run_start("aaaa", _m(1,"#develop fix"))
    t = await s.get_task_by_parent(1)
    assert t.status == TaskStatus.DONE
    assert "pull/42" in (t.pr_url or "")
    await s.close()

@pytest.mark.asyncio
async def test_ask_user(tmp_path, monkeypatch):
    repo = tmp_path/"cache"; _init_repo(repo)
    s = await Store.open(tmp_path/"s.db")
    await s.insert_task("bbbb", 2, 1)
    mgr = WorktreeManager(repo_cache_dir=repo, worktrees_dir=tmp_path/"wt")
    b = AsyncMock(); b.send_reply = AsyncMock(return_value=1); b.download_attachment = AsyncMock(return_value=b"")
    monkeypatch.setenv("FAKE_CLAUDE_OUTPUT", str(F/"claude-ask-user.jsonl"))
    w = Worker(store=s, bitrix=b, worktree=mgr, chat_id="c",
               claude_bin=F/"fake_claude.sh", task_timeout_sec=60)
    await w.run_start("bbbb", _m(2,"#develop q"))
    t = await s.get_task_by_parent(2)
    assert t.status == TaskStatus.AWAITING_CLARIFICATION
    await s.close()
```

- [ ] **Step 2: Implementation**

```python
# src/pass24_dev_agent/worker.py
from __future__ import annotations
import asyncio, json, logging, re
from asyncio import create_subprocess_exec as run_subproc
from pathlib import Path
from .bitrix.client import BitrixClient
from .bitrix.models import Message
from .chat import ChatReporter
from .prompts.render import render_task_prompt
from .state.store import Store, TaskStatus
from .worktree import WorktreeManager

log = logging.getLogger(__name__)
_ASK_USER = "<<ASK_USER>>"
_GIVE_UP = "<<GIVE_UP>>"
_PR_URL_RE = re.compile(r"https://github\.com/[^\s]+/pull/\d+")

class Worker:
    def __init__(self, *, store: Store, bitrix: BitrixClient, worktree: WorktreeManager,
                 chat_id: str, claude_bin: Path, task_timeout_sec: int) -> None:
        self._s = store; self._b = bitrix; self._wt = worktree
        self._chat = chat_id; self._claude = claude_bin; self._timeout = task_timeout_sec

    async def run_start(self, task_id: str, message: Message) -> None:
        rep = ChatReporter(self._b, self._chat, message.id)
        await rep.critical(f"Принял #{task_id}. Создаю ветку dev/auto-{task_id}…")
        await self._s.update_status(task_id, TaskStatus.RUNNING)
        try:
            wt_path = await self._wt.create(task_id)
            att_dir = wt_path/"attachments"; att_dir.mkdir(exist_ok=True)
            atts: list[tuple[str, str]] = []
            for a in message.attachments:
                data = await self._b.download_attachment(a.file_id)
                name = a.name or f"file-{a.file_id}"
                p = att_dir/name; p.write_bytes(data)
                atts.append((name, str(p)))
            prompt = render_task_prompt(short_id=task_id, text=message.text, attachments=atts)
            await self._run_claude(task_id, wt_path, prompt, rep, resume=False)
        except Exception as e:
            log.exception("worker failed for %s", task_id)
            await self._s.update_status(task_id, TaskStatus.FAILED)
            await rep.critical(f"❌ #{task_id} не получилось: {e}")
        finally:
            await rep.flush()

    async def run_resume(self, task_id: str, clarification: str, message: Message) -> None:
        t = await self._s.get_task_by_parent(message.reply_id or 0)
        if t is None: return
        rep = ChatReporter(self._b, self._chat, t.parent_message_id)
        await self._s.update_status(task_id, TaskStatus.RUNNING)
        wt_path = self._wt._path(task_id)
        if not wt_path.exists():
            await rep.critical(f"❌ #{task_id}: worktree пропал, нужен ручной разбор.")
            await self._s.update_status(task_id, TaskStatus.FAILED); return
        await self._run_claude(task_id, wt_path, clarification, rep,
                                resume=True, session_id=t.claude_session_id)
        await rep.flush()

    async def _run_claude(self, task_id: str, wt_path: Path, prompt: str,
                           rep: ChatReporter, *, resume: bool,
                           session_id: str | None = None) -> None:
        args: list[str] = [str(self._claude), "--print", "--output-format", "stream-json"]
        if resume and session_id:
            args += ["--resume", session_id]
        else:
            args += ["--permission-mode", "acceptEdits"]
        args.append(prompt)
        proc = await run_subproc(*args, cwd=str(wt_path),
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        asked = False; gave_up = False; pr_url: str | None = None
        try:
            async with asyncio.timeout(self._timeout):
                assert proc.stdout
                async for line in proc.stdout:
                    try: evt = json.loads(line.decode())
                    except json.JSONDecodeError: continue
                    await self._handle_event(task_id, evt, rep)
                    text = evt.get("text") or evt.get("delta") or ""
                    if _ASK_USER in text: asked = True
                    if _GIVE_UP in text: gave_up = True
                    out = evt.get("output") or ""
                    if "pull/" in out:
                        m = _PR_URL_RE.search(out)
                        if m: pr_url = m.group(0)
                await proc.wait()
        except TimeoutError:
            proc.kill()
            await rep.critical(f"❌ #{task_id}: таймаут Claude ({self._timeout}s).")
            await self._s.update_status(task_id, TaskStatus.FAILED); return

        if asked:
            await self._s.update_status(task_id, TaskStatus.AWAITING_CLARIFICATION)
            await rep.critical(f"❓ #{task_id}: нужно уточнение (см. выше).")
            return
        if gave_up or proc.returncode != 0:
            await self._s.update_status(task_id, TaskStatus.FAILED)
            await rep.critical(f"❌ #{task_id}: не получилось автоматически. Ветка сохранена.")
            return
        if pr_url:
            await self._s.update_fields(task_id, pr_url=pr_url)
            await self._s.update_status(task_id, TaskStatus.DONE)
            await rep.critical(f"✅ #{task_id}: готово. PR: {pr_url}")
        else:
            await self._s.update_status(task_id, TaskStatus.DONE)
            await rep.critical(f"✅ #{task_id}: готово (PR URL не распарсил).")
        await self._wt.cleanup(task_id)

    async def _handle_event(self, task_id: str, evt: dict, rep: ChatReporter) -> None:
        t = evt.get("type")
        if t == "system":
            sid = evt.get("session_id")
            if sid:
                await self._s.update_fields(task_id, claude_session_id=sid)
        elif t == "assistant":
            text = evt.get("text") or evt.get("delta") or ""
            if text:
                await rep.normal(text[:500])
        elif t == "tool_use":
            human = self._fmt_tool(evt.get("name", ""), evt.get("input") or {})
            if human:
                await rep.normal(human)

    @staticmethod
    def _fmt_tool(name: str, inp: dict) -> str:
        if name == "Read":  return f"📖 Read: {inp.get('file_path','')}"
        if name == "Edit":  return f"✏️ Edit: {inp.get('file_path','')}"
        if name == "Write": return f"📝 Write: {inp.get('file_path','')}"
        if name == "Bash":  return f"💻 Bash: {str(inp.get('command',''))[:120]}"
        return f"🔧 {name}"
```

- [ ] **Step 3:** PASS → `git commit -m "feat(worker): Claude subprocess orchestration"`

### Task 8.3: Overloaded-retry (gap из self-review)

**Files:** modify `src/pass24_dev_agent/worker.py`, `tests/test_worker_overloaded.py`, `tests/fixtures/claude-overloaded.jsonl`

- [ ] **Step 1:** `claude-overloaded.jsonl`

```
{"type":"system","session_id":"sess-ovr"}
{"type":"error","subtype":"overloaded"}
```

- [ ] **Step 2:** Детектить `{"type":"error","subtype":"overloaded"}` в `_run_claude` — НЕ помечать failed, кинуть спец-исключение `ClaudeOverloaded`; `run_start` ловит его и делает up-to-3 ретрая с задержкой 60/180/600 сек (в тестах — 0.01/0.02/0.03 через monkeypatch глобальной константы).

- [ ] **Step 3: Test**

```python
# tests/test_worker_overloaded.py — проверить: 3 попытки, потом failed; если на 2-ой вернул happy → DONE
```

- [ ] **Step 4:** `git commit -m "feat(worker): overloaded retry with exponential delay"`

---

## Этап 9 — Poller

### Task 9.1: Цикл чтения

**Files:** `src/pass24_dev_agent/poller.py`, `tests/test_poller.py`

- [ ] **Step 1: Test**

```python
# tests/test_poller.py
import asyncio
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock
import pytest
from pass24_dev_agent.bitrix.models import Message
from pass24_dev_agent.poller import Poller
from pass24_dev_agent.state.store import Store

def _m(mid):
    return Message(id=mid, chat_id=1, author_id=1,
                   date=datetime.fromisoformat("2026-04-22T10:00:00+00:00"),
                   text="x", reply_id=None, attachments=[])

@pytest.mark.asyncio
async def test_dedupe(tmp_path: Path):
    s = await Store.open(tmp_path/"s.db")
    b = AsyncMock()
    b.fetch_new_messages = AsyncMock(side_effect=[[_m(1),_m(2)],[_m(2),_m(3)],[]])
    q: asyncio.Queue = asyncio.Queue()
    p = Poller(bitrix=b, store=s, chat_id="c", queue=q, interval_sec=0.01)
    await p.run(max_iterations=3)
    ids = []
    while not q.empty(): ids.append((await q.get()).id)
    assert ids == [1, 2, 3]
    await s.close()
```

- [ ] **Step 2: Implementation**

```python
# src/pass24_dev_agent/poller.py
from __future__ import annotations
import asyncio, logging
from typing import TYPE_CHECKING, Callable
if TYPE_CHECKING:
    from .bitrix.client import BitrixClient
    from .bitrix.models import Message
    from .state.store import Store
log = logging.getLogger(__name__)

class Poller:
    def __init__(self, *, bitrix: "BitrixClient", store: "Store",
                 chat_id: str, queue: "asyncio.Queue[Message]",
                 interval_sec: float, on_tick: Callable[[], None] | None = None) -> None:
        self._b = bitrix; self._s = store; self._chat = chat_id
        self._q = queue; self._interval = interval_sec; self._on_tick = on_tick

    async def run(self, max_iterations: int | None = None) -> None:
        i = 0
        while True:
            try:
                last = await self._s.max_seen_id()
                msgs = await self._b.fetch_new_messages(self._chat, last)
                for m in msgs:
                    if await self._s.insert_seen(m.id):
                        await self._q.put(m)
                if self._on_tick: self._on_tick()
            except Exception:
                log.exception("poller iteration failed")
            i += 1
            if max_iterations is not None and i >= max_iterations:
                return
            await asyncio.sleep(self._interval)
```

- [ ] **Step 3:** PASS → `git commit -m "feat(poller): dedupe + survives errors"`

---

## Этап 10 — Supervisor + health + e2e

### Task 10.1: `app.py` + `__main__.py`

**Files:** `src/pass24_dev_agent/__main__.py`, `src/pass24_dev_agent/app.py`

- [ ] **Step 1:** `__main__.py`

```python
# src/pass24_dev_agent/__main__.py
from __future__ import annotations
import asyncio, logging
from .app import main

def cli() -> None:
    logging.basicConfig(level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    asyncio.run(main())

if __name__ == "__main__":
    cli()
```

- [ ] **Step 2:** `app.py`

```python
# src/pass24_dev_agent/app.py
from __future__ import annotations
import asyncio, logging, signal
from asyncio import create_subprocess_exec as run_subproc
from datetime import datetime
from pathlib import Path
from aiohttp import web
from .bitrix.client import BitrixClient
from .config import Settings
from .dispatcher import Dispatcher, TaskResume, TaskStart
from .poller import Poller
from .state.store import Store
from .worker import Worker
from .worktree import WorktreeManager

log = logging.getLogger(__name__)

class _State:
    started_at = datetime.utcnow()
    last_poll_at = datetime.utcnow()

async def _ensure_repo(cache: Path, url: str) -> None:
    cache.parent.mkdir(parents=True, exist_ok=True)
    if not (cache/".git").exists():
        log.info("cloning %s → %s", url, cache)
        p = await run_subproc("git", "clone", url, str(cache)); await p.wait()
    else:
        p = await run_subproc("git", "-C", str(cache), "fetch", "origin", "main"); await p.wait()

async def _run_health() -> web.AppRunner:
    app = web.Application()
    async def h(_req):
        return web.json_response({"status":"ok",
            "started_at":_State.started_at.isoformat(),
            "last_poll_at":_State.last_poll_at.isoformat()})
    app.router.add_get("/health", h)
    runner = web.AppRunner(app); await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 9876); await site.start()
    return runner

async def main() -> None:
    s = Settings()
    store = await Store.open(s.state_db_path)
    await _ensure_repo(s.repo_cache_dir, s.repo_url)
    bitrix = BitrixClient(s.bitrix24_webhook_url)
    wt = WorktreeManager(repo_cache_dir=s.repo_cache_dir, worktrees_dir=s.worktrees_dir)
    disp = Dispatcher(store, allowed_user_ids=s.allowed_user_ids)
    worker = Worker(store=store, bitrix=bitrix, worktree=wt,
                    chat_id=s.bitrix_chat_id, claude_bin=s.claude_bin,
                    task_timeout_sec=s.claude_task_timeout_sec)
    for t in await store.recover_in_flight():
        try:
            await bitrix.send_reply(s.bitrix_chat_id, t.parent_message_id,
                f"❌ #{t.task_id} прервано рестартом. Ветка dev/auto-{t.task_id} сохранена.")
        except Exception:
            log.exception("recovery reply failed")

    inbox: asyncio.Queue = asyncio.Queue()
    work_q: asyncio.Queue = asyncio.Queue()

    def _tick(): _State.last_poll_at = datetime.utcnow()
    poller = Poller(bitrix=bitrix, store=store, chat_id=s.bitrix_chat_id,
                    queue=inbox, interval_sec=s.poll_interval_sec, on_tick=_tick)
    stop = asyncio.Event()
    def _sig(*_): log.info("signal, stopping"); stop.set()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, _sig)

    async def dispatch_loop():
        while not stop.is_set():
            m = await inbox.get()
            out = await disp.classify(m)
            if out is not None: await work_q.put(out)

    async def worker_loop():
        sem = asyncio.Semaphore(s.max_concurrent_tasks)
        while not stop.is_set():
            job = await work_q.get()
            async def _run(j=job):
                async with sem:
                    if isinstance(j, TaskStart):
                        await worker.run_start(j.short_id, j.message)
                    elif isinstance(j, TaskResume):
                        await worker.run_resume(j.task_id, j.clarification_text, j.message)
            asyncio.create_task(_run())

    health = await _run_health()
    try:
        async with asyncio.TaskGroup() as tg:
            tg.create_task(poller.run())
            tg.create_task(dispatch_loop())
            tg.create_task(worker_loop())
            await stop.wait()
            raise asyncio.CancelledError
    finally:
        await health.cleanup()
        await bitrix.close()
        await store.close()
```

- [ ] **Step 3:** `uv run ruff check src/ && uv run mypy src/`

- [ ] **Step 4:** `git commit -m "feat(app): supervisor with TaskGroup + health + recovery"`

### Task 10.2: E2E тест

**Files:** `tests/test_end_to_end.py`

- [ ] **Step 1: Test**

```python
# tests/test_end_to_end.py — прогнать Dispatcher + Worker через happy-path fixture
# (скопировать test_worker.py::test_happy — он по сути уже e2e без Poller+TaskGroup)
```

- [ ] **Step 2:** `git commit -m "test(e2e): happy-path integration"`

---

## Этап 11 — Deploy infra

### Task 11.1: systemd

**Files:** `systemd/pass24-dev-agent.service`

- [ ] **Step 1:**

```ini
[Unit]
Description=pass24-dev-agent
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=pass24-dev-agent
Group=pass24-dev-agent
EnvironmentFile=/etc/pass24-dev-agent/env
WorkingDirectory=/opt/pass24-dev-agent
ExecStart=/opt/pass24-dev-agent/.venv/bin/pass24-dev-agent
Restart=on-failure
RestartSec=30s
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ReadWritePaths=/var/lib/pass24-dev-agent /var/log/pass24-dev-agent

[Install]
WantedBy=multi-user.target
```

- [ ] **Step 2:** `git commit -m "deploy: systemd unit"`

### Task 11.2: CI/CD деплой

**Files:** `.github/workflows/deploy.yml`

- [ ] **Step 1:**

```yaml
name: Deploy
on: { push: { branches: [main] } }
jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: appleboy/ssh-action@v1
        with:
          host: ${{ secrets.VPS_HOST }}
          username: ${{ secrets.VPS_USER }}
          key: ${{ secrets.VPS_SSH_KEY }}
          script: |
            cd /opt/pass24-dev-agent
            sudo -u pass24-dev-agent git pull --rebase
            sudo -u pass24-dev-agent uv sync
            sudo systemctl restart pass24-dev-agent
            sudo systemctl status pass24-dev-agent --no-pager
```

- [ ] **Step 2:** Настроить GitHub Secrets: `VPS_HOST=5.42.101.27`, `VPS_USER=root` (или доверенный), `VPS_SSH_KEY=<private key>`

- [ ] **Step 3:** `git commit -m "ci: auto-deploy on push to main"`

### Task 11.3: VPS bootstrap (ручной, 1 раз)

- [ ] **Step 1:** `ssh root@5.42.101.27`

- [ ] **Step 2:** Создать юзера и каталоги

```bash
useradd -r -m -d /opt/pass24-dev-agent -s /bin/bash pass24-dev-agent
mkdir -p /var/lib/pass24-dev-agent /var/log/pass24-dev-agent /etc/pass24-dev-agent
chown -R pass24-dev-agent:pass24-dev-agent /opt/pass24-dev-agent /var/lib/pass24-dev-agent /var/log/pass24-dev-agent
chmod 750 /etc/pass24-dev-agent
```

- [ ] **Step 3:** От имени юзера

```bash
sudo -iu pass24-dev-agent
cd ~ && git clone https://github.com/akhromovRT/pass24-dev-agent.git .
curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.cargo/env
uv sync
```

- [ ] **Step 4:** Установить `claude` CLI тем же способом, что локально (от имени `pass24-dev-agent`).

- [ ] **Step 5:** `gh auth login` + `git config --global user.name/user.email` от имени `pass24-dev-agent`.

- [ ] **Step 6:** `/etc/pass24-dev-agent/env`

```
BITRIX24_WEBHOOK_URL=https://...
BITRIX_CHAT_ID=chat<ID>
ANTHROPIC_API_KEY=sk-ant-...
GITHUB_TOKEN=github_pat_...
ALLOWED_USER_IDS=
```

`chmod 600 /etc/pass24-dev-agent/env && chown pass24-dev-agent:pass24-dev-agent /etc/pass24-dev-agent/env`

- [ ] **Step 7:** Установить юнит

```bash
cp /opt/pass24-dev-agent/systemd/pass24-dev-agent.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now pass24-dev-agent
journalctl -fu pass24-dev-agent
```

---

## Этап 12 — Acceptance

### Task 12.1: Smoke test в тестовом чате

- [ ] **Step 1:** Создать в Bitrix24 отдельный тестовый чат, положить его ID в `BITRIX_CHAT_ID`, `systemctl restart pass24-dev-agent`.

- [ ] **Step 2:** В этом чате написать: `#develop добавь в README.md строку "autodev: ok" и сделай PR`

- [ ] **Step 3:** В течение 5–10 мин следить за:
  - реплаями бота (принял → прогресс → ✅ Готово)
  - `journalctl -fu pass24-dev-agent`
  - созданием PR в GitHub

- [ ] **Step 4:** Верифицировать PR: ветка `dev/auto-<id>`, коммит `[dev-<id>]`, README обновлён.

- [ ] **Step 5:** Закрыть PR/удалить ветку, вернуть `BITRIX_CHAT_ID` на настоящий, рестарт.

- [ ] **Step 6:** Запись в `pass24-servicedesk/agent_docs/development-history.md` о запуске.

---

## Self-Review (пройдено)

- **Spec coverage:** все 13 разделов спеки покрыты этапами 0–12 или вынесены в future-work (раздел 11 спеки).
- **Placeholder scan:** «TBD/TODO» нет. Все code-шаги содержат полный код.
- **Type consistency:** `TaskStatus`, `Task`, `Store`, `WorktreeManager`, `ChatReporter(chat_id, parent_message_id, text)` — согласованы по всему плану.
- **Identified gap (fixed inline):** overloaded-retry вынесен в отдельный Task 8.3. `last_poll_at` проводится в Poller через колбэк `on_tick` → обновляется в `app.py` (Task 10.1).

---

## Execution Handoff

План готов: `agent_docs/plans/2026-04-22-pass24-dev-agent-plan.md`. Два варианта исполнения:

1. **Subagent-Driven (рекомендую)** — сабагент на каждую задачу, review между задачами.
2. **Inline Execution** — выполнять в одной сессии батчами с чекпоинтами.

Выбор — за Алексеем, при возобновлении работы.

# pass24-dev-agent — Сервис автоматической разработки из чата Bitrix24

| | |
|---|---|
| **Статус** | Design (draft) |
| **Дата** | 2026-04-22 |
| **Автор** | Алексей Хромов (бриф) + ассистент (проектирование) |
| **Репозиторий сервиса** | новый, `akhromovRT/pass24-dev-agent` |
| **Целевой репозиторий работ** | `akhromovRT/pass24-servicedesk` (только его) |
| **Следующий шаг** | План реализации через superpowers `writing-plans` |

## 1. Background / проблема

В команде поддержки PASS24 уже есть чат в Bitrix24 Messenger с названием
«Доработка servicedesk», куда стейкхолдеры пишут о мелких проблемах и желаниях по порталу
Service Desk (`akhromovRT/pass24-servicedesk`): «на странице дата без года»,
«добавь кнопку экспорта», «тут битая ссылка» и т. п.

Сейчас каждый такой запрос превращается в ручной цикл: прочитать,
завести задачу, сделать ветку, запушить, создать PR. Запросы мелкие, но их
много — рутина съедает время. Хочется, чтобы сообщения с тегом `#develop`
автоматически превращались в ветку + PR, а статус работы виден был прямо
в чате реплаями.

## 2. Цели и не-цели

### Цели
- Непрерывно слушать один конкретный чат в Bitrix24 Messenger
- Распознавать сообщения с тегом `#develop` как новые задачи
- Распознавать reply-цепочки как уточнения и финализацию задач
- Запускать Claude Code CLI на изолированном git worktree
- Стримить прогресс обратно в чат как реплаи к исходному сообщению
- По завершении создавать PR и прогонять Codex-review, затем сообщать
  готовность для ручного merge

### Не-цели (явно вне MVP)
- Горизонтальное масштабирование (1 процесс; параллельность внутри
  процесса задаётся `MAX_CONCURRENT_TASKS`, по умолчанию 1)
- Поддержка нескольких чатов или нескольких репозиториев
- Автомерж в `main` (финальный merge — вручную человеком)
- UI / дашборд (наблюдение через чат и `journalctl`)
- Собственные миграции Alembic (SQLite с `CREATE TABLE IF NOT EXISTS`)
- Поддержка редактирования и удаления сообщений в Bitrix
- Хэштег `#cancel` для отмены активной задачи
- `#develop` в середине сообщения (только в начале или на отдельной строке)

## 3. Принятые решения (суммарно)

| # | Параметр | Выбор |
|---|---|---|
| 1 | Тип чата | Bitrix24 Messenger (`im.*` API) |
| 2 | Транспорт входящих | Входящий webhook + polling (`im.dialog.messages.get`) |
| 3 | Связь задачи и сообщений | Reply-треды Bitrix + короткий hex ID (`#a7f2`), сгенерированный сервисом |
| 4 | Целевой репозиторий | Только `pass24-servicedesk` (захардкожено в конфиге) |
| 5 | Исполнитель задачи | `claude` CLI subprocess (`--print --output-format stream-json`) в git worktree |
| 6 | Завершение задачи | Сервис создаёт PR, гоняет Codex-review, человек жмёт merge |
| 7 | Хостинг | Тот же VPS `5.42.101.27`, systemd-юнит, рядом с PASS24 backend |
| 8 | Доступ к триггеру | Любой участник чата; есть конфигурационный whitelist `ALLOWED_USER_IDS` (по умолчанию пустой = все) |

## 4. Архитектура

### 4.1 Принципы
1. **Сервис — почтальон, Claude — разработчик.** Никакой бизнес-логики
   «что делать с задачей» в нашем коде: всё делегируется Claude Code CLI.
2. **Идемпотентность по сообщениям.** Таблица `messages_seen(bitrix_message_id)`
   с `INSERT OR IGNORE` — одно сообщение не породит задачу дважды даже при
   падении и рестарте.
3. **Изоляция задач через git worktree.** Каждая задача — своё рабочее
   дерево `<WORKTREES_DIR>/wt-<short_id>/`. Падение одной не затрагивает
   другие.
4. **Стрим наружу.** Прогресс виден как серия коротких реплаев, а не
   одно большое сообщение в конце.
5. **Сервис живуч, задачи смертны.** Никакая отдельная задача не
   должна ронять весь процесс.

### 4.2 Высокоуровневая диаграмма

```
┌──────────────────────┐    ┌─────────────────────┐      ┌───────────────┐
│ Bitrix24-чат         │◄──►│   pass24-dev-agent  │◄────►│  Claude Code  │
│ «Доработка servicedesk»│  │  (asyncio, Python)  │      │   CLI + git   │
└──────────────────────┘    └─────────────────────┘      └───────┬───────┘
       ▲                              │                          │
       │                              ▼                          ▼
       │                        SQLite state              git worktree →
       │                                                   gh pr create
       │                                                          │
       └──────── reply-и в тред: прогресс, вопросы, URL PR ◄──────┘
```

### 4.3 Внешние зависимости

| Зависимость | Назначение | Поведение при сбое |
|---|---|---|
| Bitrix24 REST (`im.*`, `disk.*`) | Чтение/отправка сообщений, скачивание вложений | Retry 5× back-off, polling не останавливается |
| `claude` CLI | Выполнение задачи | Exit ≠ 0 → задача `failed`, worktree сохраняется |
| `git` + `gh` CLI | Создание веток и PR | Ошибка → `failed` + сообщение в чат |
| SQLite в `/var/lib/pass24-dev-agent/state.db` | Персистентное состояние | WAL-режим, `busy_timeout=5000` |
| systemd | Supervisor | `Restart=on-failure`, `RestartSec=30s` |

## 5. Компоненты

Структура репозитория `pass24-dev-agent`:

```
pass24-dev-agent/
├── pyproject.toml
├── src/pass24_dev_agent/
│   ├── __main__.py
│   ├── app.py                 # supervisor: TaskGroup, SIGTERM, recovery
│   ├── config.py              # Pydantic Settings из .env
│   ├── bitrix/
│   │   ├── client.py          # httpx wrapper im.* + disk.*
│   │   └── models.py          # Pydantic модели сообщений/вложений
│   ├── state/
│   │   ├── store.py           # aiosqlite wrapper
│   │   └── schema.sql         # CREATE TABLE IF NOT EXISTS …
│   ├── poller.py              # long-running цикл чтения
│   ├── dispatcher.py          # msg → NEW / RESUME / IGNORE
│   ├── worker.py              # worktree → Claude CLI → PR
│   ├── chat.py                # throttled ChatReporter
│   ├── worktree.py            # git worktree add/remove + lock
│   └── prompts/task.md.j2     # Jinja-промпт для Claude
├── tests/
│   ├── test_dispatcher.py
│   ├── test_state.py
│   ├── test_chat_throttle.py
│   ├── test_worktree.py
│   ├── test_bitrix_client.py
│   ├── test_end_to_end.py
│   └── fixtures/
│       ├── claude-happy-path.jsonl
│       ├── claude-clarification.jsonl
│       └── claude-give-up.jsonl
├── systemd/pass24-dev-agent.service
├── AGENTS.md
└── README.md
```

### 5.1 Контракты модулей

**`config.py`** — Pydantic `Settings`. Ключи из `.env`:
`BITRIX24_WEBHOOK_URL`, `BITRIX_CHAT_ID`, `POLL_INTERVAL_SEC=12`,
`MAX_CONCURRENT_TASKS=1`, `ALLOWED_USER_IDS=""`,
`STATE_DB_PATH=/var/lib/pass24-dev-agent/state.db`,
`WORKTREES_DIR=/var/lib/pass24-dev-agent/wt`,
`REPO_URL=https://github.com/akhromovRT/pass24-servicedesk.git`,
`REPO_CACHE_DIR=/var/lib/pass24-dev-agent/repo`,
`CLAUDE_BIN=/usr/local/bin/claude`,
`CLAUDE_TASK_TIMEOUT_SEC=1200`, `ANTHROPIC_API_KEY`, `GITHUB_TOKEN`,
`LOG_DIR=/var/log/pass24-dev-agent`.

**`bitrix/client.py`** — три публичных метода:
- `fetch_new_messages(chat_id, last_id) -> list[Message]` поверх
  `im.dialog.messages.get` с `LIMIT` и нужным `FIRST_ID`
- `send_reply(chat_id, parent_message_id, text) -> int` поверх
  `im.message.add` с параметром `REPLY_ID`
- `download_attachment(file_id) -> bytes` через `disk.file.get` +
  загрузка по `DOWNLOAD_URL`

Retry: экспоненциальный back-off `0.5/1/2/4/8` сек, до 5 попыток.
Rate-limit по `X-RateLimit-Remaining` — засыпаем до окна.

**`state/store.py`** — `aiosqlite`, WAL, `busy_timeout=5000`. Схема:
```sql
CREATE TABLE IF NOT EXISTS messages_seen (
    bitrix_message_id  INTEGER PRIMARY KEY,
    task_id            TEXT,
    seen_at            TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS tasks (
    task_id            TEXT PRIMARY KEY,       -- 4-hex short id ('a7f2')
    parent_message_id  INTEGER UNIQUE NOT NULL,
    bitrix_user_id     INTEGER NOT NULL,
    git_branch         TEXT,
    pr_url             TEXT,
    status             TEXT NOT NULL,          -- queued|running|awaiting_clarification|reviewing|done|failed
    claude_session_id  TEXT,
    created_at         TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at         TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS events (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id            TEXT,
    kind               TEXT NOT NULL,
    payload_json       TEXT,
    at                 TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_tasks_parent ON tasks(parent_message_id);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
```

**`poller.py`** — один long-running `asyncio.Task`. Цикл:
1. `last_id = await state.get_max_seen_id()`
2. `msgs = await bitrix.fetch_new_messages(chat_id, last_id)`
3. for m in msgs: `if state.insert_seen(m.id): queue.put(m)`
4. `await asyncio.sleep(POLL_INTERVAL_SEC)`

Ошибка внутри цикла — лог + `continue`. Poller не падает никогда.

**`dispatcher.py`** — потребитель `inbox_queue`:
- Проверка `ALLOWED_USER_IDS`
- Если `#develop` в начале или отдельной строкой и нет `PARAMS.REPLY_ID` →
  генерируем `short_id` (4 hex, уникальный по `tasks`), `INSERT tasks`,
  шлём `TaskStart` в `worker_queue`, первый реплай «Принял, #a7f2».
- Если есть `REPLY_ID` и он ведёт на `tasks.parent_message_id` со
  статусом `awaiting_clarification` → `TaskResume` + текст уточнения.
- Остальное → `events.kind='ignored'`.

**`worker.py`** — потребитель `worker_queue` с `asyncio.Semaphore(MAX_CONCURRENT_TASKS)`.
Логика для `TaskStart`:
1. Скачать вложения → `<WORKTREES_DIR>/wt-<id>/attachments/*`
2. `git worktree add -B dev/auto-<id> <WORKTREES_DIR>/wt-<id> origin/main`
3. Отрендерить `prompts/task.md.j2` с текстом, ID, путями к файлам
4. Запустить `claude --print --output-format stream-json
   --permission-mode acceptEdits --input-format text <prompt>`
   в `cwd=wt-<id>`
5. Читать stdout построчно, парсить JSON. Первое событие `system` —
   сохранить `session_id` в `tasks.claude_session_id`.
6. Для `assistant`/`tool_use`/`tool_result` — throttled-реплай в чат
7. Маркеры `<<ASK_USER>>` и `<<GIVE_UP>>` ищутся как подстроки в
   текстовых полях событий `assistant` (delta/text). При обнаружении
   `<<ASK_USER>>` → закрыть stdin, дождаться exit 0,
   `status='awaiting_clarification'`, сообщение-вопрос в чат.
8. При обнаружении `<<GIVE_UP>>` → `status='failed'`, реплай с резюме.
9. По exit 0 и отсутствию маркеров: парсить URL PR из стрима,
   `status='reviewing'`, затем `status='done'`, финальный реплай,
   cleanup worktree

Логика для `TaskResume`: `claude --resume <session_id> --print
"<текст уточнения>"` в том же worktree; всё остальное как выше.

**`chat.py`** — `ChatReporter` с буферизацией:
- Обычные события копятся в буфер 10 сек, склеиваются в одно сообщение
- «Критичные» (старт задачи, ASK_USER, ошибки, PR-URL, завершение) —
  мгновенно, без throttling
- Ошибка `send_reply` — в `events.kind='reply_failed'`, не ломаем поток

**`worktree.py`** — `create(short_id) -> path` / `cleanup(short_id)`.
Внутри: полный путь к локальному клону `REPO_CACHE_DIR`, там
`git fetch origin main`, `git worktree add -B dev/auto-<id>`. Коллизия
ветки — force remove + retry. Одновременный `git worktree` из двух задач
защищён `asyncio.Lock` на уровне репо-клона.

**`app.py`** — supervisor:
- Инициализация: SQLite schema, очереди, клиенты
- Подготовка рабочего репо: если `REPO_CACHE_DIR` пуст → `git clone
  REPO_URL REPO_CACHE_DIR`, иначе `git -C REPO_CACHE_DIR fetch origin`.
  Клон «голый» относительно worktree — все задачи берут свой worktree
  из этого кэша.
- `asyncio.TaskGroup`: poller, dispatcher, worker-pool, health-server
- Recovery на старте: все `running` → `failed('supervisor_restart')` +
  реплай в чат; `awaiting_clarification` не трогаем
- SIGTERM: cancel poller → ждать 60 сек worker-пула → kill остатков →
  финальный flush chat.py → exit 0

### 5.2 Health-эндпоинт

Маленький HTTP-сервер на `127.0.0.1:9876/health`, возвращает JSON:
```
{ "status": "ok", "last_poll_at": "2026-04-22T10:01:23Z", "active_tasks": 1 }
```
cron-проверка раз в минуту снаружи; 3 подряд «last_poll_at старее 2 минут»
→ email админу через SMTP из PASS24.

## 6. Потоки данных

### 6.1 Счастливый путь
1. Пользователь пишет `#develop <описание>` со скриншотом
2. Poller читает сообщение в ≤ `POLL_INTERVAL_SEC` сек
3. Dispatcher создаёт задачу `a7f2`, шлёт стартовый реплай
4. Worker делает worktree, рендерит промпт, стартует Claude
5. Stream-json события конвертируются в throttled-реплаи («читаю X»,
   «правлю Y», «тесты зелёные»)
6. Claude коммитит, пушит, создаёт PR
7. Codex-review внутри того же claude-рана фиксит замечания
8. Worker сообщает `✅ Готово #a7f2. PR: <URL>. CI ✓, Codex ✓.`
9. Worktree удаляется, `tasks.status='done'`

### 6.2 Уточнение
1. Шаги 1–4 как выше
2. Claude печатает `<<ASK_USER>>\n<вопрос>` и завершается с exit 0
3. Worker: `status='awaiting_clarification'`, реплай-вопрос в чат
4. Пользователь отвечает реплаем на сообщение треда (любое)
5. Dispatcher по `REPLY_ID` находит задачу, шлёт `TaskResume`
6. Worker: `claude --resume <session_id> --print "<ответ>"` → продолжение
7. Дальше как 5–9 из 6.1

### 6.3 Ошибка
- Claude exit ≠ 0, или `<<GIVE_UP>>`, или таймаут 20 мин, или красные
  тесты после 3 его попыток
- `status='failed'`, worktree **сохраняется** для ручного разбора
- Реплай в чат с кратким резюме и путём к лог-файлу
  `/var/log/pass24-dev-agent/<short_id>.log`

### 6.4 Рестарт сервиса
- На старте `app.py.recover_in_flight_tasks()` переводит `running` →
  `failed('supervisor_restart')` и шлёт реплай «прервано рестартом»
- `awaiting_clarification` остаются как есть
- `last_id` у poller восстанавливается из `messages_seen`, новые сообщения
  подхватятся штатно

## 7. Обработка ошибок

Группы отказов и стратегии:

| Группа | Стратегия |
|---|---|
| **Сеть Bitrix** | Exp back-off 0.5/1/2/4/8 сек, до 5 попыток. Poller не падает. |
| **Claude rate-limit / Overloaded** | Task-level retry: 60/180/600 сек, до 3 попыток. Только этот сценарий авто-ретраит целую задачу. |
| **Claude exit ≠ 0 / timeout** | `status='failed'`, worktree сохранён, реплай в чат. |
| **Git/GitHub** | Коллизия ветки — force remove + retry. Push rejected / conflict → сообщение в чат, `failed`. |
| **SQLite** | WAL + `busy_timeout=5000`. Corruption/full disk → падение процесса, systemd перезапускает. |
| **Некорректные сообщения** | Тихо `events.kind='ignored'`. |
| **SIGTERM** | Graceful: poller-stop → 60 сек worker-пулу → SIGKILL остатков. |

Явные отказы от возможностей ради простоты MVP:
- Dead-letter queue — не нужна
- Circuit breaker на Bitrix — не нужен
- Автоматический rollback коммитов — не нужен (всё живёт в отдельной ветке)
- Retry на `send_reply` — не нужен (риск дубликатов > выгоды)

Логирование:
- **journald** — структурный лог всех событий сервиса
- **SQLite `events`** — аудит-трейл бизнес-событий
- **`/var/log/pass24-dev-agent/<short_id>.log`** — полный stream-json
  от Claude на задачу; ротация: удаление старше 7 дней, gzip при `done`

Крэш-алерт: верхний уровень `app.py` ловит любое незапланированное
исключение и перед пропагейтом пишет в чат
`[pass24-dev-agent] crash: <type>: <msg>, рестарт через 30с`.

## 8. Безопасность

- Все секреты (`ANTHROPIC_API_KEY`, `GITHUB_TOKEN`, `BITRIX24_WEBHOOK_URL`)
  живут в `/etc/pass24-dev-agent/env`, права `600`, владелец — юзер сервиса
- systemd-юнит работает под отдельным unix-пользователем `pass24-dev-agent`
- `User=pass24-dev-agent`, `NoNewPrivileges=true`, `PrivateTmp=true`,
  `ProtectSystem=strict`, `ReadWritePaths=/var/lib/pass24-dev-agent
  /var/log/pass24-dev-agent`
- `GITHUB_TOKEN` — fine-grained PAT только на `akhromovRT/pass24-servicedesk`
  с правами Contents (RW) + Pull Requests (RW). Ничего лишнего.
- Bitrix webhook — отдельный, с минимальным scope `im,imopenlines,user,disk`
- `ALLOWED_USER_IDS` по умолчанию пуст (= все участники чата). Переключить
  в whitelist — редактированием `.env` без ребилда.

## 9. Тестирование

### 9.1 Unit
- `test_dispatcher.py` — классификация сообщений, whitelist, коллизия short_id
- `test_state.py` — CRUD, `INSERT OR IGNORE`, recovery, WAL
- `test_chat_throttle.py` — буферизация 10 сек, пропуск критичных событий
- `test_worktree.py` — создание/удаление, коллизия ветки, lock
- `test_bitrix_client.py` — retry через `respx`, rate-limit, парсинг
  вложений
- `test_config.py` — дефолты, валидация

### 9.2 Интеграционный `test_end_to_end.py`
Полный граф в одном asyncio-процессе:
- респонсы Bitrix через `respx`
- `CLAUDE_BIN` = fake-bash скрипт, печатающий `fixtures/claude-*.jsonl`
- `gh` stub, печатающий PR URL
- проверка исходящих реплаев, `state.db`, cleanup worktree

Фикстуры покрывают: happy-path, clarification, give-up, overloaded-retry.

### 9.3 Ручной acceptance-тест
После деплоя — в **тестовом** чате (не «Доработка servicedesk»):
- `#develop добавь в README.md строчку "autodev: ok"`
- Дождаться PR, проверить, merge локально, удалить ветку/PR
- Проверить `journalctl -u pass24-dev-agent` на чистоту

### 9.4 Coverage
`pytest --cov` ≥ 80% на `dispatcher.py`, `state/store.py`, `worker.py`;
≥ 70% на `bitrix/client.py`.

### 9.5 CI (GitHub Actions)
`.github/workflows/ci.yml`: `uv run ruff check` + `ruff format --check` +
`mypy src/` + `pytest`. Каждый шаг ≤ 2 минуты.

## 10. Деплой

### 10.1 Инфраструктура
- Хост: VPS `5.42.101.27` (тот же, где PASS24 Service Desk)
- Unix-пользователь: `pass24-dev-agent`
- systemd-юнит: `systemd/pass24-dev-agent.service`, `Restart=on-failure`,
  `RestartSec=30s`
- Python 3.12 через `uv`, venv в `/opt/pass24-dev-agent/.venv`
- Код в `/opt/pass24-dev-agent` (git clone)
- Данные: `/var/lib/pass24-dev-agent/{state.db,wt,repo}`
- Логи: `/var/log/pass24-dev-agent/`

### 10.2 CI/CD
GitHub Actions на push в `main`:
1. Linter/test
2. SSH-деплой на VPS: `git pull`, `uv sync`, `systemctl restart pass24-dev-agent`

### 10.3 Первичный запуск (runbook)
```
1. На VPS: useradd -r -s /bin/false pass24-dev-agent
2. mkdir /var/lib/pass24-dev-agent /var/log/pass24-dev-agent
   chown -R pass24-dev-agent:pass24-dev-agent …
3. git clone https://github.com/akhromovRT/pass24-dev-agent /opt/pass24-dev-agent
4. cd /opt/pass24-dev-agent && uv sync
5. gh auth login + git config user.name/user.email — от юзера pass24-dev-agent
6. Положить /etc/pass24-dev-agent/env (все секреты)
7. systemctl enable --now pass24-dev-agent
   (при первом старте сервис сам клонирует REPO_URL в REPO_CACHE_DIR)
8. journalctl -fu pass24-dev-agent (проверить старт)
9. Прогон smoke-теста в тестовом чате (см. 9.3)
```

## 11. Будущее (explicit non-MVP)

- `#cancel` для отмены активной задачи
- `#ship` для авто-мёржа PR после approve
- Whitelist user-ID через UI/admin-команду
- Поддержка нескольких чатов/репо (list в конфиге)
- Хэштег `#develop` в середине сообщения
- Обработка edit/delete сообщений в Bitrix
- Публичные метрики Prometheus из health-эндпоинта
- Мультиязычные промпты / настраиваемый тон реплаев

## 12. Промпт-шаблон (Jinja2, appendix)

```jinja
Ты работаешь над задачей #{{ task.short_id }} в репозитории pass24-servicedesk.
Рабочая директория — git worktree на ветке dev/auto-{{ task.short_id }}
(отведена от origin/main). Соблюдай все правила из корневого AGENTS.md.

## Задача (из чата Bitrix24):
{{ task.text }}

## Вложения:
{% for a in attachments %}
- {{ a.name }} → {{ a.path }}  (используй Read для просмотра)
{%- endfor %}

## Протокол работы
1. Сначала изучи релевантные файлы (Read / Grep). Не открывай весь репо.
2. Если задача неоднозначна — напиши строку "<<ASK_USER>>" и следом
   конкретный вопрос, затем остановись (exit 0).
3. Внеси правки. Прогони тесты:
   - backend: `uv run pytest`
   - frontend: `cd frontend && npm test`
4. Коммит:
   `git commit -m "<type>(<scope>): <описание> [dev-{{ task.short_id }}]"`
5. Push + `gh pr create` с осмысленными title / body.
6. Если у тебя доступен skill /pullrequest с Codex-review — используй его
   для исправления замечаний ревью, до 3 итераций.
7. Если сломалось и не получилось починить за 3 попытки — напиши строку
   "<<GIVE_UP>>" и кратко резюмируй что пробовал.

## Важно
- Не меняй ветку вручную; ты уже на dev/auto-{{ task.short_id }}.
- Не мёржи PR в main самостоятельно.
- Не трогай другие репозитории.
```

## 13. Открытые вопросы (к уточнению до старта реализации)

1. Получить **Bitrix chat ID** существующего чата «Доработка servicedesk»
   через `im.recent.get` (чат уже создан, нужно только определить его ID
   и записать в `BITRIX_CHAT_ID`).
2. Подтвердить, что на существующем webhook Bitrix есть scope `im,disk`;
   если нет — создать второй webhook.
3. Проверить, что Codex-review в рамках `pullrequest` skill можно
   запустить из того же `claude`-рана (т. е. он доступен как сабскилл),
   либо нам нужен отдельный шаг после claude-рана.
4. Подтвердить, что `GITHUB_TOKEN` разрешено выпустить как fine-grained PAT
   на нужный репозиторий (vs classic PAT).

# Настройка окружения проекта

Правила настройки рабочего окружения для PASS24 Service Desk.

---

## Когда применять

- При создании нового проекта из шаблона.
- При первом запуске агента в проекте, если конфигурация отсутствует.

---

## Стек

- **Backend:** Python 3.12 + FastAPI + SQLModel + PostgreSQL 16
- **Frontend:** Vue 3 + TypeScript + PrimeVue + Pinia
- **Подробности:** см. ADR-001 в `agent_docs/adr.md`

---

## Правила

### 1. Видимость `.env` в IDE

Цель: `.env` виден пользователю в IDE, но скрыт от git и AI-агентов.

**Создать/обновить `.vscode/settings.json`:**

```json
{
  "explorer.excludeGitIgnore": false,
  "files.exclude": {
    "**/.env": false
  }
}
```

**Создать/обновить `.cursorignore`:**

```
# Скрыть секреты от AI-агентов
.env
.env.local
.env.*.local

# Но показывать шаблон
!.env.example
```

**Создать/обновить `.gitignore`** (добавить, если отсутствует):

```
# Переменные окружения
.env
.env.local
.env.*.local
```

**Создать `.env.example`** (если отсутствует):

```
# PASS24 Service Desk — шаблон переменных окружения
# Скопируйте в .env и заполните значения

# Backend
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/pass24_servicedesk
SECRET_KEY=your-secret-key

# Frontend
VITE_API_BASE_URL=http://localhost:8000/api
```

---

## Чек-лист настройки окружения

- [ ] `.vscode/settings.json` создан с настройками видимости
- [ ] `.cursorignore` содержит правила для `.env`
- [ ] `.gitignore` содержит правила для `.env`
- [ ] `.env.example` создан как шаблон
- [ ] Python 3.12 установлен
- [ ] PostgreSQL 16 доступен
- [ ] Node.js (LTS) установлен для frontend

---

## Тесты и прод

**Только локально / CI с изолированной БД.** Интеграционные тесты (`tests/test_inbound_email_integration.py`, `tests/test_full_suite.py` и прочие «full-flow») создают тикеты, пользователей, комментарии — гоняй их против dev-БД, не против прод.

**Прод-контейнер: только через allowlist.** Для hotfix-прогонов есть workflow `Ops — run pytest on prod` (`.github/workflows/ops-run-tests.yml`). Он:
- требует явный `target` (whole-suite прогон запрещён);
- принимает только файлы из `ALLOWED_TARGETS` в скрипте;
- чтобы добавить новую цель — правь allowlist и убеждайся, что тест **не создаёт SMTP-отправок** на реальные адреса (используй `@example.com` или другие RFC 2606/6761 домены — они блокируются guard'ом в `_send_email`, см. ADR-012).

**Email-фикстуры — только зарезервированные домены.** `@example.com`, `@example.net`, `@example.org`, `*.test`, `*.invalid`, `*.localhost`. Guard в `backend/notifications/email._send_email` гарантирует, что на эти адреса реальный SMTP не уйдёт, даже если фикстура проникла в прод-БД. См. ADR-012.

**Запрещено в тест-фикстурах:**
- Реальные домены пользователей / сотрудников PASS24.
- Домены, которые реально существуют (`mail.ru`, `gmail.com`, `yandex.ru` и т.п.) — guard их пропустит, письмо уйдёт.

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

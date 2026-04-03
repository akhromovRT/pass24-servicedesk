# PASS24 Service Desk

Help Desk портал для пользователей СКУД-системы [PASS24.online](https://pass24.online) — система тикетов и база знаний.

## Что это

Веб-портал технической поддержки, где пользователи PASS24 (жители ЖК, администраторы УК) могут:
- Создавать заявки в техподдержку и отслеживать их статус
- Искать ответы в базе знаний (FAQ, инструкции)
- Отправлять заявки по email на support@pass24online.ru

## Технический стек

- **Backend:** Python 3.12, FastAPI, SQLModel, PostgreSQL 16
- **Frontend:** Vue 3 + TypeScript + PrimeVue 4 (Aura)
- **Auth:** JWT + bcrypt, RBAC (4 роли)
- **Email:** SMTP/IMAP (smtp.timeweb.ru) — уведомления + приём заявок
- **Деплой:** Docker (multi-stage), GitHub Actions CI/CD

## Быстрый старт

### С Docker (рекомендуется)

```bash
docker compose up -d
# API: http://localhost:8000
# Swagger: http://localhost:8000/docs
```

### Без Docker

```bash
pip install -r requirements.txt
# Создать .env из .env.example, настроить DATABASE_URL
uvicorn backend.main:app --reload
```

## API endpoints (20)

| Модуль | Метод | Путь | Описание |
|--------|-------|------|----------|
| Auth | POST | /auth/register | Регистрация |
| Auth | POST | /auth/login | Вход (JWT) |
| Auth | GET | /auth/me | Текущий пользователь |
| Tickets | POST | /tickets/ | Создать тикет |
| Tickets | GET | /tickets/ | Список (пагинация, фильтры) |
| Tickets | GET | /tickets/{id} | Детали тикета |
| Tickets | POST | /tickets/{id}/status | Сменить статус (FSM) |
| Tickets | POST | /tickets/{id}/comments | Добавить комментарий |
| Tickets | DELETE | /tickets/{id} | Удалить (admin) |
| KB | GET | /knowledge/ | Список статей |
| KB | GET | /knowledge/search | Поиск |
| KB | GET | /knowledge/{slug} | Статья по slug |
| KB | POST | /knowledge/ | Создать статью |
| KB | PUT | /knowledge/{id} | Обновить статью |
| KB | DELETE | /knowledge/{id} | Удалить статью |
| System | GET | /health | Healthcheck |
| System | GET | /docs | Swagger UI |

## Email-интеграция

- **Исходящие:** уведомления при создании тикета, смене статуса, новом комментарии
- **Входящие:** письма на support@pass24online.ru автоматически создают тикеты
  - Достаточно информации → тикет + ответ-подтверждение
  - Недостаточно → ответ с запросом уточнений

## Структура проекта

```
backend/
├── main.py              # FastAPI app + email polling
├── config.py            # Настройки (.env)
├── database.py          # PostgreSQL async
├── auth/                # Аутентификация, RBAC
├── tickets/             # Тикеты, комментарии, FSM
├── knowledge/           # База знаний, поиск
└── notifications/       # Email: SMTP (out) + IMAP (in)
frontend/                # Vue 3 SPA (Vite + PrimeVue)
├── src/pages/           # Страницы (Login, Tickets, Knowledge)
├── src/stores/          # Pinia (auth, tickets, knowledge)
└── src/components/      # Переиспользуемые компоненты
tests/                   # Юнит-тесты (pytest)
```

## Документация

- `AGENTS.md` — правила работы и описание проекта
- `agent_docs/architecture.md` — архитектура, роли, компоненты, roadmap
- `agent_docs/adr.md` — архитектурные решения (ADR-001, ADR-002)
- `agent_docs/development-history.md` — история итераций

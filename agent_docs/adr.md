# ADR

## Записи

### [2026-03-04] ADR-001: Технологический стек проекта

#### Статус
Принято

#### Контекст
Необходимо выбрать технологический стек для Help Desk портала PASS24. Требования: веб-портал с системой тикетов, базой знаний, ролевой моделью, графиками аналитики. Раздельные frontend и backend.

#### Решение

| Компонент | Технология |
|-----------|-----------|
| Backend | Python 3.12 + FastAPI |
| ORM | SQLModel |
| БД | PostgreSQL 16 |
| Frontend | Vue 3 + TypeScript |
| UI-библиотека | PrimeVue |
| State management | Pinia |
| Графики | vue-echarts |
| Фоновые задачи | crontab + FastAPI BackgroundTasks |
| Redis | убран (не требуется) |

#### Обоснование
- **FastAPI + SQLModel** — высокая производительность, автодокументация API (Swagger/OpenAPI), SQLModel совмещает Pydantic-валидацию и SQLAlchemy ORM
- **Vue 3 + TypeScript** — Composition API, хорошая экосистема, лёгкость освоения
- **PrimeVue** — богатый набор enterprise-компонентов (таблицы, формы, меню), подходит для admin-панели и портала
- **Pinia** — официальный state manager для Vue 3, простой API
- **vue-echarts** — мощные интерактивные графики для аналитики и дашбордов
- **Без Redis** — на этапе MVP фоновые задачи покрываются FastAPI BackgroundTasks + crontab; Redis можно добавить позже при необходимости

#### Последствия
- (+) Единый язык (Python) на backend, быстрая итерация
- (+) Автоматическая документация API через FastAPI
- (+) PrimeVue даёт готовые enterprise-компоненты без написания с нуля
- (-) SQLModel менее зрелый, чем чистый SQLAlchemy — возможно потребуется fallback на SQLAlchemy для сложных запросов
- (-) Без Redis нет кэширования и очередей — может стать узким местом при росте нагрузки

#### Альтернативы рассмотрены
- **Next.js / React** — отвергнут в пользу Vue 3 (предпочтение команды)
- **Django** — отвергнут в пользу FastAPI (легковеснее, async из коробки, автодокументация)
- **Redis** — отложен до момента, когда BackgroundTasks перестанет справляться

---

### [2026-04-03] ADR-002: bcrypt напрямую вместо passlib

#### Статус
Принято

#### Контекст
При деплое на production (Python 3.12, bcrypt 5.x) модуль `passlib` вызывал ошибку `ValueError: password cannot be longer than 72 bytes`. Проект passlib не поддерживается (последний релиз — 2020), несовместим с bcrypt >= 4.1.

#### Решение
Заменить `passlib.context.CryptContext` на прямые вызовы `bcrypt.hashpw()` / `bcrypt.checkpw()`.

#### Обоснование
- passlib — unmaintained (последний коммит 2020, нет поддержки bcrypt 4+)
- Прямой bcrypt API — 2 функции, нет лишних абстракций
- bcrypt 5.x — актуальная библиотека, активно поддерживается

#### Последствия
- (+) Совместимость с bcrypt 5.x на Python 3.12
- (+) Убрана неподдерживаемая зависимость (passlib)
- (-) Нет автоматического выбора схемы хеширования (только bcrypt)

---

Шаблон записи: `agent_docs/templates/adr.md`

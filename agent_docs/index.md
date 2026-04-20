# Навигация по документам

Короткая навигация. Читать только релевантные файлы.

## Основные
- `agent_docs/architecture.md` — архитектура, роли, компоненты, стек (FastAPI + Vue 3); актуально при изменениях системы.
- `agent_docs/adr.md` — архитектурные решения (ADR-001: стек); использовать при важных решениях.
- `agent_docs/development-history.md` — журнал итераций; смотреть последнюю запись. Архив: `agent_docs/development-history-archive.md`.

## Планирование
- `agent_docs/roadmap.md` — roadmap v0.6–v0.9: проекты внедрения, approvals, Gantt, CRM, mobile.

## Правила и гайды
- `agent_docs/guides/support-operations.md` — **регламент работы менеджера поддержки** (обработка заявок, email, база знаний).
- `agent_docs/guides/implementation-projects.md` — **инструкция по проектам внедрения** (создание, управление, работа с клиентом).
- `agent_docs/guides/knowledge-base-manual.md` — **подробное руководство по базе знаний** для менеджеров: как устроена, как писать статьи, метрики, KPI.
- `agent_docs/guides/dod.md` — критерии завершённости (DoD): тесты, документация, линтинг.
- `agent_docs/guides/environment-setup.md` — настройка окружения (.env, .cursorignore, .vscode) + правила запуска тестов на проде и email-фикстур (ADR-012).
- `agent_docs/guides/logging.md` — логирование: Markdown-логи в `logs/run-%timestamp%/`.
- `agent_docs/guides/archiving-and-temp.md` — архивация и временные файлы.

## Шаблоны
- `agent_docs/templates/architecture.md`
- `agent_docs/templates/adr.md`
- `agent_docs/templates/development-history.md`

# Навигация по документам

Короткая навигация. Читать только релевантные файлы.

## Основные
- `agent_docs/architecture.md` — архитектура, роли, компоненты, стек (FastAPI + Vue 3); актуально при изменениях системы.
- `agent_docs/adr.md` — архитектурные решения (ADR-001: стек); использовать при важных решениях.
- `agent_docs/development-history.md` — журнал итераций; смотреть последнюю запись. Архив: `agent_docs/development-history-archive.md`.

## Планирование
- `agent_docs/roadmap.md` — roadmap v0.6–v0.9: проекты внедрения, approvals, Gantt, CRM, mobile.

## Спеки и планы
- `agent_docs/specs/2026-04-22-bitrix-dev-agent-design.md` — **дизайн** сервиса
  `pass24-dev-agent`: мониторинг чата Bitrix24 «Доработка servicedesk» →
  авто-разработка через Claude Code CLI → PR в pass24-servicedesk.
  Статус: approved, ожидает реализации.
- `agent_docs/plans/2026-04-22-pass24-dev-agent-plan.md` — **implementation
  plan** к той же спеке, 12 этапов в TDD-стиле. Статус: готов, реализация не
  начата. Раздел «Как возобновить работу» в начале файла.

## Правила и гайды
- `docs/embed-ai-chat-guide.md` — **установка AI-помощника PASS24 на любой сайт** (loader+iframe, одна строка `<script>`). Инструкции для WordPress/Tilda/Webflow/Bitrix/React/Vue, параметры, диагностика, FAQ. См. ADR-014.
- `agent_docs/telegram-bot-user-guide.md` — **user guide по Telegram-боту** (`@PASS24ROBOT`): привязка, wizard, ответы, CSAT, KB, AI, PM workflow, настройки, FAQ. Скрины в `agent_docs/screenshots/telegram/`.
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

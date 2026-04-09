# Roadmap: PASS24 Service Desk

## v0.6 — Проекты внедрения (завершён 2026-04-05)

- Модуль `backend/projects/`: 7 таблиц, CRUD, FSM, phases/tasks, documents, team, comments, events
- 4 шаблона проектов (ЖК 10 фаз, БЦ 9, Камеры 5, Большая стройка 12)
- Опциональная связь тикетов с проектами
- Email-уведомления: создание, статус, фаза, milestone
- Frontend: список проектов, детали с 7 табами, создание, Timeline
- v0.6.1: UX polish — autocomplete, doc upload, inline tasks, DatePicker, edit dialog

## v0.7 — CRM-интеграция + Компании (завершён 2026-04-06)

- **Модель Customer**: ИНН (уникальный), название, bitrix24_company_id, адрес, контакты
- **Bitrix24 sync**: компании + контакты по ИНН из `crm.requisite.list`
- **DaData**: поиск по ИНН и названию из ФНС, автосоздание компании
- **CustomerSelect.vue**: двухуровневый autocomplete (свои → DaData)
- **Связь User↔Customer↔Ticket**: автоматическая привязка
- **Password reset**: сброс пароля через email-ссылку

## v0.8 — Agent Interface Redesign + Approvals & Risk Management (завершён 2026-04-09)

**Phase 1 (2026-04-07):** Редизайн интерфейса агента
- 2-колоночный layout тикета (чат + сайдбар), 18 компонентов + 4 composables
- 7 статусов FSM (+on_hold, +engineer_visit), автостатус new→in_progress
- Email threading (body tag + In-Reply-To headers), inline-вложения
- Назначение по умолчанию, вкладка «Открытые» по умолчанию

**Phase 2 (2026-04-09):** Approvals, Risks, Templates, Analytics
- Approvals workflow: утверждение фаз клиентом (property_manager), email-уведомления
- Risk tracker: severity/probability/impact, mitigation plan, CRUD
- Template editor: шаблоны в БД (auto-seed из Python-констант), CRUD для админов
- Project analytics: метрики (duration, on-time rate, by type/status, risks, approvals)

## v0.9 — Gantt & Real-time (планируется)

- **Gantt chart**: горизонтальная визуализация с зависимостями между фазами/задачами
  - Библиотека: frappe-gantt или кастомный SVG
  - Drag-n-drop сроков, критический путь
- **CRM webhook**: Bitrix24 сделки → автосоздание проектов
  - Webhook при закрытии сделки → POST /projects с данными из CRM
- **WebSocket real-time**: обновления проекта в реальном времени
  - При изменении статуса задачи/фазы → push всем участникам
  - Замена polling → WS для NotificationBell и ProjectDetailPage
- **Push-уведомления / PWA**: Service Workers, offline-доступ к dashboard проекта

## v1.0 — Scale & Optimization (будущее)

- **Multi-tenant isolation**: разделение данных по организациям
- **Budget tracking**: бюджет проекта, затраты по фазам, BOM
- **Project cloning**: клонирование завершённого проекта (структура + задачи)
- **Import/Export**: экспорт проекта в PDF/Excel, импорт из MS Project/Gantt
- **Mobile app**: нативное приложение для PM и монтажников (статусы задач в поле)
- **SLA для фаз**: дедлайны фаз с автоматическими предупреждениями (аналог SLA watcher для тикетов)

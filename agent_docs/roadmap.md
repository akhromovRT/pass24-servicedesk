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

## v0.8 — Approvals & Risk Management (планируется)

**Цель:** дать клиенту возможность подписывать этапы и формализовать управление рисками.

- **Approvals workflow**: клиент (property_manager) подписывает завершение фазы / deliverable
  - Модель `ProjectApproval` (approvable_type, approvable_id, status: pending/approved/rejected, feedback)
  - UI: кнопка "Утвердить" на PhaseCard для PM, badge "Ожидает подтверждения"
  - Email-уведомление при запросе approval
- **Risk tracker**: управление рисками проекта
  - Модель `ProjectRisk` (severity: red/yellow/green, probability, impact, mitigation_plan, owner_id, status)
  - UI: панель рисков на ProjectDetailPage, создание/закрытие
- **Редактор шаблонов в админке**: CRUD шаблонов проектов через SettingsPage
  - Миграция: таблица `project_templates` в БД (замена Python-констант)
  - UI: админ создаёт/редактирует/клонирует шаблоны
- **Project analytics dashboard**: метрики для PASS24 staff
  - Time-to-Go-Live по типам проектов, On-Time Delivery Rate, Health Score
  - ECharts графики на отдельной странице /projects/analytics

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

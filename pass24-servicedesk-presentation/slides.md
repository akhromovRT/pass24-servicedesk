---
theme: default
title: "PASS24 Service Desk — Единая точка входа"
colorSchema: dark
fonts:
  sans: Bricolage Grotesque
  serif: Crimson Pro
  mono: JetBrains Mono
transition: fade
aspectRatio: 16/9
layout: none
---

<div style="position:absolute;inset:0;z-index:0;overflow:hidden;">
  <div style="position:absolute;top:50%;left:50%;width:600px;height:600px;transform:translate(-50%,-50%);background:radial-gradient(circle,rgba(34,211,238,0.12) 0%,transparent 70%);border-radius:50%;"></div>
</div>
<div style="position:absolute;inset:0;z-index:1;display:flex;flex-direction:column;justify-content:center;align-items:center;padding:48px 80px;text-align:center;">
  <h1 style="font-size:3.5em;font-weight:800;color:#e2e8f0;margin:0;line-height:1.1;">PASS24 Service Desk</h1>
  <div style="width:60px;height:3px;background:#22d3ee;border-radius:2px;margin:20px auto;"></div>
  <p style="font-size:1.3em;color:#94a3b8;margin:0;">Единая точка входа для коммуникации с клиентами</p>
  <p style="position:absolute;bottom:40px;font-size:0.9em;color:#22d3ee;">support.pass24pro.ru</p>
</div>

<style>
.slidev-layout { padding: 0 !important; overflow: hidden; }
</style>

---
layout: default
---

<div style="margin-bottom:8px;display:flex;align-items:center;gap:8px;">
  <span style="font-size:0.75em;font-weight:700;letter-spacing:0.1em;color:#22d3ee;text-transform:uppercase;">ПРОБЛЕМА</span>
</div>

## Фрагментация каналов и контекста

<div style="display:flex;flex-direction:column;gap:14px;margin-top:24px;">
  <div style="display:flex;align-items:center;gap:16px;background:#162036;border-radius:10px;padding:18px 24px;">
    <Icon name="mail" style="font-size:1.5em;color:#22d3ee;" />
    <span style="color:#e2e8f0;font-size:1.05em;">59% email + 30% Telegram — каналы разрознены</span>
  </div>
  <div style="display:flex;align-items:center;gap:16px;background:#162036;border-radius:10px;padding:18px 24px;">
    <Icon name="alert" style="font-size:1.5em;color:#f59e0b;" />
    <span style="color:#e2e8f0;font-size:1.05em;">82% заявок в категории «Другое» — нет классификации</span>
  </div>
  <div style="display:flex;align-items:center;gap:16px;background:#162036;border-radius:10px;padding:18px 24px;">
    <Icon name="chart" style="font-size:1.5em;color:#22d3ee;" />
    <span style="color:#e2e8f0;font-size:1.05em;">Ни SLA, ни аналитики — руководство не видит картину</span>
  </div>
</div>

---
layout: none
---

<div style="position:absolute;inset:0;z-index:0;overflow:hidden;">
  <div style="position:absolute;inset:0;background:#0f1729;"></div>
  <div style="position:absolute;top:50%;left:50%;width:500px;height:500px;transform:translate(-50%,-50%);background:radial-gradient(circle,rgba(34,211,238,0.08) 0%,transparent 70%);border-radius:50%;"></div>
</div>
<div style="position:absolute;inset:0;z-index:1;display:flex;flex-direction:column;justify-content:center;align-items:center;padding:48px 80px;text-align:center;">
  <h1 style="font-size:3em;font-weight:800;color:#e2e8f0;margin:0;line-height:1.15;">Омниканальность как фундамент</h1>
  <div style="width:60px;height:3px;background:#22d3ee;border-radius:2px;margin:16px auto;"></div>
  <p style="font-size:1.2em;color:#94a3b8;margin:0;">Один клиент → любой канал → один тикет</p>
</div>

<style>
.slidev-layout { padding: 0 !important; overflow: hidden; }
</style>

---
layout: default
---

<div style="margin-bottom:8px;display:flex;align-items:center;gap:8px;">
  <span style="font-size:0.75em;font-weight:700;letter-spacing:0.1em;color:#22d3ee;text-transform:uppercase;">КАНАЛЫ</span>
</div>

## Пять точек входа — одна система

<div style="display:flex;flex-direction:column;gap:12px;margin-top:20px;">
  <div style="display:flex;align-items:center;gap:16px;background:#162036;border-radius:10px;padding:14px 24px;">
    <Icon name="globe" style="font-size:1.4em;color:#22d3ee;" />
    <span style="color:#e2e8f0;"><strong>Web-портал</strong> — форма + live KB-suggestions</span>
  </div>
  <div style="display:flex;align-items:center;gap:16px;background:#162036;border-radius:10px;padding:14px 24px;">
    <Icon name="mail" style="font-size:1.4em;color:#22d3ee;" />
    <span style="color:#e2e8f0;"><strong>Email</strong> — IMAP каждые 60с, автосоздание тикета</span>
  </div>
  <div style="display:flex;align-items:center;gap:16px;background:#162036;border-radius:10px;padding:14px 24px;">
    <Icon name="telegram" style="font-size:1.4em;color:#22d3ee;" />
    <span style="color:#e2e8f0;"><strong>Telegram</strong> — @PASS24bot, webhook</span>
  </div>
  <div style="display:flex;align-items:center;gap:16px;background:#162036;border-radius:10px;padding:14px 24px;">
    <Icon name="api" style="font-size:1.4em;color:#22d3ee;" />
    <span style="color:#e2e8f0;"><strong>API</strong> — Admin24-SaaS для УК</span>
  </div>
  <div style="display:flex;align-items:center;gap:16px;background:#162036;border-radius:10px;padding:14px 24px;">
    <Icon name="phone" style="font-size:1.4em;color:#22d3ee;" />
    <span style="color:#e2e8f0;"><strong>Телефон</strong> — фиксация через портал</span>
  </div>
</div>

---
layout: default
---

<div style="margin-bottom:8px;display:flex;align-items:center;gap:8px;">
  <span style="font-size:0.75em;font-weight:700;letter-spacing:0.1em;color:#22d3ee;text-transform:uppercase;">РОЛИ</span>
</div>

## Четыре стороны процесса

<div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-top:20px;">
  <div style="background:#162036;border-radius:10px;padding:20px 24px;">
    <div style="display:flex;align-items:center;gap:10px;margin-bottom:8px;">
      <Icon name="users" style="font-size:1.3em;color:#22d3ee;" />
      <strong style="color:#e2e8f0;">Резидент</strong>
      <span style="font-size:0.8em;color:#94a3b8;font-family:'JetBrains Mono';">resident</span>
    </div>
    <p style="margin:0;color:#94a3b8;font-size:0.95em;">Создает заявки, видит свои, оценивает CSAT</p>
  </div>
  <div style="background:#162036;border-radius:10px;padding:20px 24px;">
    <div style="display:flex;align-items:center;gap:10px;margin-bottom:8px;">
      <Icon name="building" style="font-size:1.3em;color:#22d3ee;" />
      <strong style="color:#e2e8f0;">Администратор УК</strong>
      <span style="font-size:0.8em;color:#94a3b8;font-family:'JetBrains Mono';">property_manager</span>
    </div>
    <p style="margin:0;color:#94a3b8;font-size:0.95em;">Заявки объекта, эскалация</p>
  </div>
  <div style="background:#162036;border-radius:10px;padding:20px 24px;">
    <div style="display:flex;align-items:center;gap:10px;margin-bottom:8px;">
      <Icon name="headset" style="font-size:1.3em;color:#22d3ee;" />
      <strong style="color:#e2e8f0;">Агент поддержки</strong>
      <span style="font-size:0.8em;color:#94a3b8;font-family:'JetBrains Mono';">support_agent</span>
    </div>
    <p style="margin:0;color:#94a3b8;font-size:0.95em;">Обработка заявок, база знаний</p>
  </div>
  <div style="background:#162036;border-radius:10px;padding:20px 24px;">
    <div style="display:flex;align-items:center;gap:10px;margin-bottom:8px;">
      <Icon name="settings" style="font-size:1.3em;color:#22d3ee;" />
      <strong style="color:#e2e8f0;">Администратор</strong>
      <span style="font-size:0.8em;color:#94a3b8;font-family:'JetBrains Mono';">admin</span>
    </div>
    <p style="margin:0;color:#94a3b8;font-size:0.95em;">Аналитика, SLA, настройки</p>
  </div>
</div>

---
layout: default
---

<div style="margin-bottom:8px;display:flex;align-items:center;gap:8px;">
  <span style="font-size:0.75em;font-weight:700;letter-spacing:0.1em;color:#22d3ee;text-transform:uppercase;">ВЗАИМОДЕЙСТВИЕ</span>
</div>

## Вклад каждой стороны в цикл заявки

<div style="display:flex;flex-direction:column;gap:10px;margin-top:14px;">
  <div style="display:flex;align-items:center;gap:16px;background:rgba(22,32,54,0.5);border-left:3px solid #22d3ee;border-radius:0 10px 10px 0;padding:12px 24px;">
    <Icon name="users" :size="22" color="#22d3ee" />
    <span style="color:#e2e8f0;"><strong>Житель</strong> <span style="color:#94a3b8;">→</span> источник заявки + оценка CSAT</span>
  </div>
  <div style="display:flex;align-items:center;gap:16px;background:rgba(22,32,54,0.6);border-left:3px solid #22d3ee;border-radius:0 10px 10px 0;padding:12px 24px;">
    <Icon name="building" :size="22" color="#22d3ee" />
    <span style="color:#e2e8f0;"><strong>УК</strong> <span style="color:#94a3b8;">→</span> фильтр по объекту + эскалация</span>
  </div>
  <div style="display:flex;align-items:center;gap:16px;background:rgba(22,32,54,0.7);border-left:3px solid #22d3ee;border-radius:0 10px 10px 0;padding:12px 24px;">
    <Icon name="headset" :size="22" color="#22d3ee" />
    <span style="color:#e2e8f0;"><strong>Команда PASS24</strong> <span style="color:#94a3b8;">→</span> диагностика, решение, БЗ</span>
  </div>
  <div style="display:flex;align-items:center;gap:16px;background:rgba(22,32,54,0.8);border-left:3px solid #22d3ee;border-radius:0 10px 10px 0;padding:12px 24px;">
    <Icon name="chart" :size="22" color="#22d3ee" />
    <span style="color:#e2e8f0;"><strong>Руководитель</strong> <span style="color:#94a3b8;">→</span> контроль SLA, Deflection Rate</span>
  </div>
</div>

---
layout: none
---

<div style="position:absolute;inset:0;z-index:0;overflow:hidden;">
  <div style="position:absolute;inset:0;background:#0a1420;"></div>
  <div style="position:absolute;top:50%;left:50%;width:500px;height:500px;transform:translate(-50%,-50%);background:radial-gradient(circle,rgba(34,211,238,0.06) 0%,transparent 70%);border-radius:50%;"></div>
</div>
<div style="position:absolute;inset:0;z-index:1;display:flex;flex-direction:column;justify-content:center;align-items:center;padding:48px 80px;text-align:center;">
  <h1 style="font-size:3em;font-weight:800;color:#e2e8f0;margin:0;line-height:1.15;">Жизненный цикл тикета</h1>
  <div style="width:60px;height:3px;background:#22d3ee;border-radius:2px;margin:16px auto;"></div>
  <p style="font-size:1.2em;color:#94a3b8;margin:0;">FSM + 5-осевая классификация + автопереходы</p>
</div>

<style>
.slidev-layout { padding: 0 !important; overflow: hidden; }
</style>

---
layout: default
---

<div style="margin-bottom:8px;display:flex;align-items:center;gap:8px;">
  <span style="font-size:0.75em;font-weight:700;letter-spacing:0.1em;color:#22d3ee;text-transform:uppercase;">SLA</span>
</div>

## Обещание клиенту и инструмент команды

<div style="text-align:center;margin:20px 0 16px;">
  <span style="font-size:3.5em;font-weight:800;color:#22d3ee;line-height:1;">30 мин</span>
  <p style="color:#94a3b8;margin:4px 0 0;font-size:1em;">минимальное время реакции (critical)</p>
</div>

<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-top:12px;">
  <div style="background:#162036;border-radius:10px;padding:14px 16px;text-align:center;">
    <div style="font-weight:700;color:#f87171;font-size:0.9em;margin-bottom:6px;">Critical</div>
    <div style="color:#e2e8f0;font-size:0.85em;">Реакция: 30м</div>
    <div style="color:#94a3b8;font-size:0.85em;">Решение: 4ч</div>
  </div>
  <div style="background:#162036;border-radius:10px;padding:14px 16px;text-align:center;">
    <div style="font-weight:700;color:#f59e0b;font-size:0.9em;margin-bottom:6px;">High</div>
    <div style="color:#e2e8f0;font-size:0.85em;">Реакция: 1ч</div>
    <div style="color:#94a3b8;font-size:0.85em;">Решение: 8ч</div>
  </div>
  <div style="background:#162036;border-radius:10px;padding:14px 16px;text-align:center;">
    <div style="font-weight:700;color:#22d3ee;font-size:0.9em;margin-bottom:6px;">Normal</div>
    <div style="color:#e2e8f0;font-size:0.85em;">Реакция: 4ч</div>
    <div style="color:#94a3b8;font-size:0.85em;">Решение: 24ч</div>
  </div>
  <div style="background:#162036;border-radius:10px;padding:14px 16px;text-align:center;">
    <div style="font-weight:700;color:#94a3b8;font-size:0.9em;margin-bottom:6px;">Low</div>
    <div style="color:#e2e8f0;font-size:0.85em;">Реакция: 8ч</div>
    <div style="color:#94a3b8;font-size:0.85em;">Решение: 48ч</div>
  </div>
</div>

<p style="text-align:center;color:#94a3b8;font-size:0.8em;margin-top:12px;">Рабочие часы: пн-пт 9:00-18:00 МСК</p>

---
layout: default
---

<div style="margin-bottom:8px;display:flex;align-items:center;gap:8px;">
  <span style="font-size:0.75em;font-weight:700;letter-spacing:0.1em;color:#22d3ee;text-transform:uppercase;">ИНСТРУМЕНТЫ</span>
</div>

## Рабочий стол агента поддержки

<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:16px;margin-top:24px;">
  <div style="background:#162036;border-radius:10px;padding:24px 20px;text-align:center;">
    <div style="display:flex;justify-content:center;align-items:center;margin-bottom:8px;">
      <Icon name="layers" style="font-size:1.8em;color:#22d3ee;" />
    </div>
    <div style="font-weight:700;color:#e2e8f0;margin-bottom:8px;">Операции</div>
    <p style="color:#94a3b8;margin:0;font-size:0.9em;">Назначение, bulk-actions, merge дубликатов</p>
  </div>
  <div style="background:#162036;border-radius:10px;padding:24px 20px;text-align:center;">
    <div style="display:flex;justify-content:center;align-items:center;margin-bottom:8px;">
      <Icon name="file-text" style="font-size:1.8em;color:#22d3ee;" />
    </div>
    <div style="font-weight:700;color:#e2e8f0;margin-bottom:8px;">Шаблоны</div>
    <p style="color:#94a3b8;margin:0;font-size:0.9em;">Ответы + макросы (1 кнопка = статус + коммент)</p>
  </div>
  <div style="background:#162036;border-radius:10px;padding:24px 20px;text-align:center;">
    <div style="display:flex;justify-content:center;align-items:center;margin-bottom:8px;">
      <Icon name="bell" style="font-size:1.8em;color:#22d3ee;" />
    </div>
    <div style="font-weight:700;color:#e2e8f0;margin-bottom:8px;">Мониторинг</div>
    <p style="color:#94a3b8;margin:0;font-size:0.9em;">Saved Views, дашборд, уведомления</p>
  </div>
</div>

---
layout: none
---

<div style="position:absolute;inset:0;z-index:0;overflow:hidden;">
  <div style="position:absolute;inset:0;background:#0b1120;"></div>
  <div style="position:absolute;top:45%;left:50%;width:700px;height:700px;transform:translate(-50%,-50%);background:radial-gradient(circle,rgba(34,211,238,0.08) 0%,transparent 60%);border-radius:50%;"></div>
</div>
<div style="position:absolute;inset:0;z-index:1;display:flex;flex-direction:column;justify-content:center;align-items:center;padding:48px 80px;text-align:center;">
  <span style="font-size:5em;font-weight:800;color:#22d3ee;line-height:1;">60-70%</span>
  <p style="font-size:1.3em;color:#e2e8f0;margin:16px 0 0;max-width:600px;">типичных обращений можно автоматизировать через базу знаний</p>
  <p style="font-size:0.9em;color:#94a3b8;margin:24px 0 0;">SMS-коды: 371 заявка/год <Icon name="arrow-right" style="color:#22d3ee;" /> потенциал снижения -38%</p>
</div>

<style>
.slidev-layout { padding: 0 !important; overflow: hidden; }
</style>

---
layout: default
---

<div style="margin-bottom:8px;display:flex;align-items:center;gap:8px;">
  <span style="font-size:0.75em;font-weight:700;letter-spacing:0.1em;color:#22d3ee;text-transform:uppercase;">СЦЕНАРИИ</span>
</div>

## Как БЗ перехватывает обращение

<div style="display:flex;flex-direction:column;gap:10px;margin-top:14px;">
  <div style="background:#162036;border-radius:10px;padding:14px 24px;">
    <div style="display:flex;align-items:center;gap:10px;margin-bottom:6px;">
      <Icon name="globe" :size="20" color="#22d3ee" />
      <strong style="color:#e2e8f0;">Web-форма</strong>
    </div>
    <p style="margin:0;color:#94a3b8;font-size:0.9em;">Клиент вводит проблему → live suggestions → находит ответ → <span style="color:#22d3ee;">заявка НЕ создаётся</span></p>
  </div>
  <div style="background:#162036;border-radius:10px;padding:14px 24px;">
    <div style="display:flex;align-items:center;gap:10px;margin-bottom:6px;">
      <Icon name="mail" :size="20" color="#22d3ee" />
      <strong style="color:#e2e8f0;">Email</strong>
    </div>
    <p style="margin:0;color:#94a3b8;font-size:0.9em;">Клиент пишет → авто-ответ с 3 ссылками → тикет параллельно → <span style="color:#22d3ee;">возможно не нуждается в обработке</span></p>
  </div>
  <div style="background:#162036;border-radius:10px;padding:14px 24px;">
    <div style="display:flex;align-items:center;gap:10px;margin-bottom:6px;">
      <Icon name="search" :size="20" color="#22d3ee" />
      <strong style="color:#e2e8f0;">Прямой поиск</strong>
    </div>
    <p style="margin:0;color:#94a3b8;font-size:0.9em;">Клиент на /knowledge → синонимы находят статью → <span style="color:#22d3ee;">помогла</span> или создаёт заявку</p>
  </div>
</div>

---
layout: default
---

<div style="margin-bottom:8px;display:flex;align-items:center;gap:8px;">
  <span style="font-size:0.75em;font-weight:700;letter-spacing:0.1em;color:#22d3ee;text-transform:uppercase;">АГЕНТ + БАЗА ЗНАНИЙ</span>
</div>

## Инструменты для работы с контентом

<div style="display:flex;flex-direction:column;gap:12px;margin-top:20px;">
  <div style="display:flex;align-items:center;gap:16px;background:#162036;border-radius:10px;padding:16px 24px;">
    <Icon name="link" style="font-size:1.4em;color:#22d3ee;" />
    <span style="color:#e2e8f0;">Панель «Связанные статьи» в тикете: <span style="color:#94a3b8;font-family:'JetBrains Mono';font-size:0.9em;">helped / related / created_from</span></span>
  </div>
  <div style="display:flex;align-items:center;gap:16px;background:#162036;border-radius:10px;padding:16px 24px;">
    <Icon name="search" style="font-size:1.4em;color:#f59e0b;" />
    <span style="color:#e2e8f0;">Синонимы — ключевая фишка: <span style="color:#f59e0b;">«смс не приходит»</span> = <span style="color:#f59e0b;">«нет кода»</span> = <span style="color:#f59e0b;">«не получаю SMS»</span></span>
  </div>
  <div style="display:flex;align-items:center;gap:16px;background:#162036;border-radius:10px;padding:16px 24px;">
    <Icon name="file-text" style="font-size:1.4em;color:#22d3ee;" />
    <span style="color:#e2e8f0;">Правило статьи: Проблема <Icon name="arrow-right" style="color:#94a3b8;" /> Шаги <Icon name="arrow-right" style="color:#94a3b8;" /> Эскалация</span>
  </div>
  <div style="display:flex;align-items:center;gap:16px;background:#162036;border-radius:10px;padding:16px 24px;">
    <Icon name="hash" style="font-size:1.4em;color:#22d3ee;" />
    <span style="color:#e2e8f0;">Обязательно: теги (2-4) + синонимы (3-6)</span>
  </div>
</div>

---
layout: none
---

<div style="position:absolute;inset:0;z-index:0;overflow:hidden;">
  <div style="position:absolute;inset:0;background:#111828;"></div>
  <div style="position:absolute;top:50%;left:50%;width:500px;height:500px;transform:translate(-50%,-50%);background:radial-gradient(circle,rgba(245,158,11,0.06) 0%,transparent 70%);border-radius:50%;"></div>
</div>
<div style="position:absolute;inset:0;z-index:1;display:flex;flex-direction:column;justify-content:center;align-items:center;padding:48px 80px;text-align:center;">
  <h1 style="font-size:3em;font-weight:800;color:#e2e8f0;margin:0;line-height:1.15;">Аналитика базы знаний</h1>
  <div style="width:60px;height:3px;background:#22d3ee;border-radius:2px;margin:16px auto;"></div>
  <p style="font-size:1.2em;color:#94a3b8;margin:0;">Дашборд /kb-analytics — данные в реальном времени</p>
</div>

<style>
.slidev-layout { padding: 0 !important; overflow: hidden; }
</style>

---
layout: default
---

<div style="margin-bottom:8px;display:flex;align-items:center;gap:8px;">
  <span style="font-size:0.75em;font-weight:700;letter-spacing:0.1em;color:#22d3ee;text-transform:uppercase;">KPI · МАЙ-ИЮЛЬ 2026</span>
</div>

## Целевые метрики

<div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-top:20px;">
  <div style="display:flex;flex-direction:column;gap:12px;">
    <div style="display:flex;align-items:center;gap:12px;background:#162036;border-radius:10px;padding:14px 20px;">
      <Icon name="trending-up" style="font-size:1.3em;color:#22d3ee;" />
      <div>
        <div style="color:#e2e8f0;font-weight:600;font-size:0.95em;">Deflection Rate</div>
        <div style="color:#94a3b8;font-size:0.85em;">0% <Icon name="arrow-right" style="color:#22d3ee;font-size:0.8em;" /> 15-25%</div>
      </div>
    </div>
    <div style="display:flex;align-items:center;gap:12px;background:#162036;border-radius:10px;padding:14px 20px;">
      <Icon name="target" style="font-size:1.3em;color:#22d3ee;" />
      <div>
        <div style="color:#e2e8f0;font-weight:600;font-size:0.95em;">Helpful Ratio</div>
        <div style="color:#94a3b8;font-size:0.85em;"><Icon name="arrow-right" style="color:#22d3ee;font-size:0.8em;" /> ≥60%</div>
      </div>
    </div>
    <div style="display:flex;align-items:center;gap:12px;background:#162036;border-radius:10px;padding:14px 20px;">
      <Icon name="chart" style="font-size:1.3em;color:#f59e0b;" />
      <div>
        <div style="color:#e2e8f0;font-weight:600;font-size:0.95em;">SMS-заявки</div>
        <div style="color:#94a3b8;font-size:0.85em;">371 <Icon name="arrow-right" style="color:#22d3ee;font-size:0.8em;" /> 230/год (-38%)</div>
      </div>
    </div>
  </div>
  <div style="display:flex;flex-direction:column;gap:12px;">
    <div style="display:flex;align-items:center;gap:12px;background:#162036;border-radius:10px;padding:14px 20px;">
      <Icon name="clock" style="font-size:1.3em;color:#22d3ee;" />
      <div>
        <div style="color:#e2e8f0;font-weight:600;font-size:0.95em;">Время обработки</div>
        <div style="color:#94a3b8;font-size:0.85em;">20-30 <Icon name="arrow-right" style="color:#22d3ee;font-size:0.8em;" /> 5-10 мин</div>
      </div>
    </div>
    <div style="display:flex;align-items:center;gap:12px;background:#162036;border-radius:10px;padding:14px 20px;">
      <Icon name="trending-up" style="font-size:1.3em;color:#22d3ee;" />
      <div>
        <div style="color:#e2e8f0;font-weight:600;font-size:0.95em;">Нагрузка</div>
        <div style="color:#94a3b8;font-size:0.85em;">100% <Icon name="arrow-right" style="color:#22d3ee;font-size:0.8em;" /> 30-40%</div>
      </div>
    </div>
    <div style="display:flex;align-items:center;gap:12px;background:#162036;border-radius:10px;padding:14px 20px;">
      <Icon name="zap" style="font-size:1.3em;color:#f59e0b;" />
      <div>
        <div style="color:#e2e8f0;font-weight:600;font-size:0.95em;">ROI</div>
        <div style="color:#94a3b8;font-size:0.85em;">50-70% рутинной работы</div>
      </div>
    </div>
  </div>
</div>

---
layout: none
---

<div style="position:absolute;inset:0;z-index:0;overflow:hidden;">
  <div style="position:absolute;inset:0;background:#0b1120;"></div>
  <div style="position:absolute;top:50%;left:50%;width:500px;height:500px;transform:translate(-50%,-50%);background:radial-gradient(circle,rgba(34,211,238,0.06) 0%,transparent 70%);border-radius:50%;"></div>
</div>
<div style="position:absolute;inset:0;z-index:1;display:flex;flex-direction:column;justify-content:center;align-items:center;padding:48px 80px;text-align:center;">
  <h1 style="font-size:2.6em;font-weight:800;color:#e2e8f0;margin:0;line-height:1.2;">Магия «одного тикета»</h1>
  <div style="width:60px;height:3px;background:#22d3ee;border-radius:2px;margin:16px auto;"></div>
  <p style="font-size:1.15em;color:#94a3b8;margin:0;max-width:700px;">Клиент отвечает на email — комментарий в тикете по тегу <span style="color:#22d3ee;font-family:'JetBrains Mono';">[PASS24-xxxxxxxx]</span></p>
  <p style="font-size:1em;color:#e2e8f0;margin:24px 0 0;max-width:600px;">Клиент не обязан заходить в портал — команда в одном интерфейсе</p>
</div>

<style>
.slidev-layout { padding: 0 !important; overflow: hidden; }
</style>

---
layout: default
---

<div style="margin-bottom:8px;display:flex;align-items:center;gap:8px;">
  <span style="font-size:0.75em;font-weight:700;letter-spacing:0.1em;color:#22d3ee;text-transform:uppercase;">РУКОВОДСТВО</span>
</div>

## Что видит руководство

<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:16px;margin-top:24px;">
  <div style="background:#162036;border-radius:10px;padding:24px 20px;text-align:center;">
    <div style="display:flex;justify-content:center;align-items:center;margin-bottom:8px;">
      <Icon name="clock" style="font-size:1.8em;color:#22d3ee;" />
    </div>
    <div style="font-weight:700;color:#e2e8f0;margin-bottom:8px;">SLA-дашборд</div>
    <p style="color:#94a3b8;margin:0;font-size:0.9em;">Реакция, решение, нарушения по приоритетам</p>
  </div>
  <div style="background:#162036;border-radius:10px;padding:24px 20px;text-align:center;">
    <div style="display:flex;justify-content:center;align-items:center;margin-bottom:8px;">
      <Icon name="chart" style="font-size:1.8em;color:#22d3ee;" />
    </div>
    <div style="font-weight:700;color:#e2e8f0;margin-bottom:8px;">CSAT + нагрузка</div>
    <p style="color:#94a3b8;margin:0;font-size:0.9em;">Удовлетворенность по агентам, тренды</p>
  </div>
  <div style="background:#162036;border-radius:10px;padding:24px 20px;text-align:center;">
    <div style="display:flex;justify-content:center;align-items:center;margin-bottom:8px;">
      <Icon name="book" style="font-size:1.8em;color:#22d3ee;" />
    </div>
    <div style="font-weight:700;color:#e2e8f0;margin-bottom:8px;">Аналитика БЗ</div>
    <p style="color:#94a3b8;margin:0;font-size:0.9em;">Deflection Rate, Helpful Ratio, топ статей</p>
  </div>
</div>

---
layout: none
---

<div style="position:absolute;inset:0;z-index:0;overflow:hidden;">
  <div style="position:absolute;inset:0;background:#0e1624;"></div>
  <div style="position:absolute;top:50%;left:50%;width:500px;height:500px;transform:translate(-50%,-50%);background:radial-gradient(circle,rgba(245,158,11,0.07) 0%,transparent 70%);border-radius:50%;"></div>
</div>
<div style="position:absolute;inset:0;z-index:1;display:flex;flex-direction:column;justify-content:center;align-items:center;padding:48px 80px;text-align:center;">
  <h1 style="font-size:3em;font-weight:800;color:#e2e8f0;margin:0;line-height:1.15;">Проекты внедрения</h1>
  <div style="width:60px;height:3px;background:#f59e0b;border-radius:2px;margin:16px auto;"></div>
  <p style="font-size:1.2em;color:#94a3b8;margin:0;">Не только поддержка — управление подключением новых клиентов</p>
</div>

<style>
.slidev-layout { padding: 0 !important; overflow: hidden; }
</style>

---
layout: default
---

<div style="margin-bottom:8px;display:flex;align-items:center;gap:8px;">
  <span style="font-size:0.75em;font-weight:700;letter-spacing:0.1em;color:#f59e0b;text-transform:uppercase;">ВНЕДРЕНИЕ</span>
</div>

## 4 шаблона проекта — от создания до сдачи

<div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:14px;">
  <div style="background:#162036;border-radius:10px;padding:14px 20px;">
    <div style="display:flex;align-items:center;gap:10px;margin-bottom:6px;">
      <Icon name="building" :size="20" color="#22d3ee" />
      <strong style="color:#e2e8f0;font-size:0.95em;">Стандартный ЖК</strong>
      <span style="color:#94a3b8;font-size:0.8em;">10 фаз · 10 нед</span>
    </div>
    <p style="margin:0;color:#94a3b8;font-size:0.85em;">КПП, подъезды, шлагбаумы, обучение УК</p>
  </div>
  <div style="background:#162036;border-radius:10px;padding:14px 20px;">
    <div style="display:flex;align-items:center;gap:10px;margin-bottom:6px;">
      <Icon name="building" :size="20" color="#f59e0b" />
      <strong style="color:#e2e8f0;font-size:0.95em;">Стандартный БЦ</strong>
      <span style="color:#94a3b8;font-size:0.8em;">9 фаз · 8 нед</span>
    </div>
    <p style="margin:0;color:#94a3b8;font-size:0.85em;">Турникеты, парковка, интеграция 1С/AD</p>
  </div>
  <div style="background:#162036;border-radius:10px;padding:14px 20px;">
    <div style="display:flex;align-items:center;gap:10px;margin-bottom:6px;">
      <Icon name="search" :size="20" color="#22d3ee" />
      <strong style="color:#e2e8f0;font-size:0.95em;">Только камеры</strong>
      <span style="color:#94a3b8;font-size:0.8em;">5 фаз · 4 нед</span>
    </div>
    <p style="margin:0;color:#94a3b8;font-size:0.85em;">pass24.auto — распознавание номеров</p>
  </div>
  <div style="background:#162036;border-radius:10px;padding:14px 20px;">
    <div style="display:flex;align-items:center;gap:10px;margin-bottom:6px;">
      <Icon name="layers" :size="20" color="#f59e0b" />
      <strong style="color:#e2e8f0;font-size:0.95em;">Большая стройка</strong>
      <span style="color:#94a3b8;font-size:0.8em;">12 фаз · 16 нед</span>
    </div>
    <p style="margin:0;color:#94a3b8;font-size:0.85em;">Тендер, очереди, усиленный контроль качества</p>
  </div>
</div>

<div style="display:flex;gap:20px;margin-top:14px;align-items:center;">
  <div style="display:flex;align-items:center;gap:6px;color:#94a3b8;font-size:0.85em;">
    <Icon name="zap" :size="16" color="#22d3ee" />
    FSM: черновик → планирование → в работе → завершён
  </div>
  <div style="display:flex;align-items:center;gap:6px;color:#94a3b8;font-size:0.85em;">
    <Icon name="target" :size="16" color="#f59e0b" />
    Milestone-трекинг + автодаты фаз
  </div>
</div>

---
layout: none
---

<div style="position:absolute;inset:0;z-index:0;overflow:hidden;">
  <div style="position:absolute;inset:0;background:#0b1120;"></div>
  <div style="position:absolute;top:50%;left:50%;width:600px;height:600px;transform:translate(-50%,-50%);background:radial-gradient(circle,rgba(34,211,238,0.05) 0%,transparent 70%);border-radius:50%;"></div>
</div>
<div style="position:absolute;inset:0;z-index:1;display:flex;flex-direction:column;justify-content:center;align-items:center;padding:48px 80px;text-align:center;">
  <h1 style="font-size:2.8em;font-weight:800;color:#e2e8f0;margin:0;line-height:1.15;">Почему это работает</h1>
  <div style="width:60px;height:3px;background:#22d3ee;border-radius:2px;margin:20px auto;"></div>
  <div style="display:flex;flex-direction:column;gap:24px;margin-top:16px;">
    <p style="color:#e2e8f0;font-size:1.15em;margin:0;"><Icon name="merge" style="color:#22d3ee;font-size:1.2em;" /> <strong>Единый контекст</strong> <span style="color:#94a3b8;">— один тикет = вся история</span></p>
    <p style="color:#e2e8f0;font-size:1.15em;margin:0;"><Icon name="zap" style="color:#22d3ee;font-size:1.2em;" /> <strong>Автоматизация</strong> <span style="color:#94a3b8;">— макросы, FSM, SLA-watcher</span></p>
    <p style="color:#e2e8f0;font-size:1.15em;margin:0;"><Icon name="check-circle" style="color:#22d3ee;font-size:1.2em;" /> <strong>Прозрачность</strong> <span style="color:#94a3b8;">— клиент видит статус, команда видит метрики</span></p>
    <p style="color:#e2e8f0;font-size:1.15em;margin:0;"><Icon name="layers" style="color:#f59e0b;font-size:1.2em;" /> <strong>Полный цикл</strong> <span style="color:#94a3b8;">— от внедрения до поддержки в одной системе</span></p>
  </div>
</div>

<style>
.slidev-layout { padding: 0 !important; overflow: hidden; }
</style>

---
layout: none
---

<div style="position:absolute;inset:0;z-index:0;overflow:hidden;">
  <div style="position:absolute;inset:0;background:#0b1120;"></div>
  <div style="position:absolute;top:50%;left:50%;width:800px;height:800px;transform:translate(-50%,-50%);background:radial-gradient(circle,rgba(34,211,238,0.1) 0%,transparent 60%);border-radius:50%;"></div>
</div>
<div style="position:absolute;inset:0;z-index:1;display:flex;flex-direction:column;justify-content:center;align-items:center;padding:48px 80px;text-align:center;">
  <h1 style="font-size:2.6em;font-weight:800;color:#e2e8f0;margin:0;line-height:1.15;">Service Desk — центральный хаб</h1>
  <div style="width:60px;height:3px;background:#22d3ee;border-radius:2px;margin:20px auto;"></div>
  <div style="display:flex;gap:24px;margin:20px 0;">
    <div style="background:rgba(239,68,68,0.1);border:1px solid rgba(239,68,68,0.3);border-radius:10px;padding:14px 24px;">
      <div style="color:#f87171;font-weight:700;font-size:0.85em;margin-bottom:6px;">ДО</div>
      <p style="color:#94a3b8;margin:0;font-size:0.9em;">82% «Другое», 0% автоматизации</p>
    </div>
    <div style="background:rgba(34,211,238,0.1);border:1px solid rgba(34,211,238,0.3);border-radius:10px;padding:14px 24px;">
      <div style="color:#22d3ee;font-weight:700;font-size:0.85em;margin-bottom:6px;">ПОСЛЕ</div>
      <p style="color:#e2e8f0;margin:0;font-size:0.9em;">Тикеты, БЗ, SLA, проекты внедрения</p>
    </div>
  </div>
  <p style="color:#94a3b8;font-size:1em;margin:12px 0 0;max-width:700px;">Поддержка клиентов <span style="color:#22d3ee;">+</span> подключение новых объектов <span style="color:#22d3ee;">+</span> база знаний <span style="color:#22d3ee;">=</span> <strong style="color:#e2e8f0;">единая точка входа</strong></p>
  <p style="color:#f59e0b;font-size:0.95em;margin:16px 0 0;max-width:650px;">Следующий шаг: наполнить БЗ по SMS-кодам → 15-25% Deflection к июлю</p>
  <p style="color:#e2e8f0;font-size:1.3em;font-weight:700;margin:28px 0 0;">Вопросы и обсуждение</p>
</div>

<style>
.slidev-layout { padding: 0 !important; overflow: hidden; }
</style>

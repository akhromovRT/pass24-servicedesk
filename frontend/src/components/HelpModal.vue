<script setup lang="ts">
import { ref, computed } from 'vue'
import Button from 'primevue/button'
import Dialog from 'primevue/dialog'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const visible = ref(false)

const isAdmin = computed(() => auth.user?.role === 'admin')
const canSeeProjects = computed(() =>
  ['property_manager', 'support_agent', 'admin'].includes(auth.user?.role || ''),
)
const isStaff = computed(() =>
  ['support_agent', 'admin'].includes(auth.user?.role || ''),
)

const title = computed(() =>
  isAdmin.value
    ? 'Руководство администратора'
    : 'Руководство агента поддержки'
)

function open() { visible.value = true }
function close() { visible.value = false }

defineExpose({ open, close })
</script>

<template>
  <Dialog
    v-model:visible="visible"
    modal
    :style="{ width: '90vw', maxWidth: '900px' }"
    :breakpoints="{ '960px': '95vw' }"
    class="help-dialog"
  >
    <template #header>
      <div class="help-header">
        <i :class="isAdmin ? 'pi pi-shield' : 'pi pi-book'" class="help-header-icon" />
        <span class="help-header-title">{{ title }}</span>
      </div>
    </template>

    <div class="help-content">
      <!-- Навигация -->
      <nav class="help-toc">
        <a href="#tickets">📋 Заявки</a>
        <a href="#workflow">🔄 Работа с заявкой</a>
        <a href="#comments">💬 Комментарии</a>
        <a href="#tools">🛠️ Шаблоны и макросы</a>
        <a href="#views">⭐ Сохранённые фильтры</a>
        <a href="#permanent-clients">🌟 Постоянные клиенты</a>
        <a href="#problems">🧩 Проблемы и инциденты</a>
        <a href="#kblinks">🔗 Связь со статьями БЗ</a>
        <a href="#notifications">🔔 Уведомления</a>
        <a href="#channels">📨 Каналы связи</a>
        <a href="#sla">⏱️ SLA</a>
        <a href="#dashboard">📊 Дашборд</a>
        <a href="#ai">🤖 AI-ассистент</a>
        <a v-if="canSeeProjects" href="#projects" class="projects-link">🏗️ Проекты внедрения</a>
        <template v-if="isAdmin">
          <a href="#users" class="admin-link">👥 Пользователи и роли</a>
          <a href="#kb-review" class="admin-link">📝 Ревью улучшений БЗ</a>
          <a href="#settings" class="admin-link">⚙️ SLA и настройки</a>
        </template>
      </nav>

      <section id="tickets" class="help-section">
        <h3>📋 Заявки</h3>
        <ul>
          <li><b>Список заявок</b> (вкладка «Мои заявки») — все тикеты с фильтрами и поиском</li>
          <li><b>Вкладки-фильтры</b>: Все / Открытые / Срочные / Просрочено / Ожидание ответа клиента / Закрытые</li>
          <li><b>Поиск</b> — работает по теме, описанию, email, имени клиента, объекту</li>
          <li><b>Множественный фильтр</b> — выбор нескольких статусов/категорий сразу</li>
          <li><b>Массовые действия</b> — выделите несколько тикетов галочками, затем смените статус/назначение/удалите (admin)</li>
          <li><b>Сохранённые фильтры</b> — свой набор фильтров можно сохранить как «view» (см. раздел ниже)</li>
          <li><b>Индикатор «Кто ответил последним»</b> — в строке активного тикета рядом с метаданными:
            <ul>
              <li><b style="color:#2563eb">Отв.: клиент</b> (синий) — последним в переписке написал клиент, мяч на нашей стороне.</li>
              <li><b style="color:#64748b">Отв.: оператор</b> (серый) — последний ответ наш, ждём клиента.</li>
              <li>Считаются только <b>публичные</b> комментарии; internal-заметки не влияют. Для resolved/closed индикатор не показывается.</li>
              <li>Удобно пробегать список и сразу видеть, где ждут вас (синие), а где клиента (серые).</li>
            </ul>
          </li>
          <li><b>Синяя точка (⬤)</b> слева от заголовка — новый, ещё не просмотренный ответ клиента. Пропадает, как только вы откроете тикет.</li>
        </ul>
      </section>

      <section id="workflow" class="help-section">
        <h3>🔄 Работа с заявкой</h3>
        <p><b>Статусы и переходы (FSM):</b></p>
        <pre class="help-code">NEW → IN_PROGRESS → WAITING_FOR_USER → RESOLVED → CLOSED</pre>
        <ul>
          <li><b>Взять себе</b> — кнопка в агентской панели, назначает тикет на вас</li>
          <li><b>Dropdown агентов</b> — переназначить любому коллеге</li>
          <li><b>Статусы меняются автоматически:</b>
            <ul>
              <li>Первый публичный ответ на <code>NEW</code> → статус <code>IN_PROGRESS</code></li>
              <li>Ваш следующий публичный ответ → статус <code>WAITING_FOR_USER</code></li>
              <li>Клиент отвечает (веб / email / Telegram) → статус <code>IN_PROGRESS</code></li>
            </ul>
          </li>
          <li><b>Пауза SLA по сообщению</b> (новое поведение):
            <ul>
              <li>Как только вы написали публичный ответ — таймер «Решение» автоматически на паузе, пока клиент не ответит. Статус менять <b>не обязательно</b>.</li>
              <li>Под прогресс-баром «Решение» появляется серый бейдж <code>⏸ SLA на паузе — ждём ответ клиента</code>.</li>
              <li>Как только клиент ответил — пауза снимается, таймер продолжает с учётом накопленной паузы.</li>
              <li>Internal-комментарии SLA не паузят — клиент их не видит.</li>
            </ul>
          </li>
          <li><b>Merge дубликатов</b> — при нахождении двух одинаковых заявок можно слить в одну</li>
          <li><b>Привязка к Problem</b> — если инцидентов много от одной причины, связать их с master-тикетом типа <code>problem</code></li>
          <li><b>Link to KB</b> — при закрытии отметить статьи БЗ, которые помогли решить (для Deflection Rate)</li>
        </ul>
      </section>

      <section id="comments" class="help-section">
        <h3>💬 Комментарии</h3>
        <ul>
          <li><b>Публичные</b> — клиент получает уведомление (email или Telegram)</li>
          <li><b>Внутренние</b> (чекбокс «Внутренний») — видны только агентам/админам, без уведомлений</li>
          <li><b>Вложения</b> — до 10 МБ, images/PDF/DOC/TXT, просмотр в модальном окне</li>
          <li><b>Шаблоны ответов</b> — клик по чипу вставляет текст в окно комментария</li>
        </ul>
      </section>

      <section id="tools" class="help-section">
        <h3>🛠️ Шаблоны и макросы</h3>
        <p><b>Шаблоны ответов</b> — готовые фразы для быстрого ответа клиенту. Отображаются над окном комментария в виде чипов.</p>
        <p><b>Макросы</b> — одна кнопка выполняет комбинацию действий:</p>
        <ul>
          <li>Изменить статус</li>
          <li>Добавить комментарий (публичный или внутренний)</li>
          <li>Назначить себя на тикет</li>
          <li>Выбрать группу (L1/L2/L3, billing и т.д.)</li>
        </ul>
        <p class="help-note">💡 Создавать шаблоны и макросы можно через API. Позже появится UI-менеджер.</p>
      </section>

      <section id="views" class="help-section">
        <h3>⭐ Сохранённые фильтры (Saved Views)</h3>
        <p>Набор фильтров, который можно сохранить и переиспользовать:</p>
        <ul>
          <li><b>Личные</b> — доступны только вам (например: «Мои срочные по PASS24.Key»)</li>
          <li><b>Общие</b> (<code>is_shared=true</code>) — видны всем агентам (например: «Просроченные по интеграциям»)</li>
          <li><b>Счётчик использования</b> (<code>usage_count</code>) — популярные фильтры отображаются выше</li>
          <li><b>Порядок сортировки</b> — можно задать вручную через <code>sort_order</code></li>
        </ul>
        <p class="help-note">💡 Создавайте отдельный view для каждого рабочего сценария: «Моя очередь», «Ждут ответа УК», «Критические по оборудованию».</p>
      </section>

      <section id="permanent-clients" class="help-section">
        <h3>🌟 Постоянные клиенты (Bitrix24)</h3>
        <p>Компании, помеченные в Bitrix24 как «Постоянный клиент» (поле <code>UF_CRM_PERMANENT_CLIENT</code>), ежедневно в 03:00 синхронизируются в справочник Service Desk. Заявки, привязанные к таким компаниям через <code>customer_id</code>, выделяются в интерфейсе.</p>
        <ul>
          <li><b>Бейдж «Постоянный»</b> (золотая звезда на жёлтом фоне) появляется в трёх местах:
            <ul>
              <li>В автокомплите при создании заявки (поле «Компания-клиент») — постоянные идут в начале списка.</li>
              <li>В правой панели карточки заявки, в блоке «Объект».</li>
              <li>В мета-строке списка заявок — рядом с автором и каналом.</li>
            </ul>
          </li>
          <li><b>Тогл «Постоянные клиенты / Все клиенты»</b> в шапке списка тикетов — фильтрует ленту до заявок только от постоянных клиентов. Удобно для утреннего обхода ключевых клиентов и отчётности.</li>
          <li><b>Привязка через ИНН</b>: ключ синхронизации — ИНН компании из <code>crm.requisite.list</code>. Компании без ИНН в Bitrix24 пропускаются (известное ограничение).</li>
          <li><b>Срочно нужно обновить</b>: после простановки чекбокса в Bitrix24 изменение появится после следующего ночного sync. Чтобы обновить раньше — попросите админа дёрнуть <code>POST /customers/sync</code>.</li>
        </ul>
        <p class="help-note">💡 Подробнее — в гиде <code>agent_docs/guides/permanent-clients.md</code>: API, FAQ, troubleshooting.</p>
      </section>

      <section id="problems" class="help-section">
        <h3>🧩 Проблемы и инциденты (Parent-Child)</h3>
        <p>Когда несколько клиентов пишут о <b>одной и той же проблеме</b> (например, «не работает домофон в ЖК Солнечный»):</p>
        <ul>
          <li><b>Создаётся один Problem-тикет</b> — с типом <code>problem</code>, это master (родитель)</li>
          <li><b>Инциденты</b> от клиентов привязываются к Problem через <code>parent_ticket_id</code></li>
          <li><b>Bulk-link</b> — можно одним действием привязать несколько инцидентов к одной проблеме</li>
          <li>При решении Problem — все привязанные инциденты автоматически получают уведомление</li>
        </ul>
        <p class="help-note">💡 Это позволяет агентам работать над корневой причиной, а не дублировать работу по каждому инциденту.</p>
      </section>

      <section id="kblinks" class="help-section">
        <h3>🔗 Связь со статьями БЗ</h3>
        <p>При закрытии тикета можно привязать статьи базы знаний, которые <b>помогли</b> его решить:</p>
        <ul>
          <li><code>helped</code> — статья решила проблему клиента (для Deflection Rate метрики)</li>
          <li><code>related</code> — статья связана по теме, но не решила проблему напрямую</li>
          <li><code>created_from</code> — новая статья создана на основе этого тикета</li>
        </ul>
        <p><b>Deflection Rate</b> — % тикетов, закрытых благодаря БЗ. Метрика показывает эффективность базы знаний и помогает находить пробелы в документации.</p>
      </section>

      <section id="notifications" class="help-section">
        <h3>🔔 Уведомления</h3>
        <ul>
          <li><b>Колокольчик</b> в шапке — счётчик тикетов с новыми ответами клиентов</li>
          <li><b>Polling</b> каждые 20 сек — обновление счётчика автоматом</li>
          <li><b>Звуковой сигнал</b> при появлении нового ответа</li>
          <li><b>Клик на уведомление</b> → переход в тикет, флаг «непрочитано» сбрасывается</li>
          <li><b>Email о нарушении SLA</b> — за 30 мин до дедлайна на support@pass24online.ru</li>
        </ul>
      </section>

      <section id="channels" class="help-section">
        <h3>📨 Каналы связи с клиентом</h3>
        <ul>
          <li><b>Веб-портал</b> — клиент создаёт заявку авторизованным или как гость</li>
          <li><b>Email</b> (<code>support@pass24online.ru</code>):
            <ul>
              <li>Новое письмо → тикет (с авто-классификацией)</li>
              <li>Ответ с тегом <code>[PASS24-xxxxxxxx]</code> в теме → комментарий к тикету</li>
              <li>Вложения из письма сохраняются в тикет</li>
            </ul>
          </li>
          <li><b>Telegram</b> (<code>@PASS24bot</code>):
            <ul>
              <li>Первое сообщение → тикет</li>
              <li>Следующие сообщения → комментарии к открытому тикету</li>
              <li>Ваши комментарии автоматически отправляются в чат клиента</li>
              <li>Команда <code>/new</code> создаёт новый тикет</li>
            </ul>
          </li>
        </ul>
      </section>

      <section id="sla" class="help-section">
        <h3>⏱️ SLA — счётчики и полоски</h3>

        <h4>Главное в одной фразе</h4>
        <p>SLA-таймер тикает <b>только в рабочее время</b>: пн–пт, 9:00–18:00 МСК. Ночью, в выходные и в статусах ожидания клиента счётчик стоит. Цвет полоски зависит от того, сколько <b>рабочего</b> времени осталось до дедлайна, а не от астрономического.</p>

        <h4>Два дедлайна на каждом тикете</h4>
        <ul>
          <li><b>Первый ответ</b> — за сколько часов сотрудник должен впервые ответить клиенту.</li>
          <li><b>Решение</b> — за сколько часов проблема должна быть полностью закрыта.</li>
        </ul>

        <h4>Часы по приоритету</h4>
        <ul>
          <li><b>Critical</b> — 1 ч ответ / 4 ч решение</li>
          <li><b>High</b> — 2 ч / 8 ч</li>
          <li><b>Normal</b> — 4 ч / 24 ч</li>
          <li><b>Low</b> — 8 ч / 48 ч</li>
        </ul>
        <p class="help-note">💡 Все цифры — в <b>рабочих</b> часах. «4 рабочих часа» от заявки, пришедшей в пятницу в 17:00, истекают <b>в понедельник в 12:00</b> (1 ч пт + 3 ч пн), а не в пятницу в 21:00.</p>

        <h4>Как читать цветную полоску</h4>
        <ul>
          <li><span style="color:#10b981">🟢 <b>Зелёный</b></span> — потрачено &lt; 50%, времени достаточно.</li>
          <li><span style="color:#f59e0b">🟡 <b>Жёлтый</b></span> — 50–75%, пора браться.</li>
          <li><span style="color:#f97316">🟠 <b>Оранжевый</b></span> — 75–90%, срочно.</li>
          <li><span style="color:#ef4444">🔴 <b>Красный</b></span> — &gt; 90% или уже просрочено.</li>
          <li><span style="color:#94a3b8">⚪ <b>Серый</b></span> — на паузе.</li>
        </ul>
        <p>Рядом с полоской — точный текст: «3 ч 15 мин», «На паузе», «Выполнено» или <b>«Просрочено на 1 ч 45 мин»</b> (точный размер просрочки видно сразу).</p>

        <h4>Когда таймер стоит на паузе</h4>
        <ul>
          <li><b>Сейчас нерабочее время</b> — ночь / выходные. Никаких визуальных бейджей не появляется, просто полоска не двигается.</li>
          <li><b>Ваш ответ был последним</b> в переписке. Система автоматически ставит SLA «Решение» на паузу — мяч на стороне клиента. Под полоской «Решение» появляется бейдж <code>⏸ SLA на паузе — ждём ответ клиента</code>, цвет серый.</li>
          <li><b>Статус «Ожидание ответа клиента»</b> (<code>WAITING_FOR_USER</code>) или <b>«Отложена»</b> (<code>ON_HOLD</code>) — то же самое визуально, бейдж говорит, какой именно статус.</li>
          <li><b>Internal-комментарии не паузят</b> — клиент их не видит.</li>
        </ul>
        <p class="help-note">⚠️ Важно: пауза тоже считается в <b>рабочих часах</b>. Если тикет ждал клиента с пятницы 18:00 до понедельника 10:00 — на паузе фактически прошёл 1 рабочий час (10:00–11:00 пн), а не 64 линейных. Дедлайн сдвинется на этот 1 час, а не «подарит» сотруднику все выходные.</p>

        <h4>Когда пауза снимается</h4>
        <ul>
          <li>Клиент ответил публичным сообщением (через веб / email / Telegram).</li>
          <li>Агент перевёл тикет в активный статус (<code>IN_PROGRESS</code>, <code>ENGINEER_VISIT</code>).</li>
        </ul>
        <p>В обоих случаях полоска снова цветная и таймер продолжает идти с учётом накопленной паузы.</p>

        <h4>Где это видно</h4>
        <ul>
          <li><b>В списке заявок</b> — тонкая полоска у каждого тикета — это <b>активный</b> SLA: «Первый ответ», пока вы ещё не ответили; после первого ответа — «Решение». Иконка ⏰ — идёт, ⏸ — на паузе, ❗ — просрочено.</li>
          <li><b>Список обновляется автоматически раз в минуту</b> — цвета не «замораживаются». Открыли вкладку утром — через минуту увидите актуальную картину после начала рабочего дня.</li>
          <li><b>В карточке заявки</b> (правая панель) — две отдельные полоски: «Первый ответ» и «Решение». Бейдж паузы появляется под полоской «Решение».</li>
          <li><b>Вкладка «Просрочено»</b> наверху списка — счётчик <b>реальных</b> просрочек (не «утренней красноты» в нерабочее время).</li>
        </ul>

        <h4>На что обращать внимание менеджеру</h4>
        <ul>
          <li><b>Утренняя «краснота» больше не индикатор.</b> Тикеты, пришедшие ночью или в выходные, теперь не показываются красными к утру. Если что-то красное утром — это <b>реальная</b> просрочка, требующая разбора.</li>
          <li><b>Серая полоска ≠ забытый тикет.</b> Это значит, что обязательство сейчас на стороне клиента или сейчас нерабочее время. Возвращаться к таким — приоритетно по началу рабочего дня, но они не в SLA-нарушении.</li>
          <li><b>«Просрочено на N ч M мин»</b> — точный размер просрочки. Чем больше число, тем выше эскалация. Эти тикеты должны быть в самом верху списка работы.</li>
          <li><b>Перевод в «Ожидание ответа клиента»</b> — реальный инструмент управления нагрузкой, а не способ «спрятать» тикет. Используйте, когда действительно ждёте ответа: SLA честно ставится на паузу.</li>
          <li><b>Уведомление за 30 минут до нарушения</b> приходит на support@pass24online.ru и в Telegram создателю. Если приходит — значит до реальной просрочки осталось 30 <b>рабочих</b> минут.</li>
        </ul>
      </section>

      <section id="dashboard" class="help-section">
        <h3>📊 Дашборд и отчёты</h3>
        <ul>
          <li><b>Мой дашборд</b> (<code>/dashboard</code>):
            <ul>
              <li>Назначено мне / В работе / Решено за 30 дней / Мой CSAT</li>
              <li>Таблица всех агентов с CSAT и средним временем решения</li>
            </ul>
          </li>
          <li><b>Аналитика</b> (<code>/analytics</code>) — графики по статусам, приоритетам, SLA</li>
          <li><b>CSV-экспорт</b> — кнопка на дашборде, выгрузка всех тикетов в Excel</li>
        </ul>
      </section>

      <section id="ai" class="help-section">
        <h3>🤖 AI-ассистент</h3>
        <ul>
          <li>Всплывающее окно справа внизу (синяя кнопка-чат)</li>
          <li>Использует <b>базу знаний как RAG-контекст</b> для ответов</li>
          <li>Может предложить создать тикет, если вопрос сложный</li>
          <li>Доступен <b>всем</b> — включая гостей без авторизации</li>
        </ul>
      </section>

      <!-- ========== ПРОЕКТЫ ВНЕДРЕНИЯ ========== -->
      <template v-if="canSeeProjects">
        <div class="projects-divider">
          <i class="pi pi-sitemap" />
          <span>Проекты внедрения</span>
        </div>

        <section id="projects" class="help-section">
          <h3>🏗️ Проекты внедрения</h3>
          <p>Модуль управления полным циклом установки PASS24 на объекте клиента: от договора до сдачи работ.</p>

          <h4>Типы проектов (шаблоны)</h4>
          <ul>
            <li><b>Стандартный ЖК</b> — 10 фаз, ~10 недель (КПП, подъезды, парковка)</li>
            <li><b>Стандартный БЦ</b> — 9 фаз, ~8 недель (турникеты, шлагбаумы, 1С/AD)</li>
            <li><b>Только камеры</b> — 5 фаз, ~4 недели (pass24.auto)</li>
            <li><b>Большая стройка</b> — 12 фаз, ~16 недель (тендер, поэтапная сдача)</li>
          </ul>

          <h4>Статусы проекта</h4>
          <pre class="help-code">Черновик → Планирование → В работе ⇄ На паузе → Завершён / Отменён</pre>

          <template v-if="isStaff">
            <h4>Создание проекта (только admin)</h4>
            <ol>
              <li><b>Проекты → Создать проект</b></li>
              <li>Если клиента нет — кнопка <b>«+»</b> рядом с полем клиента → создание с автогенерацией пароля</li>
              <li>Выбрать тип проекта → справа появится предпросмотр шаблона</li>
              <li>Указать объект, даты, менеджера → <b>«Создать проект»</b></li>
              <li>Клиенту уходит welcome-email: ссылка на портал, логин/пароль, этапы внедрения</li>
            </ol>

            <h4>Управление</h4>
            <ul>
              <li><b>Кнопка «Редактировать»</b> — название, даты, примечания</li>
              <li><b>Смена статуса</b> — кнопки переходов вверху страницы проекта</li>
              <li><b>Старт/Завершение фазы</b> — кнопки на карточке фазы</li>
              <li><b>Выполнение задачи</b> — ✓ на строке задачи (прогресс пересчитывается автоматически)</li>
              <li><b>Добавление задачи</b> — кнопка «Добавить задачу» внизу раскрытой фазы</li>
              <li><b>Редактирование дат фазы</b> — кликните на даты (пунктир) → inline-календарь</li>
            </ul>

            <h4>Связь с тикетами</h4>
            <ul>
              <li>На странице тикета → блок <b>«Проект внедрения»</b> → выбрать проект</li>
              <li>Отметить <b>«Блокирует проект»</b> если тикет критичен</li>
              <li>Блокеры выделены красным на вкладке «Тикеты» проекта</li>
            </ul>
          </template>

          <h4>Вкладки страницы проекта</h4>
          <ul>
            <li><b>Этапы</b> — раскрывающиеся карточки фаз с задачами</li>
            <li><b>Timeline</b> — вертикальная визуализация этапов</li>
            <li><b>Документы</b> — загрузка/скачивание файлов (до 20 МБ)</li>
            <li><b>Команда</b> — участники проекта с ролями</li>
            <li><b>Тикеты</b> — связанные заявки (блокеры выделены)</li>
            <li><b>Комментарии</b> — публичные + внутренние (только для PASS24)</li>
            <li><b>История</b> — все события проекта</li>
          </ul>

          <h4>Уведомления клиенту</h4>
          <ul>
            <li><b>Welcome-email</b> — при создании проекта с новым клиентом (портал + пароль + этапы)</li>
            <li><b>Создание проекта</b> — код, объект, список этапов</li>
            <li><b>Смена статуса</b> — новый статус, кто изменил</li>
            <li><b>Завершение фазы</b> — название фазы, текущий % прогресса</li>
            <li><b>Milestone выполнен</b> — название вехи, кто выполнил</li>
          </ul>

          <p class="help-note">💡 Прогресс считается автоматически: фаза = выполненные / активные задачи; проект = средневзвешенное по фазам.</p>
        </section>
      </template>

      <!-- ========== ADMIN-ONLY SECTIONS ========== -->
      <template v-if="isAdmin">
        <div class="admin-divider">
          <i class="pi pi-shield" />
          <span>Разделы только для администратора</span>
        </div>

        <section id="users" class="help-section admin-section">
          <h3>👥 Пользователи и роли</h3>
          <ul>
            <li><b>4 роли:</b>
              <ul>
                <li><code>resident</code> — житель / сотрудник БЦ</li>
                <li><code>property_manager</code> — администратор УК</li>
                <li><code>support_agent</code> — агент поддержки</li>
                <li><code>admin</code> — супер-администратор</li>
              </ul>
            </li>
            <li><b>Самостоятельная регистрация</b> — только <code>resident</code> и <code>property_manager</code></li>
            <li><b>support_agent / admin</b> — назначаются только администратором (через БД или в будущем через UI)</li>
            <li><b>RBAC</b>: резиденты видят только свои тикеты; агенты/админы — все</li>
            <li><b>Удаление тикетов</b> — только admin (не agent)</li>
            <li><b>Удаление статей БЗ</b> — только admin</li>
            <li><b>Одобрение улучшений БЗ</b> — только admin</li>
          </ul>
          <p class="help-note">💡 Сейчас смена роли делается через БД. В будущем появится UI управления пользователями.</p>
        </section>

        <section id="kb-review" class="help-section admin-section">
          <h3>📝 Ревью улучшений базы знаний</h3>
          <p>Агенты отправляют предложения по улучшению статей после решения тикетов, где клиент пришёл из конкретной статьи БЗ и не нашёл ответ.</p>
          <ul>
            <li><b>Endpoint</b>: <code>GET /tickets/kb-improvements/pending</code> — все ожидающие</li>
            <li><b>Workflow</b>:
              <ul>
                <li><code>pending</code> → ждёт решения</li>
                <li><code>applied</code> → вы внесли правку в статью</li>
                <li><code>rejected</code> → отклонено с причиной</li>
              </ul>
            </li>
            <li><b>Endpoint</b>: <code>PUT /tickets/kb-improvements/{id}/status</code> (admin-only) — сменить статус</li>
            <li><b>Метрики</b>: сколько предложений применено за период → качество обучения БЗ</li>
          </ul>
          <p class="help-note">💡 Data Flywheel: каждое решённое предложение снижает приток одинаковых тикетов. Следите за pending-очередью.</p>
        </section>

        <section id="settings" class="help-section admin-section">
          <h3>⚙️ SLA и системные настройки</h3>
          <ul>
            <li><b>SLA по приоритетам</b> (часы реакции / решения):
              <ul>
                <li>Critical: 1 / 4</li>
                <li>High: 2 / 8</li>
                <li>Normal: 4 / 24</li>
                <li>Low: 8 / 48</li>
              </ul>
              Задаются в коде <code>backend/tickets/models.py</code> (SLA_TABLE).
            </li>
            <li><b>Рабочие часы</b>: пн-пт 9-18 МСК (<code>backend/tickets/business_hours.py</code> — константы <code>WORK_START_HOUR</code>, <code>WORK_END_HOUR</code>, <code>MSK_OFFSET_HOURS</code>).</li>
            <li><b>Логика SLA</b> — <code>backend/tickets/sla_service.compute_sla_state(ticket, now)</code>. Единая точка истины: используется и в API (<code>TicketRead</code>), и в watcher. См. ADR-017.</li>
            <li><b>SLA watcher</b> запускается каждые 5 минут как фоновая задача lifespan FastAPI (<code>backend/tickets/sla_watcher.py</code>). Шлёт warning за 30 мин до нарушения активной фазы (response/resolve).</li>
            <li><b>Семантика паузы</b>: <code>sla_total_pause_seconds</code> хранит <b>бизнес-секунды</b> (только рабочее время). При снятии паузы накопитель растёт через <code>business_hours_between(sla_paused_at, now)</code>.</li>
            <li><b>Email-настройки</b> (SMTP/IMAP): env-переменные в docker-compose</li>
            <li><b>Telegram bot</b> (@PASS24bot): <code>TELEGRAM_BOT_TOKEN</code>, <code>TELEGRAM_WEBHOOK_SECRET</code></li>
            <li><b>AI-ассистент</b>: <code>ANTHROPIC_API_KEY</code>, Qdrant для RAG</li>
            <li><b>Миграции БД</b>: применяются вручную после деплоя:
              <pre class="help-code">docker exec site-pass24-servicedesk python -m alembic upgrade head</pre>
            </li>
          </ul>
        </section>
      </template>
      <!-- ========== END ADMIN-ONLY ========== -->

      <section class="help-section">
        <h3>💡 Полезные советы</h3>
        <ul>
          <li>Для резидентов: можно создавать заявки <b>«От имени клиента»</b> с их email/телефоном — клиент получит все уведомления</li>
          <li>Если клиент не отвечает — переведите в <code>RESOLVED</code>, SLA остановится</li>
          <li>При закрытии заявки клиент автоматически получает запрос на оценку (CSAT 1-5)</li>
          <li>Используйте <b>внутренние комментарии</b> для обсуждения тикета с коллегами без спама клиенту</li>
        </ul>
      </section>
    </div>

    <template #footer>
      <Button label="Закрыть" icon="pi pi-times" @click="close" />
    </template>
  </Dialog>
</template>

<style scoped>
.help-header { display: flex; align-items: center; gap: 10px; }
.help-header-icon { font-size: 20px; color: #3b82f6; }
.help-header-title { font-size: 16px; font-weight: 600; }

.help-content { max-height: 70vh; overflow-y: auto; padding: 0 4px; }

.help-toc {
  display: flex; flex-wrap: wrap; gap: 8px;
  padding: 12px; background: #f0f9ff; border-radius: 8px; margin-bottom: 20px;
  border: 1px solid #bae6fd;
}
.help-toc a {
  display: inline-block; padding: 4px 10px; background: white;
  border: 1px solid #e0f2fe; border-radius: 14px; font-size: 12px;
  color: #0369a1; text-decoration: none; transition: background 0.15s;
}
.help-toc a:hover { background: #e0f2fe; }

.help-section { margin-bottom: 28px; }
.help-section h3 { font-size: 17px; font-weight: 600; color: #1e293b; margin-bottom: 10px; scroll-margin-top: 20px; }
.help-section p { font-size: 14px; color: #475569; line-height: 1.6; margin-bottom: 8px; }
.help-section ul { padding-left: 20px; color: #475569; font-size: 14px; line-height: 1.7; }
.help-section ul ul { margin-top: 4px; padding-left: 18px; font-size: 13px; }
.help-section li { margin-bottom: 4px; }
.help-section code {
  background: #f1f5f9; padding: 2px 6px; border-radius: 4px;
  font-family: 'SF Mono', 'Monaco', monospace; font-size: 12px; color: #0369a1;
}
.help-code {
  background: #0f172a; color: #f8fafc; padding: 10px 14px; border-radius: 6px;
  font-family: 'SF Mono', 'Monaco', monospace; font-size: 12px; overflow-x: auto;
}
.help-note {
  background: #fef3c7; border-left: 3px solid #f59e0b; padding: 10px 14px;
  border-radius: 4px; font-size: 13px; color: #78350f;
}

/* Admin-specific styling */
.admin-link { background: #fef3c7 !important; border-color: #fcd34d !important; color: #78350f !important; }
.admin-link:hover { background: #fde68a !important; }
.admin-divider {
  display: flex; align-items: center; gap: 10px; margin: 24px 0 16px;
  padding: 10px 14px; background: linear-gradient(90deg, #fef3c7, transparent);
  border-left: 4px solid #f59e0b; border-radius: 4px;
  font-size: 13px; font-weight: 600; color: #78350f; text-transform: uppercase;
  letter-spacing: 0.5px;
}
.admin-divider i { font-size: 16px; }
.admin-section h3 { color: #78350f; }
.admin-section { border-left: 3px solid #fcd34d; padding-left: 14px; background: #fffbeb; border-radius: 0 6px 6px 0; padding-top: 8px; padding-bottom: 8px; }

/* Projects section */
.projects-link { background: #ecfdf5 !important; border-color: #6ee7b7 !important; color: #065f46 !important; }
.projects-link:hover { background: #d1fae5 !important; }
.projects-divider {
  display: flex; align-items: center; gap: 10px; margin: 24px 0 16px;
  padding: 10px 14px; background: linear-gradient(90deg, #ecfdf5, transparent);
  border-left: 4px solid #10b981; border-radius: 4px;
  font-size: 13px; font-weight: 600; color: #065f46; text-transform: uppercase;
  letter-spacing: 0.5px;
}
.projects-divider i { font-size: 16px; }
.help-section h4 { font-size: 14px; font-weight: 600; color: #334155; margin: 14px 0 6px; }
.help-section ol { padding-left: 20px; color: #475569; font-size: 14px; line-height: 1.7; }
.help-section ol li { margin-bottom: 4px; }
</style>

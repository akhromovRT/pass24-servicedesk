<script setup lang="ts">
import { ref } from 'vue'
import Button from 'primevue/button'
import Dialog from 'primevue/dialog'

const visible = ref(false)

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
        <i class="pi pi-book help-header-icon" />
        <span class="help-header-title">Инструкция для агентов поддержки</span>
      </div>
    </template>

    <div class="help-content">
      <!-- Навигация -->
      <nav class="help-toc">
        <a href="#tickets">📋 Заявки</a>
        <a href="#workflow">🔄 Работа с заявкой</a>
        <a href="#comments">💬 Комментарии</a>
        <a href="#tools">🛠️ Шаблоны и макросы</a>
        <a href="#notifications">🔔 Уведомления</a>
        <a href="#channels">📨 Каналы связи</a>
        <a href="#sla">⏱️ SLA</a>
        <a href="#dashboard">📊 Дашборд</a>
        <a href="#ai">🤖 AI-ассистент</a>
      </nav>

      <section id="tickets" class="help-section">
        <h3>📋 Заявки</h3>
        <ul>
          <li><b>Список заявок</b> (вкладка «Мои заявки») — все тикеты с фильтрами и поиском</li>
          <li><b>Вкладки-фильтры</b>: Все / Открытые / Срочные / Просрочено / Ждут ответа / Закрытые</li>
          <li><b>Поиск</b> — работает по теме, описанию, email, имени клиента, объекту</li>
          <li><b>Множественный фильтр</b> — выбор нескольких статусов/категорий сразу</li>
          <li><b>Массовые действия</b> — выделите несколько тикетов галочками, затем смените статус/назначение/удалите (admin)</li>
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
              <li>Вы пишете публичный комментарий → статус <code>WAITING_FOR_USER</code></li>
              <li>Клиент отвечает → статус <code>IN_PROGRESS</code></li>
            </ul>
          </li>
          <li><b>Merge дубликатов</b> — при нахождении двух одинаковых заявок можно слить в одну</li>
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
        <h3>⏱️ SLA</h3>
        <ul>
          <li><b>Часы реакции</b> зависят от приоритета:
            <ul>
              <li>Critical: 1 ч ответ / 4 ч решение</li>
              <li>High: 2 ч / 8 ч</li>
              <li>Normal: 4 ч / 24 ч</li>
              <li>Low: 8 ч / 48 ч</li>
            </ul>
          </li>
          <li><b>Рабочие часы</b>: пн-пт 9-18 МСК. В нерабочее время SLA не тикает.</li>
          <li><b>WAITING_FOR_USER</b> — таймер SLA на паузе пока клиент не ответит</li>
          <li><b>Цвет шкалы SLA</b> на странице заявки: зелёный → жёлтый → оранжевый → красный</li>
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
</style>

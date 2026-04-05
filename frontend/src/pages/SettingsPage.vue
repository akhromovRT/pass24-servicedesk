<script setup lang="ts">
import { ref } from 'vue'
import Card from 'primevue/card'
import Tag from 'primevue/tag'
import Divider from 'primevue/divider'

interface SettingsSection {
  id: string
  title: string
  icon: string
  description: string
  color: string
}

const sections: SettingsSection[] = [
  {
    id: 'email',
    title: 'Подключение почты',
    icon: 'pi pi-envelope',
    description: 'SMTP / IMAP для отправки и приёма email-обращений',
    color: '#3b82f6',
  },
  {
    id: 'telegram',
    title: 'Telegram-бот',
    icon: 'pi pi-send',
    description: 'Настройка бота для приёма заявок из Telegram',
    color: '#0ea5e9',
  },
]

const activeSection = ref<string | null>('email')

function toggleSection(id: string) {
  activeSection.value = activeSection.value === id ? null : id
}
</script>

<template>
  <div class="settings-page">
    <div class="settings-header">
      <h1 class="settings-title">Настройки системы</h1>
      <p class="settings-subtitle">Интеграции и конфигурация PASS24 Service Desk</p>
    </div>

    <!-- Sections list -->
    <div class="sections-list">
      <div
        v-for="section in sections"
        :key="section.id"
        class="section-card"
        :class="{ active: activeSection === section.id }"
        @click="toggleSection(section.id)"
      >
        <div class="section-icon-wrap" :style="{ background: section.color + '15', color: section.color }">
          <i :class="section.icon" />
        </div>
        <div class="section-info">
          <div class="section-title">{{ section.title }}</div>
          <div class="section-desc">{{ section.description }}</div>
        </div>
        <i class="pi pi-chevron-down section-arrow" :class="{ rotated: activeSection === section.id }" />
      </div>
    </div>

    <!-- Email section content -->
    <Transition name="slide-down">
      <Card v-if="activeSection === 'email'" class="settings-content">
        <template #title>
          <div class="content-title"><i class="pi pi-envelope" style="color:#3b82f6" /> Подключение почты</div>
        </template>
        <template #content>
          <p class="intro">Service Desk использует SMTP для отправки уведомлений и IMAP для автоматического создания тикетов из входящих писем.</p>

          <Divider />

          <h3 class="subsection-title">Текущая конфигурация</h3>
          <div class="config-grid">
            <div class="config-item">
              <span class="config-label">SMTP хост</span>
              <span class="config-value">smtp.timeweb.ru</span>
            </div>
            <div class="config-item">
              <span class="config-label">SMTP порт</span>
              <span class="config-value">465 (SSL)</span>
            </div>
            <div class="config-item">
              <span class="config-label">IMAP хост</span>
              <span class="config-value">imap.timeweb.ru</span>
            </div>
            <div class="config-item">
              <span class="config-label">IMAP порт</span>
              <span class="config-value">993 (SSL)</span>
            </div>
            <div class="config-item">
              <span class="config-label">Email</span>
              <span class="config-value">support@pass24online.ru</span>
            </div>
            <div class="config-item">
              <span class="config-label">Статус</span>
              <Tag value="Подключено" severity="success" />
            </div>
          </div>

          <Divider />

          <h3 class="subsection-title">Как работают исходящие письма (SMTP)</h3>
          <ul class="info-list">
            <li><strong>Уведомление о создании заявки</strong> — приходит заявителю сразу после создания тикета</li>
            <li><strong>Смена статуса</strong> — приходит создателю заявки при каждом изменении статуса агентом</li>
            <li><strong>Новый комментарий</strong> — приходит создателю, если комментарий оставил не он сам</li>
            <li><strong>Тема письма</strong> содержит тег <code>[PASS24-xxxxxxxx]</code> — используется для привязки ответов</li>
          </ul>

          <Divider />

          <h3 class="subsection-title">Как работают входящие письма (IMAP)</h3>
          <ul class="info-list">
            <li>Система опрашивает почтовый ящик <strong>каждые 60 секунд</strong></li>
            <li>Читает только непрочитанные письма (UNSEEN)</li>
            <li><strong>Если тема содержит тег</strong> <code>[PASS24-xxxxxxxx]</code> — письмо становится комментарием к заявке</li>
            <li><strong>Если тега нет</strong> — создаётся новая заявка, автор извлекается из поля From</li>
            <li>Вложения (файлы) сохраняются в заявке</li>
            <li>Bounce-письма (mailer-daemon) игнорируются</li>
          </ul>

          <Divider />

          <h3 class="subsection-title">Как изменить настройки</h3>
          <p class="info">Настройки задаются через переменные окружения в <code>docker-compose.yml</code> на сервере:</p>
          <pre class="code-block">environment:
  SMTP_PASSWORD: your-password
  SMTP_HOST: smtp.timeweb.ru
  SMTP_PORT: 465
  SMTP_USER: support@pass24online.ru
  IMAP_HOST: imap.timeweb.ru
  IMAP_POLL_INTERVAL: 60</pre>

          <div class="warning-box">
            <i class="pi pi-exclamation-triangle" />
            <div>
              <strong>Важно:</strong> после изменения переменных нужно перезапустить контейнер:
              <code>docker compose up -d</code>
            </div>
          </div>
        </template>
      </Card>
    </Transition>

    <!-- Telegram section content -->
    <Transition name="slide-down">
      <Card v-if="activeSection === 'telegram'" class="settings-content">
        <template #title>
          <div class="content-title"><i class="pi pi-send" style="color:#0ea5e9" /> Telegram-бот</div>
        </template>
        <template #content>
          <p class="intro">Telegram-бот принимает заявки от пользователей через Telegram и создаёт тикеты в Service Desk.</p>

          <Divider />

          <h3 class="subsection-title">Статус интеграции</h3>
          <div class="config-grid">
            <div class="config-item">
              <span class="config-label">Бот</span>
              <span class="config-value">@PASS24ROBOT</span>
            </div>
            <div class="config-item">
              <span class="config-label">Статус</span>
              <Tag value="Требует настройки" severity="warn" />
            </div>
          </div>

          <Divider />

          <h3 class="subsection-title">Как подключить Telegram-бота</h3>
          <ol class="steps-list">
            <li>
              <strong>Создайте бота через @BotFather</strong>
              <ul>
                <li>Откройте Telegram и найдите <a href="https://t.me/BotFather" target="_blank">@BotFather</a></li>
                <li>Отправьте команду <code>/newbot</code></li>
                <li>Укажите имя бота (например: PASS24 Support)</li>
                <li>Укажите username (должен заканчиваться на <code>bot</code>, например: <code>pass24_support_bot</code>)</li>
                <li>Сохраните полученный <strong>токен</strong> — он понадобится для настройки</li>
              </ul>
            </li>
            <li>
              <strong>Настройте приветственное сообщение</strong>
              <ul>
                <li>В @BotFather: <code>/setdescription</code> — описание бота</li>
                <li><code>/setabouttext</code> — короткое описание в профиле</li>
                <li><code>/setcommands</code> — список команд (start, help, new_ticket)</li>
              </ul>
            </li>
            <li>
              <strong>Добавьте токен в настройки сервера</strong>
              <pre class="code-block">environment:
  TELEGRAM_BOT_TOKEN: 123456:ABC-DEF...</pre>
            </li>
            <li>
              <strong>Перезапустите контейнер</strong>
              <pre class="code-block">docker compose -f /opt/sites/pass24-servicedesk/docker-compose.yml up -d</pre>
            </li>
            <li>
              <strong>Проверьте работу бота</strong>
              <ul>
                <li>Найдите бота в Telegram по username</li>
                <li>Отправьте <code>/start</code></li>
                <li>Создайте тестовую заявку через бота</li>
                <li>Убедитесь, что заявка появилась в Service Desk</li>
              </ul>
            </li>
          </ol>

          <Divider />

          <h3 class="subsection-title">Как работает бот</h3>
          <ul class="info-list">
            <li>Пользователь отправляет <code>/start</code> — бот просит представиться</li>
            <li>Пользователь выбирает тему из меню (пропуска, приложение, шлагбаум и т.д.)</li>
            <li>Бот задаёт уточняющие вопросы (как AI-помощник на портале)</li>
            <li>Если проблема не решается — бот создаёт заявку с email пользователя из Telegram</li>
            <li>Все обновления по заявке бот присылает в Telegram</li>
          </ul>

          <Divider />

          <h3 class="subsection-title">Команды бота</h3>
          <div class="commands-list">
            <div class="command-item">
              <code>/start</code>
              <span>Начало работы с ботом</span>
            </div>
            <div class="command-item">
              <code>/help</code>
              <span>Справка и список команд</span>
            </div>
            <div class="command-item">
              <code>/new_ticket</code>
              <span>Создать новую заявку</span>
            </div>
            <div class="command-item">
              <code>/my_tickets</code>
              <span>Мои заявки</span>
            </div>
            <div class="command-item">
              <code>/status &lt;ID&gt;</code>
              <span>Статус заявки по номеру</span>
            </div>
          </div>

          <div class="warning-box info-box">
            <i class="pi pi-info-circle" />
            <div>
              <strong>Текущий KB-бот.</strong> На сервере уже работает бот <code>pass24-kb-bot</code> для базы знаний (отвечает на вопросы через Claude + Qdrant). Новый бот Service Desk создаётся отдельно, чтобы не пересекаться с базой знаний.
            </div>
          </div>
        </template>
      </Card>
    </Transition>
  </div>
</template>

<style scoped>
.settings-page { display: flex; flex-direction: column; gap: 16px; }

.settings-header { margin-bottom: 8px; }
.settings-title { font-size: 24px; font-weight: 700; color: #0f172a; margin: 0 0 4px; }
.settings-subtitle { font-size: 14px; color: #64748b; margin: 0; }

.sections-list { display: flex; flex-direction: column; gap: 8px; }

.section-card {
  display: flex; align-items: center; gap: 14px;
  padding: 14px 18px; background: white; border-radius: 12px;
  cursor: pointer; transition: all 0.15s; border: 1px solid #e2e8f0;
}
.section-card:hover { border-color: #cbd5e1; box-shadow: 0 2px 8px rgba(0,0,0,0.04); }
.section-card.active { border-color: #3b82f6; background: #f8fafc; }

.section-icon-wrap {
  width: 44px; height: 44px; border-radius: 12px;
  display: flex; align-items: center; justify-content: center;
  font-size: 20px; flex-shrink: 0;
}

.section-info { flex: 1; }
.section-title { font-size: 15px; font-weight: 600; color: #1e293b; }
.section-desc { font-size: 13px; color: #64748b; margin-top: 2px; }

.section-arrow {
  color: #94a3b8; font-size: 14px; transition: transform 0.2s;
}
.section-arrow.rotated { transform: rotate(180deg); }

/* Transitions */
.slide-down-enter-active, .slide-down-leave-active { transition: all 0.25s ease; }
.slide-down-enter-from, .slide-down-leave-to { opacity: 0; transform: translateY(-10px); max-height: 0; }

/* Content */
.settings-content { margin-top: 0; }
.content-title {
  display: flex; align-items: center; gap: 10px;
  font-size: 18px; font-weight: 700; color: #0f172a;
}

.intro { color: #475569; font-size: 14px; margin: 0; }

.subsection-title {
  font-size: 15px; font-weight: 600; color: #1e293b;
  margin: 0 0 12px;
}

.config-grid {
  display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px;
}
@media (max-width: 600px) { .config-grid { grid-template-columns: 1fr; } }

.config-item {
  display: flex; justify-content: space-between; align-items: center;
  padding: 10px 14px; background: #f8fafc; border-radius: 8px;
  border: 1px solid #f1f5f9;
}
.config-label { font-size: 13px; color: #64748b; }
.config-value { font-size: 13px; color: #1e293b; font-weight: 500; font-family: 'SF Mono', Monaco, monospace; }

.info { font-size: 14px; color: #475569; margin: 0 0 10px; }

.info-list { list-style: none; padding: 0; margin: 0; }
.info-list li {
  padding: 8px 0 8px 22px; position: relative;
  font-size: 14px; color: #475569; line-height: 1.5;
}
.info-list li::before {
  content: "✓"; position: absolute; left: 0; top: 8px;
  color: #22c55e; font-weight: 700;
}

.steps-list { padding-left: 20px; margin: 0; color: #475569; }
.steps-list > li { margin-bottom: 14px; font-size: 14px; line-height: 1.5; }
.steps-list ul { list-style: disc; padding-left: 20px; margin-top: 6px; }
.steps-list ul li { padding: 3px 0; font-size: 13px; }

.commands-list { display: flex; flex-direction: column; gap: 6px; }
.command-item {
  display: flex; align-items: center; gap: 12px;
  padding: 8px 12px; background: #f8fafc; border-radius: 6px;
  border: 1px solid #f1f5f9;
}
.command-item code {
  background: #1e293b; color: #e2e8f0; padding: 2px 8px;
  border-radius: 4px; font-size: 12px; min-width: 120px;
}
.command-item span { font-size: 13px; color: #475569; }

code {
  background: #f1f5f9; color: #0f172a; padding: 2px 6px;
  border-radius: 4px; font-size: 13px;
  font-family: 'SF Mono', Monaco, monospace;
}

.code-block {
  background: #1e293b; color: #e2e8f0;
  padding: 12px 16px; border-radius: 8px;
  font-family: 'SF Mono', Monaco, monospace; font-size: 12px;
  line-height: 1.5; overflow-x: auto; margin: 8px 0;
}
.code-block code { background: transparent; color: inherit; padding: 0; }

.warning-box, .info-box {
  display: flex; gap: 12px; align-items: flex-start;
  padding: 12px 14px; border-radius: 8px; margin-top: 12px;
  font-size: 13px; line-height: 1.5;
}
.warning-box { background: #fef3c7; border: 1px solid #fde68a; color: #92400e; }
.warning-box i { color: #d97706; font-size: 16px; flex-shrink: 0; margin-top: 2px; }
.warning-box code { background: #fef9c3; color: #78350f; }

.info-box { background: #eff6ff; border: 1px solid #bfdbfe; color: #1e40af; }
.info-box i { color: #3b82f6; font-size: 16px; flex-shrink: 0; margin-top: 2px; }
.info-box code { background: #dbeafe; color: #1e3a8a; }

a { color: #3b82f6; }
</style>

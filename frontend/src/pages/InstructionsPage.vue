<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import InputText from 'primevue/inputtext'
import IconField from 'primevue/iconfield'
import InputIcon from 'primevue/inputicon'
import Tag from 'primevue/tag'

const router = useRouter()
const searchQuery = ref('')

interface Guide {
  title: string
  description: string
  icon: string
  slug: string
  badge?: string
}

interface Section {
  id: string
  title: string
  subtitle: string
  icon: string
  color: string
  gradient: string
  guides: Guide[]
}

const sections: Section[] = [
  {
    id: 'mobile',
    title: 'Мобильное приложение',
    subtitle: 'Пропуска, проходы и управление доступом со смартфона',
    icon: 'pi pi-mobile',
    color: '#3b82f6',
    gradient: 'linear-gradient(135deg, #3b82f6, #1d4ed8)',
    guides: [
      { title: 'Установка и первый вход', description: 'Скачивание, регистрация, настройка профиля', icon: 'pi pi-download', slug: 'kak-ustanovit-i-nastroit-prilozhenie-pass24' },
      { title: 'Создание пропуска для пешехода', description: 'Пошаговая инструкция для гостевого прохода', icon: 'pi pi-user', slug: 'sozdanie-propuska-dlya-peshekhoda-v-mobilnom-prilozhenii' },
      { title: 'Создание пропуска на автомобиль', description: 'Пропуск для проезда через шлагбаум', icon: 'pi pi-car', slug: 'sozdanie-propuska-na-avtomobil-v-mobilnom-prilozhenii' },
      { title: 'Приглашение — гость заполняет сам', description: 'Отправьте ссылку, гость введёт свои данные', icon: 'pi pi-send', slug: 'priglashenie-gost-zapolnyaet-dannye-samostoyatelno' },
      { title: 'Управление пропусками', description: 'Мои пропуска: поиск, шаблоны, закрытие', icon: 'pi pi-list', slug: 'upravlenie-propuskami-razdel-moi-propuska' },
      { title: 'Запросы в УК', description: 'Доверенность, новый адрес, постоянный пропуск, обращение в УК', icon: 'pi pi-file-edit', slug: 'zaprosy-v-mobilnom-prilozhenii-doverennost-adres-obrashchenie-v-uk' },
      { title: 'FAQ по приложению', description: '9 частых вопросов и ответов', icon: 'pi pi-question-circle', slug: 'faq-po-mobilnomu-prilozheniyu-pass24', badge: 'FAQ' },
    ],
  },
  {
    id: 'web',
    title: 'Веб-интерфейс администратора',
    subtitle: 'Управление объектом, пользователями и пропусками через браузер',
    icon: 'pi pi-desktop',
    color: '#8b5cf6',
    gradient: 'linear-gradient(135deg, #8b5cf6, #6d28d9)',
    guides: [
      { title: 'Модуль «Пропуска»', description: 'Создание, закрытие, массовые операции, экспорт', icon: 'pi pi-id-card', slug: 'modul-propuska-sozdanie-i-upravlenie-v-veb-interfeyse' },
      { title: 'Модуль «Пользователи»', description: 'Добавление, импорт, блокировка пользователей', icon: 'pi pi-users', slug: 'modul-polzovateli-upravlenie-zhitelyami-i-sotrudnikami' },
      { title: 'Модуль «Запросы»', description: 'Одобрение заявок от жителей на пропуска и доступ', icon: 'pi pi-inbox', slug: 'modul-zaprosy-odobrenie-zayavok-ot-zhiteley' },
      { title: 'Модуль «Адреса»', description: 'Управление адресами, импорт, привязка жителей', icon: 'pi pi-map-marker', slug: 'modul-adresa-upravlenie-adresami-obekta' },
      { title: 'Модуль «Объекты»', description: 'Настройки объекта, КПП, типы транспорта, чёрный список', icon: 'pi pi-building', slug: 'modul-obekty-nastroyki-zhk-bts' },
      { title: 'Массовая рассылка пропусков', description: 'Импорт из Excel и массовая отправка', icon: 'pi pi-upload', slug: 'massovaya-rassylka-peshekhodnykh-propuskov' },
    ],
  },
  {
    id: 'keys',
    title: 'PASS24.Key — мобильные ключи',
    subtitle: 'Открывайте двери и шлагбаумы смартфоном через Bluetooth',
    icon: 'pi pi-key',
    color: '#f59e0b',
    gradient: 'linear-gradient(135deg, #f59e0b, #d97706)',
    guides: [
      { title: 'Установка PASS24.Key', description: 'Скачивание приложения и активация ключа', icon: 'pi pi-download', slug: 'ustanovka-prilozheniya-pass24-key-dlya-ble-klyuchey' },
      { title: 'Активация BLE-ключа по QR-коду', description: 'Сканирование QR, подключение Bluetooth', icon: 'pi pi-qrcode', slug: 'aktivatsiya-ble-klyucha-po-qr-kodu' },
      { title: 'Настройка Bluetooth и разрешений', description: 'iOS и Android — какие разрешения нужны', icon: 'pi pi-cog', slug: 'nastroyka-bluetooth-i-razresheniy-dlya-pass24-key' },
    ],
  },
  {
    id: 'qr',
    title: 'QR-коды и приглашения',
    subtitle: 'Как работает проход по QR-коду — от создания до валидации',
    icon: 'pi pi-qrcode',
    color: '#10b981',
    gradient: 'linear-gradient(135deg, #10b981, #059669)',
    guides: [
      { title: 'Как работает QR-пропуск', description: 'Полный цикл: создание → отправка → проход → деактивация', icon: 'pi pi-sync', slug: 'kak-rabotaet-qr-propusk-v-pass24' },
      { title: 'Создание приглашения с QR-кодом', description: 'Пошаговая инструкция для жителя', icon: 'pi pi-plus', slug: 'sozdanie-priglasheniya-s-qr-kodom-poshagovaya-instruktsiya' },
    ],
  },
  {
    id: 'auto',
    title: 'PASS24.auto — распознавание номеров',
    subtitle: 'Автоматический проезд через шлагбаум по номеру автомобиля',
    icon: 'pi pi-car',
    color: '#ef4444',
    gradient: 'linear-gradient(135deg, #ef4444, #dc2626)',
    guides: [
      { title: 'Как работает распознавание', description: 'Камера считывает номер → проверяет пропуск → открывает шлагбаум', icon: 'pi pi-camera', slug: 'kamera-ne-raspoznayot-nomer-avtomobilya' },
      { title: 'Шлагбаум не открывается', description: 'Диагностика и решение типичных проблем', icon: 'pi pi-exclamation-triangle', slug: 'shlagbaum-ne-otkryvaetsya' },
    ],
  },
  {
    id: 'telegram',
    title: 'Telegram-бот PASS24',
    subtitle: 'Заказ пропусков через Telegram без установки приложения',
    icon: 'pi pi-telegram',
    color: '#0ea5e9',
    gradient: 'linear-gradient(135deg, #0ea5e9, #0284c7)',
    guides: [
      { title: 'Заказ пропуска через Telegram', description: 'Бот @PASS24ROBOT: подтверждение, выбор объекта, создание пропуска', icon: 'pi pi-comment', slug: 'zakaz-propuska-cherez-telegram-bot-pass24' },
    ],
  },
]

const filteredSections = computed(() => {
  if (!searchQuery.value.trim()) return sections
  const q = searchQuery.value.toLowerCase()
  return sections
    .map(section => ({
      ...section,
      guides: section.guides.filter(
        g => g.title.toLowerCase().includes(q) || g.description.toLowerCase().includes(q)
      ),
    }))
    .filter(s => s.guides.length > 0)
})

function openGuide(slug: string) {
  router.push(`/instructions/${slug}`)
}
</script>

<template>
  <div class="instructions">
    <!-- Hero -->
    <div class="hero">
      <h1 class="hero-title">Инструкции PASS24</h1>
      <p class="hero-subtitle">Пошаговые руководства по всем продуктам и возможностям системы</p>
      <IconField class="hero-search">
        <InputIcon class="pi pi-search" />
        <InputText
          v-model="searchQuery"
          placeholder="Найти инструкцию..."
          class="hero-search-input"
        />
      </IconField>
    </div>

    <!-- Quick stats -->
    <div class="stats-bar">
      <div class="stat" v-for="section in sections" :key="section.id">
        <i :class="section.icon" :style="{ color: section.color }" />
        <span class="stat-count">{{ section.guides.length }}</span>
        <span class="stat-label">{{ section.title.split('—')[0].split('PASS24.')[0].trim() }}</span>
      </div>
    </div>

    <!-- Sections -->
    <div v-for="section in filteredSections" :key="section.id" class="section">
      <div class="section-header">
        <div class="section-icon" :style="{ background: section.gradient }">
          <i :class="section.icon" />
        </div>
        <div>
          <h2 class="section-title">{{ section.title }}</h2>
          <p class="section-subtitle">{{ section.subtitle }}</p>
        </div>
      </div>

      <div class="guides-grid">
        <div
          v-for="guide in section.guides"
          :key="guide.slug"
          class="guide-card"
          @click="openGuide(guide.slug)"
        >
          <div class="guide-icon-wrap" :style="{ color: section.color }">
            <i :class="guide.icon" />
          </div>
          <div class="guide-content">
            <div class="guide-title-row">
              <h3 class="guide-title">{{ guide.title }}</h3>
              <Tag v-if="guide.badge" :value="guide.badge" severity="info" class="guide-badge" />
            </div>
            <p class="guide-desc">{{ guide.description }}</p>
          </div>
          <i class="pi pi-chevron-right guide-arrow" />
        </div>
      </div>
    </div>

    <!-- Empty state -->
    <div v-if="filteredSections.length === 0" class="empty">
      <i class="pi pi-search empty-icon" />
      <p>По запросу «{{ searchQuery }}» ничего не найдено</p>
      <p class="empty-hint">Попробуйте другие ключевые слова или загляните в <router-link to="/knowledge">базу знаний</router-link></p>
    </div>
  </div>
</template>

<style scoped>
.instructions {
  max-width: 900px;
  margin: 0 auto;
}

/* Hero */
.hero {
  text-align: center;
  padding: 40px 20px 32px;
}

.hero-title {
  font-size: 32px;
  font-weight: 800;
  color: #0f172a;
  margin-bottom: 8px;
  letter-spacing: -0.02em;
}

.hero-subtitle {
  font-size: 16px;
  color: #64748b;
  margin-bottom: 24px;
}

.hero-search {
  max-width: 480px;
  margin: 0 auto;
  display: block;
}

.hero-search :deep(input) {
  width: 100%;
  border-radius: 12px;
  padding: 12px 16px 12px 40px;
  font-size: 15px;
  border: 2px solid #e2e8f0;
  transition: border-color 0.2s;
}

.hero-search :deep(input:focus) {
  border-color: #3b82f6;
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
}

/* Stats bar */
.stats-bar {
  display: flex;
  gap: 4px;
  justify-content: center;
  flex-wrap: wrap;
  margin-bottom: 32px;
  padding: 0 20px;
}

.stat {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 14px;
  background: white;
  border-radius: 20px;
  font-size: 13px;
  border: 1px solid #e2e8f0;
}

.stat i { font-size: 14px; }
.stat-count { font-weight: 700; color: #1e293b; }
.stat-label { color: #64748b; }

/* Section */
.section {
  margin-bottom: 36px;
}

.section-header {
  display: flex;
  align-items: center;
  gap: 14px;
  margin-bottom: 16px;
  padding: 0 4px;
}

.section-icon {
  width: 44px;
  height: 44px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  font-size: 20px;
  flex-shrink: 0;
}

.section-title {
  font-size: 18px;
  font-weight: 700;
  color: #0f172a;
  margin: 0;
}

.section-subtitle {
  font-size: 14px;
  color: #64748b;
  margin: 2px 0 0;
}

/* Guide cards */
.guides-grid {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.guide-card {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 14px 18px;
  background: white;
  border-radius: 12px;
  cursor: pointer;
  transition: all 0.15s;
  border: 1px solid #f1f5f9;
}

.guide-card:hover {
  border-color: #e2e8f0;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
  transform: translateX(4px);
}

.guide-icon-wrap {
  width: 38px;
  height: 38px;
  border-radius: 10px;
  background: #f8fafc;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
  flex-shrink: 0;
}

.guide-content {
  flex: 1;
  min-width: 0;
}

.guide-title-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.guide-title {
  font-size: 15px;
  font-weight: 600;
  color: #1e293b;
  margin: 0;
}

.guide-badge { font-size: 11px; }

.guide-desc {
  font-size: 13px;
  color: #94a3b8;
  margin: 2px 0 0;
}

.guide-arrow {
  color: #cbd5e1;
  font-size: 12px;
  flex-shrink: 0;
  transition: color 0.15s;
}

.guide-card:hover .guide-arrow {
  color: #3b82f6;
}

/* Empty */
.empty {
  text-align: center;
  padding: 60px 20px;
  color: #94a3b8;
}

.empty-icon {
  font-size: 40px;
  margin-bottom: 12px;
  opacity: 0.5;
}

.empty-hint {
  font-size: 14px;
  margin-top: 8px;
}

.empty-hint a {
  color: #3b82f6;
}

/* Responsive */
@media (max-width: 640px) {
  .hero-title { font-size: 24px; }
  .stats-bar { gap: 6px; }
  .stat { padding: 4px 10px; font-size: 12px; }
  .guide-card { padding: 12px 14px; }
}
</style>

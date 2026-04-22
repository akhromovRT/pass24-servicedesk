<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import InputText from 'primevue/inputtext'
import IconField from 'primevue/iconfield'
import InputIcon from 'primevue/inputicon'
import Button from 'primevue/button'
import Tag from 'primevue/tag'
import { useToast } from 'primevue/usetoast'
import { useKnowledgeStore } from '../stores/knowledge'
import { useAuthStore } from '../stores/auth'
import type { Article } from '../types'

const router = useRouter()
const route = useRoute()
const toast = useToast()
const knowledge = useKnowledgeStore()
const auth = useAuthStore()

const searchInput = ref('')
const selectedType = ref<'all' | 'guide' | 'faq'>('all')
const selectedTag = ref<string | null>(null)
let debounceTimer: ReturnType<typeof setTimeout> | null = null

interface CategoryMeta {
  id: string
  title: string
  subtitle: string
  icon: string
  color: string
  gradient: string
}

// Метаданные для 6 категорий БД: иконки и цвета
const CATEGORIES: CategoryMeta[] = [
  {
    id: 'app',
    title: 'Мобильное приложение',
    subtitle: 'Установка, пропуска, проходы со смартфона',
    icon: 'pi pi-mobile',
    color: '#3b82f6',
    gradient: 'linear-gradient(135deg, #3b82f6, #1d4ed8)',
  },
  {
    id: 'pass',
    title: 'Пропуска и QR-коды',
    subtitle: 'Создание, приглашения, гостевые пропуска',
    icon: 'pi pi-id-card',
    color: '#22c55e',
    gradient: 'linear-gradient(135deg, #22c55e, #16a34a)',
  },
  {
    id: 'access',
    title: 'Доступ и вход',
    subtitle: 'Регистрация, вход, SMS-коды, восстановление',
    icon: 'pi pi-sign-in',
    color: '#ef4444',
    gradient: 'linear-gradient(135deg, #ef4444, #dc2626)',
  },
  {
    id: 'gate',
    title: 'Шлагбаумы и камеры',
    subtitle: 'Распознавание номеров, проезд через КПП',
    icon: 'pi pi-car',
    color: '#f59e0b',
    gradient: 'linear-gradient(135deg, #f59e0b, #d97706)',
  },
  {
    id: 'notifications',
    title: 'Уведомления',
    subtitle: 'Push, email, настройки оповещений',
    icon: 'pi pi-bell',
    color: '#8b5cf6',
    gradient: 'linear-gradient(135deg, #8b5cf6, #6d28d9)',
  },
  {
    id: 'general',
    title: 'Общее',
    subtitle: 'О платформе, безопасность, тарифы',
    icon: 'pi pi-info-circle',
    color: '#64748b',
    gradient: 'linear-gradient(135deg, #64748b, #475569)',
  },
]

const allArticles = ref<Article[]>([])
const loadingAll = ref(false)

const canCreate = computed(
  () => auth.user?.role === 'support_agent' || auth.user?.role === 'admin',
)

// Топ-теги: считаем частоту тегов по всем статьям, берём топ-8
const topTags = computed(() => {
  const counts = new Map<string, number>()
  for (const article of allArticles.value) {
    for (const tag of article.tags || []) {
      counts.set(tag, (counts.get(tag) || 0) + 1)
    }
  }
  return Array.from(counts.entries())
    .sort((a, b) => b[1] - a[1])
    .slice(0, 8)
    .map(([tag, count]) => ({ tag, count }))
})

// Переводы ключевых тегов на русский для отображения
const tagLabels: Record<string, string> = {
  sms: 'SMS-коды',
  registration: 'Регистрация',
  login: 'Вход',
  password: 'Пароль',
  recovery: 'Восстановление',
  onboarding: 'Первый вход',
  crash: 'Вылеты',
  app: 'Приложение',
  account: 'Аккаунт',
  duplicate: 'Дубликаты',
  authentication: 'Аутентификация',
  stability: 'Стабильность',
  troubleshooting: 'Диагностика',
  hub: 'Общее',
}

// Фильтрация по типу + тегу + поисковому запросу (клиентская, т.к. статей немного)
const filteredArticles = computed(() => {
  let list = allArticles.value
  if (selectedType.value !== 'all') {
    list = list.filter((a) => a.article_type === selectedType.value)
  }
  if (selectedTag.value) {
    list = list.filter((a) => (a.tags || []).includes(selectedTag.value!))
  }
  const q = searchInput.value.trim().toLowerCase()
  if (q) {
    list = list.filter(
      (a) =>
        a.title.toLowerCase().includes(q) ||
        a.content.toLowerCase().includes(q) ||
        (a.tags || []).some((t) => t.includes(q)) ||
        (a.synonyms || []).some((s) => s.toLowerCase().includes(q)),
    )
  }
  return list
})

function toggleTag(tag: string) {
  selectedTag.value = selectedTag.value === tag ? null : tag
}

// Группировка статей по категории (для секций)
const articlesByCategory = computed(() => {
  const map = new Map<string, Article[]>()
  for (const article of filteredArticles.value) {
    if (!map.has(article.category)) map.set(article.category, [])
    map.get(article.category)!.push(article)
  }
  return map
})

const visibleCategories = computed(() =>
  CATEGORIES.filter((c) => (articlesByCategory.value.get(c.id)?.length || 0) > 0),
)

const totalVisibleCount = computed(() => filteredArticles.value.length)

function typeLabel(t: string): { label: string; severity: string } {
  return t === 'guide'
    ? { label: 'Инструкция', severity: 'info' }
    : { label: 'FAQ', severity: 'warn' }
}

function articleIcon(article: Article): string {
  // Для guide — pi-book, для faq — pi-question-circle
  return article.article_type === 'guide' ? 'pi pi-book' : 'pi pi-question-circle'
}

async function loadAll() {
  loadingAll.value = true
  try {
    // Store хардкодит per_page=20; собираем все страницы вручную
    await knowledge.fetchArticles(1)
    allArticles.value = [...knowledge.articles]

    // Защита: максимум 10 страниц (200 статей) чтобы не зациклиться при багах API
    let safety = 10
    while (allArticles.value.length < knowledge.total && safety-- > 0) {
      const nextPage = Math.floor(allArticles.value.length / 20) + 1
      const prevCount = allArticles.value.length
      await knowledge.fetchArticles(nextPage)
      allArticles.value.push(...knowledge.articles)
      if (allArticles.value.length === prevCount) break
    }
  } catch (e: any) {
    toast.add({
      severity: 'error',
      summary: 'Ошибка',
      detail: e.message || 'Не удалось загрузить статьи',
      life: 4000,
    })
  } finally {
    loadingAll.value = false
  }
}

function onSearchInput() {
  if (debounceTimer) clearTimeout(debounceTimer)
  // Здесь debounce нужен только чтобы computed не дёргался на каждой букве,
  // но так как Vue реактивность и так дешёвая, просто применяем сразу
  debounceTimer = setTimeout(() => {
    // trigger reactivity (уже через v-model → searchInput)
  }, 100)
}

function openArticle(slug: string) {
  router.push(`/knowledge/${slug}`)
}

onMounted(async () => {
  await loadAll()
  // Применяем tag из query ?tag=sms
  const tagFromQuery = route.query.tag
  if (tagFromQuery && typeof tagFromQuery === 'string') {
    selectedTag.value = tagFromQuery
  }
})
watch(searchInput, onSearchInput)
// Синхронизируем selectedTag ↔ URL (чтобы можно было шарить ссылки)
watch(selectedTag, (newTag) => {
  router.replace({ query: newTag ? { ...route.query, tag: newTag } : {} })
})
</script>

<template>
  <div class="knowledge">
    <!-- Hero -->
    <div class="hero">
      <h1 class="hero-title">База знаний PASS24</h1>
      <p class="hero-subtitle">
        Пошаговые инструкции, ответы на частые вопросы и руководства по всем продуктам
      </p>
      <IconField class="hero-search">
        <InputIcon class="pi pi-search" />
        <InputText
          v-model="searchInput"
          placeholder="Найти статью или инструкцию..."
          class="hero-search-input"
        />
      </IconField>

      <!-- Фильтр по типу: переключатель -->
      <div class="type-filter">
        <button
          type="button"
          :class="['type-btn', { active: selectedType === 'all' }]"
          @click="selectedType = 'all'"
        >
          <i class="pi pi-th-large" />
          Все
        </button>
        <button
          type="button"
          :class="['type-btn', { active: selectedType === 'guide' }]"
          @click="selectedType = 'guide'"
        >
          <i class="pi pi-book" />
          Инструкции
        </button>
        <button
          type="button"
          :class="['type-btn', { active: selectedType === 'faq' }]"
          @click="selectedType = 'faq'"
        >
          <i class="pi pi-question-circle" />
          FAQ
        </button>
      </div>

      <!-- Топ-теги: быстрый фильтр по темам -->
      <div v-if="topTags.length > 0" class="tag-chips">
        <button
          v-for="{ tag, count } in topTags"
          :key="tag"
          type="button"
          :class="['tag-chip', { active: selectedTag === tag }]"
          @click="toggleTag(tag)"
        >
          <i class="pi pi-tag" />
          {{ tagLabels[tag] || tag }}
          <span class="tag-count">{{ count }}</span>
        </button>
        <button
          v-if="selectedTag"
          type="button"
          class="tag-chip clear"
          @click="selectedTag = null"
        >
          <i class="pi pi-times" />
          Сбросить
        </button>
      </div>

      <div v-if="canCreate" class="hero-actions">
        <Button
          label="Аналитика"
          icon="pi pi-chart-line"
          size="small"
          severity="secondary"
          outlined
          @click="router.push('/kb-analytics')"
        />
        <Button
          label="Создать статью"
          icon="pi pi-plus"
          size="small"
          severity="secondary"
          outlined
          @click="router.push('/knowledge/create')"
        />
      </div>
    </div>

    <!-- Loading -->
    <div v-if="loadingAll" class="knowledge-loading">
      <i class="pi pi-spin pi-spinner" style="font-size: 2rem; color: #94a3b8" />
    </div>

    <!-- Empty state -->
    <div v-else-if="totalVisibleCount === 0" class="empty">
      <i class="pi pi-search empty-icon" />
      <p v-if="searchInput">По запросу «{{ searchInput }}» ничего не найдено</p>
      <p v-else>Статьи не найдены</p>
      <div class="empty-cta">
        <span class="empty-cta__text">Не нашли ответ?</span>
        <router-link to="/tickets/create" class="empty-cta__button">
          <i class="pi pi-plus" />
          Создайте заявку
        </router-link>
      </div>
    </div>

    <!-- Stats bar -->
    <div v-else-if="!searchInput && selectedType === 'all'" class="stats-bar">
      <div
        v-for="cat in CATEGORIES"
        :key="cat.id"
        class="stat"
        :style="{ borderColor: (articlesByCategory.get(cat.id)?.length || 0) > 0 ? cat.color : '#e2e8f0' }"
      >
        <i :class="cat.icon" :style="{ color: cat.color }" />
        <span class="stat-count">{{ articlesByCategory.get(cat.id)?.length || 0 }}</span>
        <span class="stat-label">{{ cat.title.split(' ')[0] }}</span>
      </div>
    </div>

    <!-- Sections -->
    <div v-if="!loadingAll && totalVisibleCount > 0" class="sections">
      <div v-for="cat in visibleCategories" :key="cat.id" class="section">
        <div class="section-header">
          <div class="section-icon" :style="{ background: cat.gradient }">
            <i :class="cat.icon" />
          </div>
          <div class="section-head-text">
            <h2 class="section-title">{{ cat.title }}</h2>
            <p class="section-subtitle">{{ cat.subtitle }}</p>
          </div>
          <div class="section-count">
            {{ articlesByCategory.get(cat.id)?.length || 0 }}
          </div>
        </div>

        <div class="articles-grid">
          <div
            v-for="article in articlesByCategory.get(cat.id) || []"
            :key="article.id"
            class="article-card"
            @click="openArticle(article.slug)"
          >
            <div class="article-icon" :style="{ color: cat.color }">
              <i :class="articleIcon(article)" />
            </div>
            <div class="article-body">
              <div class="article-title-row">
                <h3 class="article-title">{{ article.title }}</h3>
                <Tag
                  :value="typeLabel(article.article_type).label"
                  :severity="typeLabel(article.article_type).severity"
                  class="article-type-tag"
                />
              </div>
              <div class="article-meta">
                <span><i class="pi pi-eye" /> {{ article.views_count }}</span>
              </div>
            </div>
            <i class="pi pi-chevron-right article-arrow" />
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.knowledge {
  max-width: 900px;
  margin: 0 auto;
}

/* Hero */
.hero {
  text-align: center;
  padding: 40px 20px 24px;
}

.hero-title {
  font-size: 32px;
  font-weight: 800;
  color: #0f172a;
  margin: 0 0 8px;
  letter-spacing: -0.02em;
}

.hero-subtitle {
  font-size: 16px;
  color: #64748b;
  margin: 0 0 24px;
  max-width: 600px;
  margin-left: auto;
  margin-right: auto;
}

.hero-search {
  max-width: 520px;
  margin: 0 auto;
  display: block;
}

.hero-search :deep(input) {
  width: 100%;
  border-radius: 12px;
  padding: 13px 16px 13px 40px;
  font-size: 15px;
  border: 2px solid #e2e8f0;
  transition: border-color 0.2s, box-shadow 0.2s;
}

.hero-search :deep(input:focus) {
  border-color: #3b82f6;
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
}

/* Type filter (segmented control) */
.type-filter {
  display: inline-flex;
  gap: 4px;
  padding: 4px;
  background: #f1f5f9;
  border-radius: 10px;
  margin-top: 20px;
}

.type-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  background: transparent;
  border: none;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 500;
  color: #64748b;
  cursor: pointer;
  transition: all 0.15s;
}

.type-btn:hover {
  color: #1e293b;
}

.type-btn.active {
  background: white;
  color: #1e293b;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
}

.type-btn i {
  font-size: 13px;
}

.hero-actions {
  margin-top: 16px;
  display: flex;
  gap: 8px;
  justify-content: center;
  flex-wrap: wrap;
}

/* Tag chips */
.tag-chips {
  display: flex;
  gap: 6px;
  justify-content: center;
  flex-wrap: wrap;
  margin-top: 16px;
  padding: 0 20px;
}

.tag-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  background: white;
  border: 1px solid #e2e8f0;
  border-radius: 20px;
  font-size: 13px;
  color: #475569;
  cursor: pointer;
  transition: all 0.15s;
}

.tag-chip i {
  font-size: 11px;
  color: #94a3b8;
}

.tag-chip:hover {
  border-color: #cbd5e1;
  background: #f8fafc;
}

.tag-chip.active {
  background: #3b82f6;
  border-color: #3b82f6;
  color: white;
}

.tag-chip.active i {
  color: white;
}

.tag-chip.clear {
  color: #94a3b8;
  font-size: 12px;
}

.tag-count {
  font-weight: 600;
  font-size: 11px;
  color: #94a3b8;
  padding-left: 2px;
}

.tag-chip.active .tag-count {
  color: rgba(255, 255, 255, 0.85);
}

/* Loading / empty */
.knowledge-loading {
  display: flex;
  justify-content: center;
  padding: 80px 0;
}

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

.empty-cta {
  display: inline-flex;
  align-items: center;
  gap: 14px;
  flex-wrap: wrap;
  justify-content: center;
  margin-top: 24px;
  padding: 16px 24px;
  background: rgba(59, 130, 246, 0.08);
  border: 1px solid rgba(59, 130, 246, 0.25);
  border-radius: 12px;
  backdrop-filter: blur(4px);
}

.empty-cta__text {
  font-size: 18px;
  font-weight: 500;
  color: #334155;
}

.empty-cta__button {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 10px 18px;
  background: #3b82f6;
  color: #ffffff;
  font-size: 16px;
  font-weight: 600;
  text-decoration: none;
  border-radius: 8px;
  transition: background 0.15s ease, transform 0.15s ease, box-shadow 0.15s ease;
  box-shadow: 0 2px 6px rgba(59, 130, 246, 0.25);
}

.empty-cta__button:hover {
  background: #2563eb;
  transform: translateY(-1px);
  box-shadow: 0 4px 10px rgba(59, 130, 246, 0.35);
}

.empty-cta__button:active {
  transform: translateY(0);
  box-shadow: 0 2px 4px rgba(59, 130, 246, 0.25);
}

/* Stats bar */
.stats-bar {
  display: flex;
  gap: 8px;
  justify-content: center;
  flex-wrap: wrap;
  margin-bottom: 32px;
  padding: 0 20px;
}

.stat {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  background: white;
  border-radius: 20px;
  font-size: 13px;
  border: 1px solid #e2e8f0;
}

.stat i {
  font-size: 14px;
}

.stat-count {
  font-weight: 700;
  color: #1e293b;
}

.stat-label {
  color: #64748b;
}

/* Sections */
.sections {
  padding: 0 4px;
}

.section {
  margin-bottom: 36px;
}

.section-header {
  display: flex;
  align-items: center;
  gap: 14px;
  margin-bottom: 14px;
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

.section-head-text {
  flex: 1;
  min-width: 0;
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

.section-count {
  font-size: 12px;
  font-weight: 600;
  color: #94a3b8;
  background: #f1f5f9;
  padding: 4px 10px;
  border-radius: 20px;
  flex-shrink: 0;
}

/* Articles grid */
.articles-grid {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.article-card {
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

.article-card:hover {
  border-color: #e2e8f0;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
  transform: translateX(4px);
}

.article-icon {
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

.article-body {
  flex: 1;
  min-width: 0;
}

.article-title-row {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.article-title {
  font-size: 15px;
  font-weight: 600;
  color: #1e293b;
  margin: 0;
  line-height: 1.4;
}

.article-type-tag {
  font-size: 10px;
  font-weight: 600;
  flex-shrink: 0;
}

.article-meta {
  display: flex;
  gap: 12px;
  font-size: 12px;
  color: #94a3b8;
  margin-top: 4px;
}

.article-meta span {
  display: flex;
  align-items: center;
  gap: 4px;
}

.article-meta i {
  font-size: 11px;
}

.article-arrow {
  color: #cbd5e1;
  font-size: 12px;
  flex-shrink: 0;
  transition: color 0.15s;
}

.article-card:hover .article-arrow {
  color: #3b82f6;
}

/* Responsive */
@media (max-width: 640px) {
  .hero-title {
    font-size: 24px;
  }

  .type-filter {
    width: 100%;
  }

  .type-btn {
    flex: 1;
    padding: 8px 12px;
    font-size: 13px;
  }

  .stats-bar {
    gap: 6px;
  }

  .stat {
    padding: 4px 10px;
    font-size: 12px;
  }

  .article-card {
    padding: 12px 14px;
  }

  .article-title {
    font-size: 14px;
  }
}
</style>

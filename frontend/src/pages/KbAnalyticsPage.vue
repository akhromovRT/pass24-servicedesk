<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import Button from 'primevue/button'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Tag from 'primevue/tag'
import { api } from '../api/client'

interface Totals {
  views: number
  helpful_count: number
  not_helpful_count: number
  helpful_ratio: number | null
  ticket_created_from_article: number
}

interface TopHelpfulRow {
  article_id: string
  title: string
  slug: string
  helpful_count: number
  not_helpful_count: number
  helpful_ratio: number | null
}

interface UnderperformingRow {
  article_id: string
  title: string
  slug: string
  views_count: number
  helpful_count: number
  not_helpful_count: number
  helpful_ratio: number | null
  ticket_anyway_count: number
}

interface DeflectionStats {
  totals: Totals
  top_helpful: TopHelpfulRow[]
  underperforming: UnderperformingRow[]
}

const router = useRouter()
const stats = ref<DeflectionStats | null>(null)
const loading = ref(true)
const error = ref('')

async function load() {
  loading.value = true
  error.value = ''
  try {
    stats.value = await api.get<DeflectionStats>('/knowledge/stats/deflection')
  } catch (e: any) {
    error.value = e.message || 'Не удалось загрузить статистику'
  } finally {
    loading.value = false
  }
}

// «Deflection Rate» — показывает сколько людей НЕ создали тикет после просмотра
// Формула: helpful_count / (helpful_count + ticket_created_from_article)
// Это приближение: мы знаем сколько ПОМЕТИЛИ «помогла» vs сколько создали тикет «из статьи»
const deflectionRate = computed(() => {
  if (!stats.value) return null
  const t = stats.value.totals
  const denominator = t.helpful_count + t.ticket_created_from_article
  if (denominator === 0) return null
  return t.helpful_count / denominator
})

function formatRatio(v: number | null): string {
  if (v === null) return '—'
  return `${Math.round(v * 100)}%`
}

function openArticle(slug: string) {
  router.push(`/knowledge/${slug}`)
}

function ratioSeverity(ratio: number | null): string {
  if (ratio === null) return 'secondary'
  if (ratio >= 0.7) return 'success'
  if (ratio >= 0.5) return 'warn'
  return 'danger'
}

onMounted(load)
</script>

<template>
  <div class="kb-analytics">
    <div class="page-header">
      <h1>Аналитика базы знаний</h1>
      <Button
        label="Обновить"
        icon="pi pi-refresh"
        severity="secondary"
        outlined
        size="small"
        :loading="loading"
        @click="load"
      />
    </div>

    <div v-if="loading && !stats" class="loading">
      <i class="pi pi-spin pi-spinner" style="font-size: 2rem; color: #94a3b8" />
    </div>

    <div v-else-if="error" class="error-msg">{{ error }}</div>

    <template v-else-if="stats">
      <!-- Summary cards -->
      <div class="stat-grid">
        <div class="stat-card">
          <div class="stat-label">Просмотры статей</div>
          <div class="stat-value">{{ stats.totals.views.toLocaleString('ru-RU') }}</div>
          <div class="stat-sub">всего за период</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">Helpful ratio</div>
          <div class="stat-value">
            {{ formatRatio(stats.totals.helpful_ratio) }}
          </div>
          <div class="stat-sub">
            👍 {{ stats.totals.helpful_count }} / 👎 {{ stats.totals.not_helpful_count }}
          </div>
        </div>
        <div class="stat-card">
          <div class="stat-label">Deflection Rate</div>
          <div class="stat-value" :class="{ good: deflectionRate !== null && deflectionRate >= 0.5 }">
            {{ formatRatio(deflectionRate) }}
          </div>
          <div class="stat-sub">решили без заявки</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">Заявок из статей</div>
          <div class="stat-value warn">{{ stats.totals.ticket_created_from_article }}</div>
          <div class="stat-sub">прочитали — и всё равно создали</div>
        </div>
      </div>

      <!-- Top helpful -->
      <div class="section">
        <h2 class="section-title">
          <i class="pi pi-thumbs-up" />
          Топ «помогающих» статей
        </h2>
        <p class="section-subtitle">
          Статьи с наибольшей долей 👍 (минимум 3 отзыва)
        </p>
        <div v-if="stats.top_helpful.length === 0" class="empty">
          Пока недостаточно данных — нужно минимум 3 отзыва на статью
        </div>
        <DataTable
          v-else
          :value="stats.top_helpful"
          :row-hover="true"
          size="small"
          class="analytics-table"
          @row-click="openArticle($event.data.slug)"
        >
          <Column field="title" header="Статья">
            <template #body="{ data }">
              <a class="article-link" @click.stop="openArticle(data.slug)">
                {{ data.title }}
              </a>
            </template>
          </Column>
          <Column header="Helpful ratio" style="width: 140px">
            <template #body="{ data }">
              <Tag
                :value="formatRatio(data.helpful_ratio)"
                :severity="ratioSeverity(data.helpful_ratio)"
              />
            </template>
          </Column>
          <Column header="👍 / 👎" style="width: 120px">
            <template #body="{ data }">
              <span class="thumbs">
                <span class="thumbs-up">{{ data.helpful_count }}</span> /
                <span class="thumbs-down">{{ data.not_helpful_count }}</span>
              </span>
            </template>
          </Column>
        </DataTable>
      </div>

      <!-- Underperforming -->
      <div class="section">
        <h2 class="section-title">
          <i class="pi pi-exclamation-triangle" style="color: #f59e0b" />
          Статьи, требующие внимания
        </h2>
        <p class="section-subtitle">
          Пользователи читали и всё равно создавали заявки → кандидаты на переписывание
        </p>
        <div v-if="stats.underperforming.length === 0" class="empty">
          Нет статей с заявками из них — это хороший знак!
        </div>
        <DataTable
          v-else
          :value="stats.underperforming"
          :row-hover="true"
          size="small"
          class="analytics-table"
        >
          <Column field="title" header="Статья">
            <template #body="{ data }">
              <a class="article-link" @click="openArticle(data.slug)">
                {{ data.title }}
              </a>
            </template>
          </Column>
          <Column header="Заявок" style="width: 90px">
            <template #body="{ data }">
              <span class="warn-num">{{ data.ticket_anyway_count }}</span>
            </template>
          </Column>
          <Column header="Просмотры" style="width: 100px">
            <template #body="{ data }">{{ data.views_count }}</template>
          </Column>
          <Column header="Helpful" style="width: 100px">
            <template #body="{ data }">
              <Tag
                v-if="data.helpful_ratio !== null"
                :value="formatRatio(data.helpful_ratio)"
                :severity="ratioSeverity(data.helpful_ratio)"
              />
              <span v-else class="no-data">—</span>
            </template>
          </Column>
        </DataTable>
      </div>
    </template>
  </div>
</template>

<style scoped>
.kb-analytics {
  display: flex;
  flex-direction: column;
  gap: 24px;
  max-width: 1100px;
  margin: 0 auto;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.page-header h1 {
  font-size: 1.5rem;
  font-weight: 700;
  margin: 0;
}

.loading,
.empty {
  display: flex;
  justify-content: center;
  padding: 40px 0;
  color: #94a3b8;
  font-size: 14px;
}

.error-msg {
  padding: 16px;
  background: #fef2f2;
  border: 1px solid #fecaca;
  border-radius: 8px;
  color: #dc2626;
}

/* Summary grid */
.stat-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 12px;
}

.stat-card {
  background: white;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  padding: 16px 18px;
}

.stat-label {
  font-size: 12px;
  font-weight: 600;
  color: #64748b;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.stat-value {
  font-size: 28px;
  font-weight: 700;
  color: #0f172a;
  margin-top: 4px;
  line-height: 1.2;
}

.stat-value.good {
  color: #16a34a;
}

.stat-value.warn {
  color: #dc2626;
}

.stat-sub {
  font-size: 12px;
  color: #94a3b8;
  margin-top: 4px;
}

/* Section */
.section {
  background: white;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  padding: 20px 22px;
}

.section-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 16px;
  font-weight: 700;
  color: #0f172a;
  margin: 0 0 4px;
}

.section-title i {
  font-size: 15px;
  color: #3b82f6;
}

.section-subtitle {
  font-size: 13px;
  color: #64748b;
  margin: 0 0 14px;
}

.article-link {
  color: #3b82f6;
  cursor: pointer;
  text-decoration: none;
}

.article-link:hover {
  text-decoration: underline;
}

.thumbs {
  font-size: 13px;
  color: #64748b;
}

.thumbs-up {
  color: #16a34a;
  font-weight: 600;
}

.thumbs-down {
  color: #dc2626;
  font-weight: 600;
}

.warn-num {
  font-weight: 700;
  color: #dc2626;
}

.no-data {
  color: #cbd5e1;
  font-size: 13px;
}

.analytics-table :deep(.p-datatable-tbody > tr) {
  cursor: pointer;
}

@media (max-width: 640px) {
  .stat-value {
    font-size: 22px;
  }
  .section {
    padding: 16px;
  }
}
</style>

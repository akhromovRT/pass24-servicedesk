<script setup lang="ts">
import { onMounted, ref, computed } from 'vue'
import Card from 'primevue/card'
import Select from 'primevue/select'
import { useToast } from 'primevue/usetoast'
import { api } from '../api/client'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { PieChart, BarChart, LineChart } from 'echarts/charts'
import {
  TitleComponent,
  TooltipComponent,
  LegendComponent,
  GridComponent,
} from 'echarts/components'
import VChart from 'vue-echarts'

use([
  CanvasRenderer,
  PieChart,
  BarChart,
  LineChart,
  TitleComponent,
  TooltipComponent,
  LegendComponent,
  GridComponent,
])

const toast = useToast()
const loading = ref(true)

interface Overview {
  total: number
  open: number
  resolved: number
  closed: number
  by_status: Record<string, number>
  by_priority: Record<string, number>
  by_category: Record<string, number>
}

interface TimelinePoint {
  date: string
  count: number
}

interface SlaMetric {
  total: number
  avg_hours: number
  breached: number
  compliance_pct: number
}

interface SlaStats {
  response: SlaMetric
  resolution: SlaMetric
}

const overview = ref<Overview | null>(null)
const timeline = ref<TimelinePoint[]>([])
const sla = ref<SlaStats | null>(null)
const timelineDays = ref(30)

const daysOptions = [
  { label: '7 дней', value: 7 },
  { label: '30 дней', value: 30 },
  { label: '90 дней', value: 90 },
]

const statusLabels: Record<string, string> = {
  new: 'Новый',
  in_progress: 'В работе',
  waiting_for_user: 'Ожидает ответа',
  resolved: 'Решён',
  closed: 'Закрыт',
}

const priorityLabels: Record<string, string> = {
  low: 'Низкий',
  normal: 'Обычный',
  high: 'Высокий',
  critical: 'Критический',
}

const categoryLabels: Record<string, string> = {
  access: 'Доступ',
  pass: 'Пропуска',
  gate: 'Шлагбаум',
  notifications: 'Уведомления',
  general: 'Общее',
  other: 'Другое',
}

const statusColors: Record<string, string> = {
  new: '#3b82f6',
  in_progress: '#f59e0b',
  waiting_for_user: '#8b5cf6',
  resolved: '#10b981',
  closed: '#6b7280',
}

const priorityColors: Record<string, string> = {
  low: '#94a3b8',
  normal: '#3b82f6',
  high: '#f59e0b',
  critical: '#ef4444',
}

const statusChartOption = computed(() => {
  if (!overview.value) return {}
  const data = Object.entries(overview.value.by_status).map(([key, value]) => ({
    name: statusLabels[key] || key,
    value,
    itemStyle: { color: statusColors[key] || '#94a3b8' },
  }))
  return {
    tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
    series: [{
      type: 'pie',
      radius: ['40%', '70%'],
      label: { show: true, formatter: '{b}\n{c}' },
      data,
    }],
  }
})

const priorityChartOption = computed(() => {
  if (!overview.value) return {}
  const entries = Object.entries(overview.value.by_priority)
  return {
    tooltip: { trigger: 'axis' },
    xAxis: {
      type: 'category',
      data: entries.map(([k]) => priorityLabels[k] || k),
    },
    yAxis: { type: 'value', minInterval: 1 },
    series: [{
      type: 'bar',
      data: entries.map(([k, v]) => ({
        value: v,
        itemStyle: { color: priorityColors[k] || '#3b82f6' },
      })),
      barWidth: '50%',
    }],
  }
})

const categoryChartOption = computed(() => {
  if (!overview.value) return {}
  const entries = Object.entries(overview.value.by_category)
  return {
    tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
    series: [{
      type: 'pie',
      radius: '65%',
      label: { show: true, formatter: '{b}\n{c}' },
      data: entries.map(([k, v]) => ({
        name: categoryLabels[k] || k,
        value: v,
      })),
    }],
  }
})

const timelineChartOption = computed(() => {
  if (!timeline.value.length) return {}
  return {
    tooltip: { trigger: 'axis' },
    grid: { left: 40, right: 20, bottom: 30, top: 20 },
    xAxis: {
      type: 'category',
      data: timeline.value.map((p) => {
        const d = new Date(p.date)
        return `${d.getDate()}.${String(d.getMonth() + 1).padStart(2, '0')}`
      }),
      axisLabel: { rotate: 45 },
    },
    yAxis: { type: 'value', minInterval: 1 },
    series: [{
      type: 'line',
      data: timeline.value.map((p) => p.count),
      smooth: true,
      areaStyle: { opacity: 0.15 },
      itemStyle: { color: '#3b82f6' },
    }],
  }
})

async function loadData() {
  loading.value = true
  try {
    const [ov, tl, sl] = await Promise.all([
      api.get<Overview>('/stats/overview'),
      api.get<TimelinePoint[]>(`/stats/timeline?days=${timelineDays.value}`),
      api.get<SlaStats>('/stats/sla'),
    ])
    overview.value = ov
    timeline.value = tl
    sla.value = sl
  } catch (e: any) {
    toast.add({
      severity: 'error',
      summary: 'Ошибка',
      detail: e.message || 'Не удалось загрузить статистику',
      life: 4000,
    })
  } finally {
    loading.value = false
  }
}

function onDaysChange() {
  loadData()
}

onMounted(() => loadData())
</script>

<template>
  <div class="analytics-page">
    <h1>Аналитика</h1>

    <div v-if="loading" class="analytics-loading">
      <i class="pi pi-spin pi-spinner" style="font-size: 2rem" />
    </div>

    <template v-else-if="overview">
      <!-- Карточки-счётчики -->
      <div class="stats-cards">
        <Card class="stat-card">
          <template #content>
            <div class="stat-value">{{ overview.total }}</div>
            <div class="stat-label">Всего заявок</div>
          </template>
        </Card>
        <Card class="stat-card stat-open">
          <template #content>
            <div class="stat-value">{{ overview.open }}</div>
            <div class="stat-label">Открытых</div>
          </template>
        </Card>
        <Card class="stat-card stat-resolved">
          <template #content>
            <div class="stat-value">{{ overview.resolved }}</div>
            <div class="stat-label">Решённых</div>
          </template>
        </Card>
        <Card class="stat-card stat-closed">
          <template #content>
            <div class="stat-value">{{ overview.closed }}</div>
            <div class="stat-label">Закрытых</div>
          </template>
        </Card>
      </div>

      <!-- SLA -->
      <div v-if="sla" class="stats-cards">
        <Card class="stat-card">
          <template #content>
            <div class="stat-value">{{ sla.response.avg_hours }}ч</div>
            <div class="stat-label">Среднее время ответа</div>
          </template>
        </Card>
        <Card class="stat-card">
          <template #content>
            <div class="stat-value" :class="sla.response.compliance_pct >= 90 ? 'stat-resolved' : 'stat-open'">
              {{ sla.response.compliance_pct }}%
            </div>
            <div class="stat-label">SLA ответ ({{ sla.response.breached }} нарушений)</div>
          </template>
        </Card>
        <Card class="stat-card">
          <template #content>
            <div class="stat-value">{{ sla.resolution.avg_hours }}ч</div>
            <div class="stat-label">Среднее время решения</div>
          </template>
        </Card>
        <Card class="stat-card">
          <template #content>
            <div class="stat-value" :class="sla.resolution.compliance_pct >= 90 ? 'stat-resolved' : 'stat-open'">
              {{ sla.resolution.compliance_pct }}%
            </div>
            <div class="stat-label">SLA решение ({{ sla.resolution.breached }} нарушений)</div>
          </template>
        </Card>
      </div>

      <!-- Графики -->
      <div class="charts-grid">
        <Card class="chart-card">
          <template #title>По статусам</template>
          <template #content>
            <VChart :option="statusChartOption" style="height: 280px" autoresize />
          </template>
        </Card>

        <Card class="chart-card">
          <template #title>По приоритетам</template>
          <template #content>
            <VChart :option="priorityChartOption" style="height: 280px" autoresize />
          </template>
        </Card>

        <Card class="chart-card">
          <template #title>По категориям</template>
          <template #content>
            <VChart :option="categoryChartOption" style="height: 280px" autoresize />
          </template>
        </Card>

        <Card class="chart-card">
          <template #title>
            <div class="timeline-header">
              <span>Заявки по дням</span>
              <Select
                v-model="timelineDays"
                :options="daysOptions"
                option-label="label"
                option-value="value"
                class="days-select"
                @change="onDaysChange"
              />
            </div>
          </template>
          <template #content>
            <VChart :option="timelineChartOption" style="height: 280px" autoresize />
          </template>
        </Card>
      </div>
    </template>
  </div>
</template>

<style scoped>
.analytics-page {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.analytics-page h1 {
  font-size: 1.5rem;
  font-weight: 700;
}

.analytics-loading {
  display: flex;
  justify-content: center;
  padding: 60px 0;
}

.stats-cards {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
}

.stat-card {
  text-align: center;
}

.stat-value {
  font-size: 2rem;
  font-weight: 700;
  color: #1e293b;
}

.stat-open .stat-value { color: #f59e0b; }
.stat-resolved .stat-value { color: #10b981; }
.stat-closed .stat-value { color: #6b7280; }

.stat-label {
  font-size: 0.875rem;
  color: #64748b;
  margin-top: 4px;
}

.charts-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 16px;
}

.chart-card {
  width: 100%;
}

.timeline-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.days-select {
  width: 130px;
}

@media (max-width: 768px) {
  .stats-cards {
    grid-template-columns: repeat(2, 1fr);
  }
  .charts-grid {
    grid-template-columns: 1fr;
  }
}
</style>

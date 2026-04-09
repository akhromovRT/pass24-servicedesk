<script setup lang="ts">
import { onMounted, ref, computed } from 'vue'
import Card from 'primevue/card'
import { useToast } from 'primevue/usetoast'
import { api } from '../api/client'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { PieChart, BarChart } from 'echarts/charts'
import {
  TitleComponent,
  TooltipComponent,
  LegendComponent,
  GridComponent,
} from 'echarts/components'
import VChart from 'vue-echarts'

use([CanvasRenderer, PieChart, BarChart, TitleComponent, TooltipComponent, LegendComponent, GridComponent])

const toast = useToast()

interface Analytics {
  total_projects: number
  active_projects: number
  completed_projects: number
  on_hold_projects: number
  avg_duration_days: number | null
  on_time_rate: number | null
  by_type: Record<string, number>
  by_status: Record<string, number>
  open_risks_count: number
  pending_approvals_count: number
}

const data = ref<Analytics | null>(null)
const loading = ref(true)

const typeLabels: Record<string, string> = {
  residential: 'ЖК',
  commercial: 'БЦ',
  cameras_only: 'Камеры',
  large_construction: 'Большая стройка',
}

const statusLabels: Record<string, string> = {
  draft: 'Черновик',
  planning: 'Планирование',
  in_progress: 'В работе',
  on_hold: 'На паузе',
  completed: 'Завершён',
  cancelled: 'Отменён',
}

const statusColors: Record<string, string> = {
  draft: '#94a3b8',
  planning: '#3b82f6',
  in_progress: '#f59e0b',
  on_hold: '#8b5cf6',
  completed: '#10b981',
  cancelled: '#ef4444',
}

async function loadAnalytics() {
  loading.value = true
  try {
    data.value = await api.get<Analytics>('/projects/analytics')
  } catch (e: any) {
    toast.add({ severity: 'error', summary: 'Ошибка', detail: e.message, life: 4000 })
  } finally {
    loading.value = false
  }
}

const byTypeChart = computed(() => {
  if (!data.value) return {}
  const entries = Object.entries(data.value.by_type)
  return {
    tooltip: { trigger: 'item' },
    series: [{
      type: 'pie',
      radius: ['40%', '70%'],
      label: { formatter: '{b}: {c}' },
      data: entries.map(([k, v]) => ({
        name: typeLabels[k] || k,
        value: v,
      })),
    }],
  }
})

const byStatusChart = computed(() => {
  if (!data.value) return {}
  const entries = Object.entries(data.value.by_status)
  return {
    tooltip: { trigger: 'axis' },
    xAxis: {
      type: 'category',
      data: entries.map(([k]) => statusLabels[k] || k),
    },
    yAxis: { type: 'value' },
    series: [{
      type: 'bar',
      data: entries.map(([k, v]) => ({
        value: v,
        itemStyle: { color: statusColors[k] || '#94a3b8' },
      })),
      barMaxWidth: 40,
      borderRadius: [6, 6, 0, 0],
    }],
  }
})

onMounted(loadAnalytics)
</script>

<template>
  <div class="analytics-page">
    <h1 class="page-title">Аналитика проектов внедрения</h1>

    <div v-if="loading" class="loading-state">
      <i class="pi pi-spin pi-spinner" style="font-size: 2rem; color: #94a3b8"></i>
    </div>

    <template v-if="data">
      <!-- Summary cards -->
      <div class="stats-grid">
        <Card class="stat-card">
          <template #content>
            <div class="stat-value">{{ data.total_projects }}</div>
            <div class="stat-label">Всего проектов</div>
          </template>
        </Card>
        <Card class="stat-card">
          <template #content>
            <div class="stat-value" style="color: #f59e0b">{{ data.active_projects }}</div>
            <div class="stat-label">Активных</div>
          </template>
        </Card>
        <Card class="stat-card">
          <template #content>
            <div class="stat-value" style="color: #10b981">{{ data.completed_projects }}</div>
            <div class="stat-label">Завершённых</div>
          </template>
        </Card>
        <Card class="stat-card">
          <template #content>
            <div class="stat-value" style="color: #8b5cf6">{{ data.on_hold_projects }}</div>
            <div class="stat-label">На паузе</div>
          </template>
        </Card>
        <Card class="stat-card">
          <template #content>
            <div class="stat-value">{{ data.avg_duration_days ?? '—' }}</div>
            <div class="stat-label">Средняя длительность (дни)</div>
          </template>
        </Card>
        <Card class="stat-card">
          <template #content>
            <div class="stat-value" :style="{ color: (data.on_time_rate ?? 0) >= 80 ? '#10b981' : '#ef4444' }">
              {{ data.on_time_rate != null ? data.on_time_rate + '%' : '—' }}
            </div>
            <div class="stat-label">Вовремя</div>
          </template>
        </Card>
        <Card class="stat-card">
          <template #content>
            <div class="stat-value" style="color: #ef4444">{{ data.open_risks_count }}</div>
            <div class="stat-label">Открытых рисков</div>
          </template>
        </Card>
        <Card class="stat-card">
          <template #content>
            <div class="stat-value" style="color: #f59e0b">{{ data.pending_approvals_count }}</div>
            <div class="stat-label">Ожидают утверждения</div>
          </template>
        </Card>
      </div>

      <!-- Charts -->
      <div class="charts-grid">
        <Card class="chart-card">
          <template #title>Проекты по типам</template>
          <template #content>
            <VChart :option="byTypeChart" style="height: 300px" autoresize />
          </template>
        </Card>
        <Card class="chart-card">
          <template #title>Проекты по статусам</template>
          <template #content>
            <VChart :option="byStatusChart" style="height: 300px" autoresize />
          </template>
        </Card>
      </div>
    </template>
  </div>
</template>

<style scoped>
.analytics-page {
  padding: 24px;
  max-width: 1200px;
  margin: 0 auto;
}

.page-title {
  font-size: 22px;
  font-weight: 700;
  color: #0f172a;
  margin: 0 0 24px;
}

.loading-state {
  display: flex;
  justify-content: center;
  padding: 60px 0;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
  gap: 12px;
  margin-bottom: 24px;
}

.stat-card { text-align: center; }
.stat-value { font-size: 28px; font-weight: 700; color: #0f172a; }
.stat-label { font-size: 12px; color: #64748b; margin-top: 4px; }

.charts-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}

@media (max-width: 768px) {
  .charts-grid { grid-template-columns: 1fr; }
  .stats-grid { grid-template-columns: repeat(2, 1fr); }
}
</style>

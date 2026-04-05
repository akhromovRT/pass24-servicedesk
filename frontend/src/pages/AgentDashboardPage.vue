<script setup lang="ts">
import { ref, onMounted } from 'vue'
import Card from 'primevue/card'
import Button from 'primevue/button'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import { api } from '../api/client'
import { useAuthStore } from '../stores/auth'

interface MyStats {
  assigned_total: number
  open: number
  resolved_30d: number
  avg_csat: number | null
}

interface AgentRow {
  id: string
  full_name: string
  email: string
  assigned: number
  resolved: number
  avg_csat: number | null
  csat_count: number
  avg_resolve_hours: number
}

const auth = useAuthStore()
const myStats = ref<MyStats | null>(null)
const agents = ref<AgentRow[]>([])
const loading = ref(true)

async function load() {
  loading.value = true
  try {
    const [mine, all] = await Promise.all([
      api.get<MyStats>('/tickets/dashboard/me'),
      api.get<AgentRow[]>('/stats/agents'),
    ])
    myStats.value = mine
    agents.value = all
  } finally {
    loading.value = false
  }
}

function formatCsat(v: number | null): string {
  if (v === null) return '—'
  return `${v.toFixed(1)} / 5.0`
}

function exportCsv() {
  const token = localStorage.getItem('access_token')
  const url = `/tickets/export.csv`
  // Открываем через fetch чтобы добавить токен, затем download blob
  fetch(url, { headers: { Authorization: `Bearer ${token}` } })
    .then(r => r.blob())
    .then(blob => {
      const u = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = u
      a.download = `tickets-${new Date().toISOString().slice(0, 10)}.csv`
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(u)
    })
}

onMounted(load)
</script>

<template>
  <div class="dashboard-page">
    <div class="page-header">
      <h1>Дашборд агента</h1>
      <Button label="Экспорт CSV" icon="pi pi-download" severity="secondary" outlined @click="exportCsv" />
    </div>

    <div v-if="loading" class="loading">
      <i class="pi pi-spin pi-spinner" style="font-size: 2rem" />
    </div>

    <template v-else-if="myStats">
      <!-- Мои карточки -->
      <div class="stats-grid">
        <Card class="stat-card">
          <template #content>
            <div class="stat-icon"><i class="pi pi-user" /></div>
            <div class="stat-value">{{ myStats.assigned_total }}</div>
            <div class="stat-label">Назначено мне</div>
          </template>
        </Card>
        <Card class="stat-card stat-warn">
          <template #content>
            <div class="stat-icon"><i class="pi pi-inbox" /></div>
            <div class="stat-value">{{ myStats.open }}</div>
            <div class="stat-label">В работе</div>
          </template>
        </Card>
        <Card class="stat-card stat-success">
          <template #content>
            <div class="stat-icon"><i class="pi pi-check-circle" /></div>
            <div class="stat-value">{{ myStats.resolved_30d }}</div>
            <div class="stat-label">Решено за 30 дней</div>
          </template>
        </Card>
        <Card class="stat-card stat-primary">
          <template #content>
            <div class="stat-icon"><i class="pi pi-star" /></div>
            <div class="stat-value">{{ formatCsat(myStats.avg_csat) }}</div>
            <div class="stat-label">Мой CSAT</div>
          </template>
        </Card>
      </div>

      <!-- Таблица агентов -->
      <Card class="agents-card">
        <template #title>Все агенты</template>
        <template #content>
          <DataTable :value="agents" striped-rows size="small">
            <Column field="full_name" header="Агент">
              <template #body="{ data }">
                <strong v-if="data.id === auth.user?.id">{{ data.full_name }} (вы)</strong>
                <span v-else>{{ data.full_name }}</span>
              </template>
            </Column>
            <Column field="assigned" header="Назначено" style="width: 120px" />
            <Column field="resolved" header="Решено" style="width: 110px" />
            <Column field="avg_resolve_hours" header="Среднее время" style="width: 140px">
              <template #body="{ data }">
                {{ data.avg_resolve_hours > 0 ? `${data.avg_resolve_hours} ч` : '—' }}
              </template>
            </Column>
            <Column field="avg_csat" header="CSAT" style="width: 140px">
              <template #body="{ data }">
                <span v-if="data.avg_csat">
                  {{ formatCsat(data.avg_csat) }}
                  <small style="color:#94a3b8">({{ data.csat_count }})</small>
                </span>
                <span v-else style="color:#94a3b8">—</span>
              </template>
            </Column>
          </DataTable>
        </template>
      </Card>
    </template>
  </div>
</template>

<style scoped>
.dashboard-page { display: flex; flex-direction: column; gap: 20px; }
.page-header { display: flex; justify-content: space-between; align-items: center; }
.page-header h1 { font-size: 1.5rem; font-weight: 700; margin: 0; }
.loading { display: flex; justify-content: center; padding: 60px 0; }

.stats-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; }
@media (max-width: 768px) { .stats-grid { grid-template-columns: repeat(2, 1fr); } }

.stat-card { text-align: center; position: relative; overflow: hidden; }
.stat-icon { font-size: 24px; color: #3b82f6; margin-bottom: 8px; }
.stat-value { font-size: 2rem; font-weight: 700; color: #1e293b; }
.stat-label { font-size: 0.875rem; color: #64748b; margin-top: 4px; }
.stat-warn .stat-icon { color: #f59e0b; }
.stat-success .stat-icon { color: #10b981; }
.stat-primary .stat-icon { color: #8b5cf6; }

.agents-card { width: 100%; }
</style>

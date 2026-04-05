<script setup lang="ts">
import { onMounted, ref, watch, computed } from 'vue'
import { useRouter } from 'vue-router'
import Button from 'primevue/button'
import MultiSelect from 'primevue/multiselect'
import Paginator from 'primevue/paginator'
import InputText from 'primevue/inputtext'
import IconField from 'primevue/iconfield'
import InputIcon from 'primevue/inputicon'
import { useToast } from 'primevue/usetoast'
import { useTicketsStore } from '../stores/tickets'
import { useAuthStore } from '../stores/auth'
import type { Ticket } from '../types'

const router = useRouter()
const toast = useToast()
const store = useTicketsStore()
const auth = useAuthStore()

const isStaff = computed(() => auth.user?.role === 'support_agent' || auth.user?.role === 'admin')

// ─── Filters & View ─────────────────────────────────────────────
const activeView = ref<string>('all')
const statusFilter = ref<string[]>([])
const categoryFilter = ref<string[]>([])
const searchQuery = ref('')
const showAdvancedFilters = ref(false)
let searchDebounceTimer: ReturnType<typeof setTimeout> | null = null

// ─── Views (tabs) ────────────────────────────────────────────────
const views = computed(() => {
  const base = [
    { id: 'all', label: 'Все', icon: 'pi pi-list' },
    { id: 'open', label: 'Открытые', icon: 'pi pi-inbox', count: store.stats.open },
    { id: 'urgent', label: 'Срочные', icon: 'pi pi-exclamation-triangle', count: store.stats.urgent, severity: 'danger' },
    { id: 'overdue', label: 'Просрочено', icon: 'pi pi-clock', count: store.stats.overdue, severity: 'danger' },
    { id: 'waiting', label: 'Ждут ответа', icon: 'pi pi-hourglass', count: store.stats.waiting, severity: 'warn' },
    { id: 'closed', label: 'Закрытые', icon: 'pi pi-check-circle' },
  ]
  return base
})

// ─── Options ─────────────────────────────────────────────────────
const statusOptions = [
  { label: 'Новый', value: 'new' },
  { label: 'В работе', value: 'in_progress' },
  { label: 'Ожидает ответа', value: 'waiting_for_user' },
  { label: 'Решён', value: 'resolved' },
  { label: 'Закрыт', value: 'closed' },
]

const categoryOptions = [
  { label: 'Регистрация и вход', value: 'registration' },
  { label: 'Пропуска и доступ', value: 'passes' },
  { label: 'Распознавание номеров', value: 'recognition' },
  { label: 'Работа приложения', value: 'app_issues' },
  { label: 'Объекты', value: 'objects' },
  { label: 'Доверенные лица', value: 'trusted_persons' },
  { label: 'Оборудование', value: 'equipment_issues' },
  { label: 'Консультация', value: 'consultation' },
  { label: 'Предложение', value: 'feature_request' },
  { label: 'Другое', value: 'other' },
]

const statusLabels: Record<string, string> = {
  new: 'Новый', in_progress: 'В работе', waiting_for_user: 'Ожидает', resolved: 'Решён', closed: 'Закрыт',
}
const statusColors: Record<string, string> = {
  new: '#3b82f6', in_progress: '#f59e0b', waiting_for_user: '#8b5cf6', resolved: '#10b981', closed: '#64748b',
}
const priorityColors: Record<string, string> = {
  critical: '#dc2626', high: '#ea580c', normal: '#2563eb', low: '#64748b',
}
const priorityLabels: Record<string, string> = {
  critical: 'Критический', high: 'Высокий', normal: 'Обычный', low: 'Низкий',
}
const categoryLabels: Record<string, string> = {
  registration: 'Регистрация', passes: 'Пропуска', recognition: 'Распознавание',
  app_issues: 'Приложение', objects: 'Объекты', trusted_persons: 'Доверенные',
  equipment_issues: 'Оборудование', consultation: 'Консультация', feature_request: 'Предложение', other: 'Другое',
}
const productLabels: Record<string, string> = {
  pass24_online: 'PASS24.online', mobile_app: 'Мобильное приложение', pass24_key: 'PASS24.Key',
  pass24_control: 'PASS24.control', pass24_auto: 'PASS24.auto',
  equipment: 'Оборудование', integration: 'Интеграция', other: 'Другое',
}

// ─── SLA calculations ───────────────────────────────────────────
function slaProgress(ticket: Ticket): { pct: number; remaining: string; breach: boolean } {
  if (!ticket.sla_response_hours || !ticket.created_at) {
    return { pct: 0, remaining: '', breach: false }
  }
  // Если тикет решён — SLA done
  if (ticket.status === 'resolved' || ticket.status === 'closed') {
    return { pct: 100, remaining: 'завершено', breach: false }
  }
  const now = Date.now()
  const created = new Date(ticket.created_at).getTime()
  const pauseMs = (ticket.sla_total_pause_seconds || 0) * 1000
  const totalHours = ticket.sla_resolve_hours || 24
  const deadline = created + totalHours * 3600 * 1000 + pauseMs
  const totalMs = totalHours * 3600 * 1000
  const elapsedMs = now - created - pauseMs
  const pct = Math.min(100, Math.round((elapsedMs / totalMs) * 100))
  const remainingMs = deadline - now
  const breach = remainingMs < 0 || ticket.sla_breached

  if (breach) {
    const overMs = Math.abs(remainingMs)
    const overH = Math.floor(overMs / 3600000)
    const overM = Math.floor((overMs % 3600000) / 60000)
    return { pct: 100, remaining: `-${overH}ч ${overM}м`, breach: true }
  }
  const h = Math.floor(remainingMs / 3600000)
  const m = Math.floor((remainingMs % 3600000) / 60000)
  const remaining = h > 0 ? `${h}ч ${m}м` : `${m}м`
  return { pct, remaining, breach: false }
}

function slaColor(pct: number, breach: boolean): string {
  if (breach) return '#dc2626'
  if (pct > 75) return '#ea580c'
  if (pct > 50) return '#f59e0b'
  return '#10b981'
}

function formatDate(dateStr: string): string {
  const d = new Date(dateStr)
  const diffMs = Date.now() - d.getTime()
  const diffH = diffMs / 3600000
  if (diffH < 1) return 'только что'
  if (diffH < 24) return `${Math.floor(diffH)} ч назад`
  if (diffH < 48) return 'вчера'
  return new Intl.DateTimeFormat('ru-RU', { day: 'numeric', month: 'short' }).format(d)
}

// ─── Actions ─────────────────────────────────────────────────────
async function loadTickets(p?: number) {
  try {
    await store.fetchTickets(p, {
      status: statusFilter.value.length ? statusFilter.value : undefined,
      category: categoryFilter.value.length ? categoryFilter.value : undefined,
      q: searchQuery.value.trim() || undefined,
      view: activeView.value !== 'all' ? activeView.value : undefined,
    })
  } catch (e: any) {
    toast.add({ severity: 'error', summary: 'Ошибка', detail: e.message || 'Не удалось загрузить', life: 4000 })
  }
}

function selectView(viewId: string) {
  activeView.value = viewId
  statusFilter.value = []
  categoryFilter.value = []
  loadTickets(1)
}

function onPageChange(event: { page: number }) { loadTickets(event.page + 1) }

watch(searchQuery, () => {
  if (searchDebounceTimer) clearTimeout(searchDebounceTimer)
  searchDebounceTimer = setTimeout(() => loadTickets(1), 300)
})

function openTicket(id: string) { router.push(`/tickets/${id}`) }

onMounted(() => {
  store.fetchStats()
  loadTickets(1)
})
</script>

<template>
  <div class="tickets-page">
    <!-- Header -->
    <div class="page-header">
      <div>
        <h1 class="page-title">Заявки</h1>
        <p class="page-subtitle">{{ store.total }} всего · {{ store.stats.open }} открытых</p>
      </div>
      <Button label="Создать заявку" icon="pi pi-plus" @click="router.push('/tickets/create')" />
    </div>

    <!-- Tabs -->
    <div class="views-tabs">
      <button
        v-for="view in views"
        :key="view.id"
        class="view-tab"
        :class="{ active: activeView === view.id, danger: view.severity === 'danger', warn: view.severity === 'warn' }"
        @click="selectView(view.id)"
      >
        <i :class="view.icon" />
        <span>{{ view.label }}</span>
        <span v-if="view.count !== undefined && view.count > 0" class="view-count">{{ view.count }}</span>
      </button>
    </div>

    <!-- Search + Advanced filters toggle -->
    <div class="toolbar">
      <IconField class="search-field">
        <InputIcon class="pi pi-search" />
        <InputText v-model="searchQuery" placeholder="Поиск по теме, описанию, email, объекту..." class="search-input" fluid />
      </IconField>
      <Button
        :label="showAdvancedFilters ? 'Скрыть фильтры' : 'Фильтры'"
        :icon="showAdvancedFilters ? 'pi pi-filter-slash' : 'pi pi-filter'"
        severity="secondary"
        outlined
        @click="showAdvancedFilters = !showAdvancedFilters"
      />
    </div>

    <!-- Advanced filters -->
    <div v-if="showAdvancedFilters" class="advanced-filters">
      <MultiSelect
        v-model="statusFilter"
        :options="statusOptions"
        option-label="label" option-value="value"
        placeholder="Статус" :max-selected-labels="2" selected-items-label="{0} статусов"
        class="filter-select"
        @change="loadTickets(1)"
      />
      <MultiSelect
        v-model="categoryFilter"
        :options="categoryOptions"
        option-label="label" option-value="value"
        placeholder="Категория" :max-selected-labels="2" selected-items-label="{0} категорий"
        class="filter-select"
        @change="loadTickets(1)"
      />
      <Button
        v-if="statusFilter.length || categoryFilter.length"
        label="Сбросить"
        icon="pi pi-times"
        text severity="secondary" size="small"
        @click="statusFilter = []; categoryFilter = []; loadTickets(1)"
      />
    </div>

    <!-- Ticket list -->
    <div v-if="store.loading" class="state-loading">
      <i class="pi pi-spin pi-spinner" style="font-size: 24px; color: #94a3b8;" />
    </div>

    <div v-else-if="store.tickets.length === 0" class="state-empty">
      <i class="pi pi-inbox" style="font-size: 40px; color: #cbd5e1; margin-bottom: 12px;" />
      <p>{{ searchQuery || statusFilter.length || categoryFilter.length ? 'Ничего не найдено' : 'Нет заявок' }}</p>
      <Button
        v-if="searchQuery || statusFilter.length || categoryFilter.length"
        label="Сбросить фильтры" text severity="secondary" size="small"
        @click="searchQuery = ''; statusFilter = []; categoryFilter = []; activeView = 'all'; loadTickets(1)"
      />
      <Button v-else label="Создать первую заявку" icon="pi pi-plus" @click="router.push('/tickets/create')" />
    </div>

    <div v-else class="ticket-list">
      <article
        v-for="ticket in store.tickets"
        :key="ticket.id"
        class="ticket-row"
        :class="{ 'row-urgent': ticket.urgent, 'row-unread': isStaff && ticket.has_unread_reply }"
        :style="{ '--priority-color': priorityColors[ticket.priority] || '#64748b' }"
        @click="openTicket(ticket.id)"
      >
        <div class="row-priority-bar" />

        <div class="row-main">
          <div class="row-header">
            <span v-if="isStaff && ticket.has_unread_reply" class="unread-dot" title="Новый ответ клиента" />
            <h3 class="row-title">{{ ticket.title }}</h3>
            <span v-if="ticket.urgent" class="badge-urgent" title="Срочная">●</span>
          </div>

          <div class="row-meta">
            <span class="meta-id">#{{ ticket.id.slice(0, 8).toUpperCase() }}</span>
            <span class="meta-sep">·</span>
            <span v-if="ticket.product" class="meta-item">
              <i class="pi pi-box" />{{ productLabels[ticket.product] || ticket.product }}
            </span>
            <span v-if="ticket.category" class="meta-sep">·</span>
            <span v-if="ticket.category" class="meta-item">{{ categoryLabels[ticket.category] || ticket.category }}</span>
            <span v-if="ticket.contact_name || ticket.contact_email" class="meta-sep">·</span>
            <span v-if="ticket.contact_name || ticket.contact_email" class="meta-item">
              <i class="pi pi-user" />{{ ticket.contact_name || ticket.contact_email }}
            </span>
            <span v-if="ticket.comments?.length" class="meta-sep">·</span>
            <span v-if="ticket.comments?.length" class="meta-item"><i class="pi pi-comment" />{{ ticket.comments.length }}</span>
            <span v-if="ticket.attachments?.length" class="meta-sep">·</span>
            <span v-if="ticket.attachments?.length" class="meta-item"><i class="pi pi-paperclip" />{{ ticket.attachments.length }}</span>
          </div>
        </div>

        <div class="row-right">
          <!-- SLA indicator -->
          <div v-if="ticket.status !== 'closed' && ticket.status !== 'resolved'" class="sla-widget">
            <div class="sla-bar-track">
              <div
                class="sla-bar-fill"
                :style="{ width: slaProgress(ticket).pct + '%', background: slaColor(slaProgress(ticket).pct, slaProgress(ticket).breach) }"
              />
            </div>
            <div class="sla-remaining" :style="{ color: slaColor(slaProgress(ticket).pct, slaProgress(ticket).breach) }">
              <i :class="slaProgress(ticket).breach ? 'pi pi-exclamation-circle' : 'pi pi-clock'" />
              {{ slaProgress(ticket).remaining }}
            </div>
          </div>
          <div v-else class="sla-widget done">
            <i class="pi pi-check-circle" /> решено
          </div>

          <!-- Status + Priority -->
          <div class="row-badges">
            <span class="pill pill-status" :style="{ '--c': statusColors[ticket.status] }">
              {{ statusLabels[ticket.status] || ticket.status }}
            </span>
            <span class="pill pill-priority" :style="{ '--c': priorityColors[ticket.priority] || '#64748b' }">
              {{ priorityLabels[ticket.priority] || ticket.priority }}
            </span>
          </div>

          <div class="row-date">{{ formatDate(ticket.created_at) }}</div>
        </div>
      </article>
    </div>

    <Paginator
      v-if="store.total > 20"
      :rows="20"
      :total-records="store.total"
      :first="(store.page - 1) * 20"
      @page="onPageChange"
    />
  </div>
</template>

<style scoped>
.tickets-page { display: flex; flex-direction: column; gap: 16px; }

/* Header */
.page-header { display: flex; justify-content: space-between; align-items: flex-start; gap: 16px; }
.page-title { font-size: 24px; font-weight: 700; color: #0f172a; margin: 0; letter-spacing: -0.02em; }
.page-subtitle { font-size: 13px; color: #64748b; margin: 2px 0 0; }

/* Tabs */
.views-tabs {
  display: flex; gap: 2px; background: #f1f5f9; padding: 4px; border-radius: 10px;
  overflow-x: auto; scrollbar-width: none;
}
.views-tabs::-webkit-scrollbar { display: none; }

.view-tab {
  display: flex; align-items: center; gap: 6px; padding: 8px 14px;
  background: transparent; border: none; border-radius: 8px; cursor: pointer;
  font-size: 13px; font-weight: 500; color: #64748b; white-space: nowrap;
  transition: all 0.15s;
}
.view-tab:hover { color: #1e293b; background: #e2e8f0; }
.view-tab.active { background: white; color: #0f172a; box-shadow: 0 1px 3px rgba(0,0,0,0.08); font-weight: 600; }
.view-tab.active.danger { color: #dc2626; }
.view-tab.active.warn { color: #d97706; }
.view-tab i { font-size: 12px; }
.view-count {
  display: inline-flex; align-items: center; justify-content: center; min-width: 20px; height: 18px;
  padding: 0 6px; border-radius: 9px; background: #e2e8f0; color: #475569; font-size: 11px; font-weight: 700;
}
.view-tab.active .view-count { background: #3b82f6; color: white; }
.view-tab.active.danger .view-count { background: #dc2626; }
.view-tab.active.warn .view-count { background: #d97706; }

/* Toolbar */
.toolbar { display: flex; gap: 10px; align-items: center; }
.search-field { flex: 1; }
.search-input :deep(input) { border-radius: 10px; padding: 10px 14px 10px 38px; }

/* Advanced filters */
.advanced-filters { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }
.filter-select { min-width: 200px; }

/* States */
.state-loading, .state-empty {
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  gap: 10px; padding: 60px 20px; color: #94a3b8; text-align: center;
}
.state-empty p { margin: 0; font-size: 14px; }

/* Ticket list */
.ticket-list { display: flex; flex-direction: column; gap: 6px; }

.ticket-row {
  position: relative; display: flex; align-items: center; gap: 16px;
  padding: 14px 16px 14px 22px; background: white; border: 1px solid #e2e8f0;
  border-radius: 10px; cursor: pointer; transition: all 0.15s; overflow: hidden;
}
.ticket-row:hover { border-color: #cbd5e1; box-shadow: 0 2px 8px rgba(0,0,0,0.04); transform: translateY(-1px); }

.row-priority-bar {
  position: absolute; left: 0; top: 0; bottom: 0; width: 4px; background: var(--priority-color);
}

.ticket-row.row-urgent { background: linear-gradient(to right, #fef2f2, white); }
.ticket-row.row-unread { background: linear-gradient(to right, #eff6ff, white); border-color: #bfdbfe; }
.ticket-row.row-unread .row-title { font-weight: 700; }

.row-main { flex: 1; min-width: 0; }
.row-header { display: flex; align-items: center; gap: 8px; margin-bottom: 4px; }
.unread-dot { width: 8px; height: 8px; background: #3b82f6; border-radius: 50%; flex-shrink: 0; }
.row-title {
  font-size: 14px; font-weight: 600; color: #0f172a; margin: 0;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.badge-urgent { color: #dc2626; font-size: 14px; animation: pulse 2s infinite; }
@keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.4; } }

.row-meta { display: flex; align-items: center; gap: 6px; font-size: 12px; color: #94a3b8; flex-wrap: wrap; }
.meta-id { font-family: 'SF Mono', monospace; color: #cbd5e1; }
.meta-sep { color: #e2e8f0; }
.meta-item { display: inline-flex; align-items: center; gap: 4px; color: #64748b; }
.meta-item i { font-size: 11px; }

.row-right { display: flex; flex-direction: column; align-items: flex-end; gap: 6px; flex-shrink: 0; }

/* SLA widget */
.sla-widget { display: flex; flex-direction: column; align-items: flex-end; gap: 3px; min-width: 110px; }
.sla-widget.done { color: #10b981; font-size: 12px; font-weight: 500; }
.sla-widget.done i { margin-right: 4px; }
.sla-bar-track { width: 100%; height: 4px; background: #f1f5f9; border-radius: 2px; overflow: hidden; }
.sla-bar-fill { height: 100%; transition: width 0.3s, background 0.3s; }
.sla-remaining { font-size: 11px; font-weight: 600; display: flex; align-items: center; gap: 4px; }
.sla-remaining i { font-size: 10px; }

/* Pills */
.row-badges { display: flex; gap: 4px; }
.pill {
  display: inline-flex; align-items: center; padding: 3px 8px; border-radius: 6px;
  font-size: 11px; font-weight: 600; background: color-mix(in srgb, var(--c) 12%, white);
  color: var(--c); border: 1px solid color-mix(in srgb, var(--c) 25%, white);
}

.row-date { font-size: 11px; color: #94a3b8; }

/* Responsive */
@media (max-width: 768px) {
  .page-header { flex-direction: column; align-items: stretch; }
  .views-tabs { gap: 4px; }
  .view-tab { padding: 8px 10px; font-size: 12px; }

  .ticket-row { flex-direction: column; align-items: flex-start; gap: 10px; padding: 14px 14px 14px 20px; }
  .row-right { flex-direction: row; align-items: center; width: 100%; justify-content: space-between; flex-wrap: wrap; }
  .sla-widget { min-width: 90px; }
}
</style>

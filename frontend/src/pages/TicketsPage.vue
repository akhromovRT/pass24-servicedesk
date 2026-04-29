<script setup lang="ts">
import { onMounted, onUnmounted, ref, watch, computed } from 'vue'
import { useRouter } from 'vue-router'
import Button from 'primevue/button'
import MultiSelect from 'primevue/multiselect'
import Paginator from 'primevue/paginator'
import InputText from 'primevue/inputtext'
import IconField from 'primevue/iconfield'
import InputIcon from 'primevue/inputicon'
import Dialog from 'primevue/dialog'
import Select from 'primevue/select'
import Checkbox from 'primevue/checkbox'
import ConfirmDialog from 'primevue/confirmdialog'
import { useToast } from 'primevue/usetoast'
import { useConfirm } from 'primevue/useconfirm'
import { useTicketsStore, type SavedView } from '../stores/tickets'
import { useAuthStore } from '../stores/auth'
import { useAgentTools } from '../composables/useAgentTools'
import type { Ticket } from '../types'
import { buildActiveProgress, type SlaProgress } from '../utils/sla'

const router = useRouter()
const toast = useToast()
const confirm = useConfirm()
const store = useTicketsStore()
const auth = useAuthStore()
const { agents, loadAll: loadAgentTools } = useAgentTools()

const isStaff = computed(() => auth.user?.role === 'support_agent' || auth.user?.role === 'admin')

// ─── Filters & View ─────────────────────────────────────────────
const activeView = ref<string>('open')
const activeSavedViewId = ref<string | null>(null)
const statusFilter = ref<string[]>([])
const categoryFilter = ref<string[]>([])
const onlyPermanent = ref(false)
const searchQuery = ref('')
const showAdvancedFilters = ref(false)
const sortField = ref<string>('created_desc')
let searchDebounceTimer: ReturnType<typeof setTimeout> | null = null

const sortOptions = computed(() => {
  const base = [
    { label: 'Сначала новые', value: 'created_desc' },
    { label: 'Сначала старые', value: 'created_asc' },
    { label: 'Последние обновлённые', value: 'updated_desc' },
  ]
  if (isStaff.value) {
    base.unshift({ label: 'По умолчанию (SLA)', value: 'default' })
    base.push({ label: 'По приоритету', value: 'priority_desc' })
  } else {
    base.unshift({ label: 'По умолчанию', value: 'default' })
  }
  return base
})

// ─── Saved Views ────────────────────────────────────────────────
const iconOptions = [
  { label: 'Звезда', value: 'pi pi-star', icon: 'pi pi-star' },
  { label: 'Закладка', value: 'pi pi-bookmark', icon: 'pi pi-bookmark' },
  { label: 'Флаг', value: 'pi pi-flag', icon: 'pi pi-flag' },
  { label: 'Пользователь', value: 'pi pi-user', icon: 'pi pi-user' },
  { label: 'Объект', value: 'pi pi-building', icon: 'pi pi-building' },
  { label: 'Внимание', value: 'pi pi-exclamation-triangle', icon: 'pi pi-exclamation-triangle' },
]

const showSaveDialog = ref(false)
const savingView = ref(false)
const newViewName = ref('')
const newViewIcon = ref<string>('pi pi-star')
const newViewShared = ref(false)

const hasActiveFilters = computed(() =>
  statusFilter.value.length > 0 || categoryFilter.value.length > 0 || searchQuery.value.trim().length > 0,
)

const visibleSavedViews = computed(() => {
  const me = auth.user?.id
  return store.savedViews.filter((v) => v.owner_id === me || v.is_shared)
})

const currentFiltersPreview = computed(() => {
  const chips: { label: string; value: string }[] = []
  if (activeView.value !== 'all') {
    const view = views.value.find((v) => v.id === activeView.value)
    if (view) chips.push({ label: 'Раздел', value: view.label })
  }
  if (statusFilter.value.length) {
    const names = statusFilter.value
      .map((s) => statusOptions.find((o) => o.value === s)?.label || s)
      .join(', ')
    chips.push({ label: 'Статус', value: names })
  }
  if (categoryFilter.value.length) {
    const names = categoryFilter.value
      .map((c) => categoryOptions.find((o) => o.value === c)?.label || c)
      .join(', ')
    chips.push({ label: 'Категория', value: names })
  }
  if (searchQuery.value.trim()) {
    chips.push({ label: 'Поиск', value: searchQuery.value.trim() })
  }
  return chips
})

// ─── Views (tabs) ────────────────────────────────────────────────
const views = computed(() => {
  if (isStaff.value) {
    return [
      { id: 'all', label: 'Все', icon: 'pi pi-list' },
      { id: 'open', label: 'Открытые', icon: 'pi pi-inbox', count: store.stats.open },
      { id: 'urgent', label: 'Срочные', icon: 'pi pi-exclamation-triangle', count: store.stats.urgent, severity: 'danger' },
      { id: 'overdue', label: 'Просрочено', icon: 'pi pi-clock', count: store.stats.overdue, severity: 'danger' },
      { id: 'waiting', label: 'Ожидание ответа клиента', icon: 'pi pi-hourglass', count: store.stats.waiting, severity: 'warn' },
      { id: 'engineer_visit', label: 'Выезды', icon: 'pi pi-car' },
      { id: 'closed', label: 'Закрытые', icon: 'pi pi-check-circle' },
    ]
  }
  return [
    { id: 'open', label: 'Открытые', icon: 'pi pi-inbox', count: store.stats.open },
    { id: 'all', label: 'Все', icon: 'pi pi-list' },
    { id: 'closed', label: 'Закрытые', icon: 'pi pi-check-circle' },
  ]
})

// ─── Options ─────────────────────────────────────────────────────
const statusOptions = [
  { label: 'Новый', value: 'new' },
  { label: 'В работе', value: 'in_progress' },
  { label: 'Ожидание ответа клиента', value: 'waiting_for_user' },
  { label: 'Отложена', value: 'on_hold' },
  { label: 'Выезд инженера', value: 'engineer_visit' },
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

const statusLabelsStaff: Record<string, string> = {
  new: 'Новый', in_progress: 'В работе', waiting_for_user: 'Ожидание ответа клиента', on_hold: 'Отложена', engineer_visit: 'Выезд', resolved: 'Решён', closed: 'Закрыт',
}
const statusLabelsUser: Record<string, string> = {
  new: 'Принята', in_progress: 'В работе', waiting_for_user: 'Ждёт ответа', on_hold: 'Отложена', engineer_visit: 'Инженер выехал', resolved: 'Решена', closed: 'Закрыта',
}
const statusLabels = computed(() => isStaff.value ? statusLabelsStaff : statusLabelsUser)
const statusColors: Record<string, string> = {
  new: '#3b82f6', in_progress: '#f59e0b', waiting_for_user: '#8b5cf6', on_hold: '#6366f1', engineer_visit: '#0ea5e9', resolved: '#10b981', closed: '#64748b',
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
  pass24_online: 'PASS24', mobile_app: 'Мобильное приложение', pass24_key: 'PASS24.Key',
  pass24_control: 'PASS24.control', pass24_auto: 'PASS24.auto',
  equipment: 'Оборудование', integration: 'Интеграция', other: 'Другое',
}
const sourceLabels: Record<string, string> = {
  web: 'Веб', email: 'Email', telegram: 'Telegram', api: 'API', phone: 'Телефон',
}
const sourceIcons: Record<string, string> = {
  web: 'pi pi-globe', email: 'pi pi-envelope', telegram: 'pi pi-send', api: 'pi pi-code', phone: 'pi pi-phone',
}

const agentMap = computed(() => {
  const m = new Map<string, string>()
  for (const a of agents.value) m.set(a.id, a.full_name)
  return m
})

// ─── SLA widget ─────────────────────────────────────────────────
// Берём готовые значения с бэка (sla_*_remaining_seconds, sla_is_paused) —
// бэк уже учёл бизнес-часы и паузы. См. compute_sla_state.
function slaWidget(ticket: Ticket): SlaProgress | null {
  return buildActiveProgress(ticket)
}

function formatDate(dateStr: string): string {
  const d = new Date(dateStr.endsWith('Z') ? dateStr : dateStr + 'Z')
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
      customer_only_permanent: onlyPermanent.value || undefined,
      q: searchQuery.value.trim() || undefined,
      view: activeView.value !== 'all' ? activeView.value : undefined,
      sort: sortField.value !== 'default' ? sortField.value : undefined,
    })
  } catch (e: any) {
    toast.add({ severity: 'error', summary: 'Ошибка', detail: e.message || 'Не удалось загрузить', life: 4000 })
  }
}

function selectView(viewId: string) {
  activeView.value = viewId
  activeSavedViewId.value = null
  statusFilter.value = []
  categoryFilter.value = []
  loadTickets(1)
}

function applySavedView(view: SavedView) {
  const f = view.filters || {}
  activeSavedViewId.value = view.id
  activeView.value = typeof f.view === 'string' ? f.view : 'all'
  statusFilter.value = Array.isArray(f.status) ? [...f.status] : []
  categoryFilter.value = Array.isArray(f.category) ? [...f.category] : []
  searchQuery.value = typeof f.q === 'string' ? f.q : ''
  // fire-and-forget usage increment
  store.recordViewUsage(view.id)
  // bump local count so UI reflects immediately
  const local = store.savedViews.find((v) => v.id === view.id)
  if (local) local.usage_count += 1
  loadTickets(1)
}

function openSaveDialog() {
  newViewName.value = ''
  newViewIcon.value = 'pi pi-star'
  newViewShared.value = false
  showSaveDialog.value = true
}

async function submitSaveView() {
  const name = newViewName.value.trim()
  if (!name) return
  savingView.value = true
  try {
    const filtersPayload: Record<string, any> = {}
    if (activeView.value !== 'all') filtersPayload.view = activeView.value
    if (statusFilter.value.length) filtersPayload.status = [...statusFilter.value]
    if (categoryFilter.value.length) filtersPayload.category = [...categoryFilter.value]
    if (searchQuery.value.trim()) filtersPayload.q = searchQuery.value.trim()

    await store.createSavedView({
      name: name.slice(0, 128),
      icon: newViewIcon.value || null,
      filters: filtersPayload,
      is_shared: newViewShared.value,
    })
    await store.fetchSavedViews()
    showSaveDialog.value = false
    toast.add({ severity: 'success', summary: 'View сохранён', life: 2000 })
  } catch (e: any) {
    toast.add({ severity: 'error', summary: 'Ошибка', detail: e.message || 'Не удалось сохранить', life: 4000 })
  } finally {
    savingView.value = false
  }
}

function confirmDeleteView(view: SavedView, event: Event) {
  event.stopPropagation()
  confirm.require({
    message: `Удалить сохранённый view «${view.name}»?`,
    header: 'Удаление view',
    icon: 'pi pi-exclamation-triangle',
    acceptClass: 'p-button-danger',
    acceptLabel: 'Удалить',
    rejectLabel: 'Отмена',
    accept: async () => {
      try {
        await store.deleteSavedView(view.id)
        if (activeSavedViewId.value === view.id) activeSavedViewId.value = null
        toast.add({ severity: 'success', summary: 'Удалён', life: 2000 })
      } catch (e: any) {
        toast.add({ severity: 'error', summary: 'Ошибка', detail: e.message || 'Не удалось удалить', life: 4000 })
      }
    },
  })
}

function onPageChange(event: { page: number; rows: number }) {
  // PrimeVue Paginator при смене rows-per-page эмитит то же событие @page.
  // Если число строк изменилось — отдаём управление store.setPerPage,
  // который сам перезагрузит первую страницу с новым per_page.
  if (event.rows !== store.perPage) {
    store.setPerPage(event.rows)
    return
  }
  loadTickets(event.page + 1)
}

watch(searchQuery, (v, prev) => {
  if (v !== prev && activeSavedViewId.value) activeSavedViewId.value = null
  if (searchDebounceTimer) clearTimeout(searchDebounceTimer)
  searchDebounceTimer = setTimeout(() => loadTickets(1), 300)
})

watch([statusFilter, categoryFilter], () => {
  if (activeSavedViewId.value) activeSavedViewId.value = null
}, { deep: true })

// Активный статус — индикатор «кто ответил последним» показываем только
// для таких тикетов. Для resolved/closed история уже зафиксирована.
const ACTIVE_STATUSES = new Set(['new', 'in_progress', 'waiting_for_user', 'on_hold', 'engineer_visit'])
function isActiveStatus(status: string): boolean {
  return ACTIVE_STATUSES.has(status)
}

// Polling: освежаем список + статистику раз в минуту, чтобы SLA-полоска
// не «замораживалась» в нерабочее время. Сервер пересчитывает remaining
// каждый запрос, фронт не делает Date.now()-арифметику.
let pollTimer: ReturnType<typeof setInterval> | null = null

onMounted(() => {
  store.fetchStats()
  // Пользователи видят только открытые по умолчанию
  if (!isStaff.value) activeView.value = 'open'
  loadTickets(1)
  if (auth.isLoggedIn) store.fetchSavedViews()
  if (isStaff.value) loadAgentTools()
  pollTimer = setInterval(() => {
    loadTickets(store.page || 1)
    store.fetchStats()
  }, 60_000)
})

onUnmounted(() => {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
})
</script>

<template>
  <div class="tickets-page" :class="{ 'user-view': !isStaff }">
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
        :class="{ active: activeView === view.id && !activeSavedViewId, danger: view.severity === 'danger', warn: view.severity === 'warn' }"
        @click="selectView(view.id)"
      >
        <i :class="view.icon" />
        <span>{{ view.label }}</span>
        <span v-if="view.count !== undefined && view.count > 0" class="view-count">{{ view.count }}</span>
      </button>

      <template v-if="auth.isLoggedIn && (visibleSavedViews.length > 0 || hasActiveFilters)">
        <span class="views-separator" aria-hidden="true" />

        <button
          v-for="sv in visibleSavedViews"
          :key="sv.id"
          class="view-tab saved-view-tab"
          :class="{ active: activeSavedViewId === sv.id }"
          :title="sv.is_shared ? 'Общий view' : 'Личный view'"
          @click="applySavedView(sv)"
        >
          <i :class="sv.icon || 'pi pi-star'" />
          <span>{{ sv.name }}</span>
          <span v-if="sv.is_shared" class="saved-view-shared" title="Общий"><i class="pi pi-users" /></span>
          <span v-if="sv.usage_count > 0" class="view-count">{{ sv.usage_count }}</span>
          <span
            v-if="auth.user && sv.owner_id === auth.user.id"
            class="saved-view-delete"
            title="Удалить"
            @click="confirmDeleteView(sv, $event)"
          >
            <i class="pi pi-trash" />
          </span>
        </button>

        <button
          v-if="hasActiveFilters"
          class="view-tab saved-view-add"
          title="Сохранить текущие фильтры как view"
          @click="openSaveDialog"
        >
          <i class="pi pi-plus" />
          <span>Сохранить</span>
        </button>
      </template>
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
      <Select
        v-model="sortField"
        :options="sortOptions"
        option-label="label"
        option-value="value"
        placeholder="Сортировка"
        class="sort-select"
        @change="loadTickets(1)"
      />
    </div>

    <!-- Advanced filters -->
    <div v-if="showAdvancedFilters" class="advanced-filters">
      <MultiSelect
        v-if="isStaff"
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
        v-if="isStaff"
        :label="onlyPermanent ? 'Постоянные клиенты' : 'Все клиенты'"
        :icon="onlyPermanent ? 'pi pi-star-fill' : 'pi pi-star'"
        :severity="onlyPermanent ? 'warning' : 'secondary'"
        :outlined="!onlyPermanent"
        size="small"
        title="Показывать только заявки от постоянных клиентов (синхронизированы из Bitrix24)"
        @click="onlyPermanent = !onlyPermanent; loadTickets(1)"
      />
      <Button
        v-if="statusFilter.length || categoryFilter.length || onlyPermanent"
        label="Сбросить"
        icon="pi pi-times"
        text severity="secondary" size="small"
        @click="statusFilter = []; categoryFilter = []; onlyPermanent = false; loadTickets(1)"
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
        v-if="searchQuery || statusFilter.length || categoryFilter.length || onlyPermanent"
        label="Сбросить фильтры" text severity="secondary" size="small"
        @click="searchQuery = ''; statusFilter = []; categoryFilter = []; onlyPermanent = false; activeView = 'all'; loadTickets(1)"
      />
      <Button v-else label="Создать заявку" icon="pi pi-plus" @click="router.push('/tickets/create')" />
    </div>

    <div v-else class="ticket-list">
      <RouterLink
        v-for="ticket in store.tickets"
        :key="ticket.id"
        :to="`/tickets/${ticket.id}`"
        class="ticket-row"
        :class="{ 'row-urgent': ticket.urgent, 'row-unread': isStaff && ticket.has_unread_reply }"
        :style="{ '--priority-color': priorityColors[ticket.priority] || '#64748b' }"
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
            <span v-if="isStaff && ticket.product" class="meta-item">
              <i class="pi pi-box" />{{ productLabels[ticket.product] || ticket.product }}
            </span>
            <span v-if="ticket.category" class="meta-sep">·</span>
            <span v-if="ticket.category" class="meta-item">{{ categoryLabels[ticket.category] || ticket.category }}</span>
            <span v-if="isStaff && (ticket.contact_name || ticket.contact_email)" class="meta-sep">·</span>
            <span v-if="isStaff && (ticket.contact_name || ticket.contact_email)" class="meta-item">
              <i class="pi pi-user" />{{ ticket.contact_name || ticket.contact_email }}
            </span>
            <template v-if="isStaff && ticket.customer_is_permanent">
              <span class="meta-sep">·</span>
              <span class="meta-item meta-permanent" title="Постоянный клиент (Bitrix24)">
                <i class="pi pi-star-fill" />Постоянный
              </span>
            </template>
            <template v-if="ticket.last_public_reply_by && isActiveStatus(ticket.status)">
              <span class="meta-sep">·</span>
              <span
                class="meta-item"
                :class="`reply-by-${ticket.last_public_reply_by}`"
                :title="ticket.last_public_reply_by === 'client' ? 'Последним ответил клиент' : 'Последним ответил оператор'"
              >
                Отв.: {{ ticket.last_public_reply_by === 'client' ? 'клиент' : 'оператор' }}
              </span>
            </template>
            <span v-if="ticket.comments?.length" class="meta-sep">·</span>
            <span v-if="ticket.comments?.length" class="meta-item"><i class="pi pi-comment" />{{ ticket.comments.length }}</span>
            <span v-if="ticket.attachments?.length" class="meta-sep">·</span>
            <span v-if="ticket.attachments?.length" class="meta-item"><i class="pi pi-paperclip" />{{ ticket.attachments.length }}</span>
            <template v-if="isStaff && ticket.assignee_id">
              <span class="meta-sep">·</span>
              <span class="meta-item meta-assignee" :title="'Ответственный: ' + (agentMap.get(ticket.assignee_id) || '')">
                <i class="pi pi-shield" />{{ agentMap.get(ticket.assignee_id) || 'Назначен' }}
              </span>
            </template>
            <template v-if="isStaff && ticket.source">
              <span class="meta-sep">·</span>
              <span class="meta-item meta-source" :title="'Канал: ' + (sourceLabels[ticket.source] || ticket.source)">
                <i :class="sourceIcons[ticket.source] || 'pi pi-inbox'" />{{ sourceLabels[ticket.source] || ticket.source }}
              </span>
            </template>
          </div>
        </div>

        <div class="row-right">
          <!-- SLA indicator (только для агентов) -->
          <template v-if="isStaff && ticket.status !== 'closed' && ticket.status !== 'resolved'">
            <div v-if="slaWidget(ticket)" class="sla-widget">
              <div class="sla-bar-track">
                <div
                  class="sla-bar-fill"
                  :style="{ width: slaWidget(ticket)!.pct + '%', background: slaWidget(ticket)!.color }"
                />
              </div>
              <div class="sla-remaining" :style="{ color: slaWidget(ticket)!.color }">
                <i
                  :class="
                    slaWidget(ticket)!.paused
                      ? 'pi pi-pause-circle'
                      : slaWidget(ticket)!.overdue
                        ? 'pi pi-exclamation-circle'
                        : 'pi pi-clock'
                  "
                />
                {{ slaWidget(ticket)!.label }}
              </div>
            </div>
          </template>
          <div v-else-if="isStaff" class="sla-widget done">
            <i class="pi pi-check-circle" /> решено
          </div>

          <!-- Status + Priority -->
          <div class="row-badges">
            <span class="pill pill-status" :style="{ '--c': statusColors[ticket.status] }">
              {{ statusLabels[ticket.status] || ticket.status }}
            </span>
            <span v-if="isStaff" class="pill pill-priority" :style="{ '--c': priorityColors[ticket.priority] || '#64748b' }">
              {{ priorityLabels[ticket.priority] || ticket.priority }}
            </span>
          </div>

          <div class="row-date">{{ formatDate(ticket.created_at) }}</div>
        </div>
      </RouterLink>
    </div>

    <Paginator
      v-if="store.total > store.perPage"
      :rows="store.perPage"
      :total-records="store.total"
      :first="(store.page - 1) * store.perPage"
      :rows-per-page-options="[20, 50, 100]"
      template="FirstPageLink PrevPageLink PageLinks NextPageLink LastPageLink RowsPerPageDropdown CurrentPageReport"
      current-page-report-template="{first}–{last} из {totalRecords}"
      @page="onPageChange"
    />

    <!-- Save view dialog -->
    <Dialog
      v-model:visible="showSaveDialog"
      modal
      header="Сохранить view"
      :style="{ width: '460px' }"
      :draggable="false"
    >
      <div class="save-view-form">
        <div class="form-field">
          <label for="sv-name">Название <span class="req">*</span></label>
          <InputText
            id="sv-name"
            v-model="newViewName"
            maxlength="128"
            placeholder="Например: Мои срочные"
            fluid
            autofocus
          />
        </div>
        <div class="form-field">
          <label for="sv-icon">Иконка</label>
          <Select
            id="sv-icon"
            v-model="newViewIcon"
            :options="iconOptions"
            option-label="label"
            option-value="value"
            fluid
          >
            <template #value="slotProps">
              <span v-if="slotProps.value" class="icon-select-value">
                <i :class="slotProps.value" />
                {{ iconOptions.find(o => o.value === slotProps.value)?.label }}
              </span>
              <span v-else>Выберите иконку</span>
            </template>
            <template #option="slotProps">
              <span class="icon-select-value">
                <i :class="slotProps.option.icon" />
                {{ slotProps.option.label }}
              </span>
            </template>
          </Select>
        </div>
        <div class="form-field-inline">
          <Checkbox v-model="newViewShared" input-id="sv-shared" :binary="true" />
          <label for="sv-shared">Поделиться с командой</label>
        </div>

        <div v-if="currentFiltersPreview.length" class="filters-preview">
          <div class="filters-preview-title">Текущие фильтры</div>
          <div class="filters-preview-chips">
            <span v-for="(chip, i) in currentFiltersPreview" :key="i" class="filter-chip">
              <span class="filter-chip-label">{{ chip.label }}:</span>
              <span class="filter-chip-value">{{ chip.value }}</span>
            </span>
          </div>
        </div>
      </div>
      <template #footer>
        <Button label="Отмена" severity="secondary" text @click="showSaveDialog = false" />
        <Button
          label="Сохранить"
          icon="pi pi-check"
          :loading="savingView"
          :disabled="!newViewName.trim()"
          @click="submitSaveView"
        />
      </template>
    </Dialog>

    <ConfirmDialog />
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

/* Saved views */
.views-separator {
  display: inline-block; width: 1px; height: 20px; background: #cbd5e1; margin: 0 4px; align-self: center;
}
.saved-view-tab { position: relative; padding-right: 14px; }
.saved-view-tab:hover .saved-view-delete { opacity: 1; pointer-events: auto; }
.saved-view-delete {
  position: absolute; top: 50%; right: 4px; transform: translateY(-50%);
  display: inline-flex; align-items: center; justify-content: center;
  width: 18px; height: 18px; border-radius: 4px;
  background: rgba(220, 38, 38, 0.1); color: #dc2626;
  opacity: 0; pointer-events: none; transition: opacity 0.15s, background 0.15s;
}
.saved-view-delete:hover { background: #dc2626; color: white; }
.saved-view-delete i { font-size: 10px; }
.saved-view-shared { display: inline-flex; align-items: center; color: #94a3b8; }
.saved-view-shared i { font-size: 10px; }
.saved-view-tab.active .saved-view-shared { color: #3b82f6; }
.saved-view-add { color: #3b82f6 !important; font-weight: 600; }
.saved-view-add:hover { background: #dbeafe !important; color: #2563eb !important; }
.saved-view-add i { font-size: 11px; }

/* Toolbar */
.toolbar { display: flex; gap: 10px; align-items: center; }
.search-field { flex: 1; }
.search-input :deep(input) { border-radius: 10px; padding: 10px 14px 10px 38px; }
.sort-select { min-width: 200px; }

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
  /* RouterLink рендерится как <a> — нейтрализуем дефолтные стили якоря,
     чтобы карточка визуально не отличалась от прежнего <article>. */
  text-decoration: none;
  color: inherit;
}
.ticket-row:hover { border-color: #cbd5e1; box-shadow: 0 2px 8px rgba(0,0,0,0.04); transform: translateY(-1px); text-decoration: none; }
.ticket-row:focus-visible { outline: 2px solid #6366f1; outline-offset: 2px; }
.ticket-row:visited { color: inherit; }

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
/* Индикатор «кто ответил последним» в списке активных тикетов */
.meta-item.reply-by-client { color: #2563eb; font-weight: 600; }
.meta-item.reply-by-staff { color: #64748b; font-weight: 500; }
.meta-item.meta-permanent { color: #b45309; font-weight: 600; }
.meta-item.meta-permanent i { color: #d97706; }

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

/* Save view dialog */
.save-view-form { display: flex; flex-direction: column; gap: 14px; }
.form-field { display: flex; flex-direction: column; gap: 6px; }
.form-field label { font-size: 13px; font-weight: 500; color: #334155; }
.form-field .req { color: #dc2626; }
.form-field-inline { display: flex; align-items: center; gap: 8px; }
.form-field-inline label { font-size: 13px; color: #334155; cursor: pointer; }
.icon-select-value { display: inline-flex; align-items: center; gap: 8px; }
.icon-select-value i { font-size: 13px; color: #64748b; }

.filters-preview {
  display: flex; flex-direction: column; gap: 6px;
  padding: 10px 12px; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px;
}
.filters-preview-title { font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.04em; color: #64748b; }
.filters-preview-chips { display: flex; flex-wrap: wrap; gap: 6px; }
.filter-chip {
  display: inline-flex; align-items: center; gap: 4px;
  padding: 3px 8px; background: white; border: 1px solid #e2e8f0; border-radius: 6px; font-size: 11px;
}
.filter-chip-label { color: #94a3b8; font-weight: 500; }
.filter-chip-value { color: #0f172a; font-weight: 600; }

/* Responsive */
@media (max-width: 768px) {
  .page-header { flex-direction: column; align-items: stretch; }
  .views-tabs { gap: 4px; }
  .view-tab { padding: 8px 10px; font-size: 12px; }

  .ticket-row { flex-direction: column; align-items: flex-start; gap: 10px; padding: 14px 14px 14px 20px; }
  .row-right { flex-direction: row; align-items: center; width: 100%; justify-content: space-between; flex-wrap: wrap; }
  .sla-widget { min-width: 90px; }
}

/* --- Упрощённый вид для обычных пользователей --- */
.user-view .ticket-row { padding: 18px 20px 18px 26px; }
.user-view .row-right { gap: 12px; }
</style>

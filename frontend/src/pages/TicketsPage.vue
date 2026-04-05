<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Button from 'primevue/button'
import MultiSelect from 'primevue/multiselect'
import Toolbar from 'primevue/toolbar'
import Paginator from 'primevue/paginator'
import Tag from 'primevue/tag'
import InputText from 'primevue/inputtext'
import IconField from 'primevue/iconfield'
import InputIcon from 'primevue/inputicon'
import { useToast } from 'primevue/usetoast'
import TicketStatusBadge from '../components/TicketStatusBadge.vue'
import TicketPriorityBadge from '../components/TicketPriorityBadge.vue'
import { useTicketsStore } from '../stores/tickets'
import type { Ticket } from '../types'

const router = useRouter()
const toast = useToast()
const store = useTicketsStore()

const statusFilter = ref<string[]>([])
const categoryFilter = ref<string[]>([])
const myOnly = ref(false)
const searchQuery = ref('')
let searchDebounceTimer: ReturnType<typeof setTimeout> | null = null

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

const categoryLabels: Record<string, string> = {
  registration: 'Регистрация',
  passes: 'Пропуска',
  recognition: 'Распознавание',
  app_issues: 'Приложение',
  objects: 'Объекты',
  trusted_persons: 'Доверенные лица',
  equipment_issues: 'Оборудование',
  consultation: 'Консультация',
  feature_request: 'Предложение',
  other: 'Другое',
}

const productLabels: Record<string, string> = {
  pass24_online: 'PASS24.online',
  mobile_app: 'Мобильное приложение',
  pass24_key: 'PASS24.Key',
  pass24_control: 'PASS24.control',
  pass24_auto: 'PASS24.auto',
  equipment: 'Оборудование',
  integration: 'Интеграция',
  other: 'Другое',
}

function formatDate(dateStr: string): string {
  return new Intl.DateTimeFormat('ru-RU', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(dateStr))
}

async function loadTickets(page?: number) {
  try {
    await store.fetchTickets(page, {
      status: statusFilter.value.length ? statusFilter.value : undefined,
      category: categoryFilter.value.length ? categoryFilter.value : undefined,
      my: myOnly.value || undefined,
      q: searchQuery.value.trim() || undefined,
    })
  } catch (e: any) {
    toast.add({
      severity: 'error',
      summary: 'Ошибка',
      detail: e.message || 'Не удалось загрузить заявки',
      life: 4000,
    })
  }
}

function onPageChange(event: { page: number }) {
  loadTickets(event.page + 1)
}

function onFilterChange() {
  loadTickets(1)
}

watch(searchQuery, () => {
  if (searchDebounceTimer) clearTimeout(searchDebounceTimer)
  searchDebounceTimer = setTimeout(() => loadTickets(1), 300)
})

function onRowClick(event: { data: Ticket }) {
  router.push(`/tickets/${event.data.id}`)
}

onMounted(() => loadTickets(1))
</script>

<template>
  <div class="tickets-page">
    <Toolbar class="tickets-toolbar">
      <template #start>
        <div class="toolbar-filters">
          <IconField class="search-field">
            <InputIcon class="pi pi-search" />
            <InputText
              v-model="searchQuery"
              placeholder="Поиск по теме, описанию, email..."
              class="search-input"
            />
          </IconField>
          <MultiSelect
            v-model="statusFilter"
            :options="statusOptions"
            option-label="label"
            option-value="value"
            placeholder="Статус"
            :max-selected-labels="2"
            selected-items-label="{0} статусов"
            class="filter-select"
            @change="onFilterChange"
          />
          <MultiSelect
            v-model="categoryFilter"
            :options="categoryOptions"
            option-label="label"
            option-value="value"
            placeholder="Категория"
            :max-selected-labels="2"
            selected-items-label="{0} категорий"
            class="filter-select"
            @change="onFilterChange"
          />
          <Button
            :label="myOnly ? 'Все заявки' : 'Мои заявки'"
            :icon="myOnly ? 'pi pi-list' : 'pi pi-user'"
            :severity="myOnly ? 'primary' : 'secondary'"
            :outlined="!myOnly"
            size="small"
            @click="myOnly = !myOnly; onFilterChange()"
          />
        </div>
      </template>
      <template #end>
        <Button
          label="Создать заявку"
          icon="pi pi-plus"
          @click="router.push('/tickets/create')"
        />
      </template>
    </Toolbar>

    <!-- Active filters chips -->
    <div v-if="statusFilter.length || categoryFilter.length" class="active-filters">
      <Tag
        v-for="s in statusFilter"
        :key="'s-' + s"
        :value="statusOptions.find(o => o.value === s)?.label || s"
        severity="info"
        rounded
        class="filter-chip"
        @click="statusFilter = statusFilter.filter(v => v !== s); onFilterChange()"
      />
      <Tag
        v-for="c in categoryFilter"
        :key="'c-' + c"
        :value="categoryLabels[c] || c"
        severity="secondary"
        rounded
        class="filter-chip"
        @click="categoryFilter = categoryFilter.filter(v => v !== c); onFilterChange()"
      />
      <Button
        label="Сбросить фильтры"
        icon="pi pi-times"
        text
        size="small"
        severity="secondary"
        @click="statusFilter = []; categoryFilter = []; onFilterChange()"
      />
    </div>

    <DataTable
      :value="store.tickets"
      :loading="store.loading"
      row-hover
      striped-rows
      class="tickets-table"
      @row-click="onRowClick"
    >
      <template #empty>
        <div class="empty-message">Заявки не найдены</div>
      </template>

      <Column field="title" header="Тема" style="min-width: 220px">
        <template #body="{ data }">
          <div class="ticket-cell-title">
            <span class="ticket-title">{{ data.title }}</span>
            <span v-if="data.urgent" class="urgent-dot" title="Срочная">!</span>
          </div>
        </template>
      </Column>

      <Column field="product" header="Продукт" style="width: 140px">
        <template #body="{ data }">
          <span class="ticket-meta-text">{{ productLabels[data.product] || data.product || '—' }}</span>
        </template>
      </Column>

      <Column field="category" header="Категория" style="width: 140px">
        <template #body="{ data }">
          <span class="ticket-meta-text">{{ categoryLabels[data.category] || data.category || '—' }}</span>
        </template>
      </Column>

      <Column field="status" header="Статус" style="width: 150px">
        <template #body="{ data }">
          <TicketStatusBadge :status="data.status" />
        </template>
      </Column>

      <Column field="priority" header="Приоритет" style="width: 130px">
        <template #body="{ data }">
          <TicketPriorityBadge :priority="data.priority" />
        </template>
      </Column>

      <Column field="created_at" header="Создана" style="width: 160px">
        <template #body="{ data }">
          <span class="ticket-date">{{ formatDate(data.created_at) }}</span>
        </template>
      </Column>
    </DataTable>

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
.tickets-page {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.tickets-toolbar {
  border-radius: 8px;
}

.toolbar-filters {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.filter-select {
  min-width: 180px;
}

.search-field {
  min-width: 280px;
  flex: 1;
}

.search-input {
  width: 100%;
}

.active-filters {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  align-items: center;
}

.filter-chip {
  cursor: pointer;
  transition: opacity 0.15s;
}

.filter-chip:hover {
  opacity: 0.7;
}

.tickets-table {
  cursor: pointer;
}

.ticket-cell-title {
  display: flex;
  align-items: center;
  gap: 6px;
}

.ticket-title {
  font-weight: 500;
  color: #1e293b;
}

.urgent-dot {
  background: #ef4444;
  color: white;
  font-weight: 700;
  font-size: 11px;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.ticket-meta-text {
  font-size: 13px;
  color: #64748b;
}

.ticket-date {
  font-size: 13px;
  color: #64748b;
}

.empty-message {
  text-align: center;
  padding: 2rem;
  color: #94a3b8;
}

@media (max-width: 768px) {
  .toolbar-filters {
    flex-direction: column;
    gap: 8px;
  }

  .filter-select {
    min-width: 100%;
  }
}
</style>

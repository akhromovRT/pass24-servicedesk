<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Button from 'primevue/button'
import Select from 'primevue/select'
import Toolbar from 'primevue/toolbar'
import Paginator from 'primevue/paginator'
import { useToast } from 'primevue/usetoast'
import TicketStatusBadge from '../components/TicketStatusBadge.vue'
import TicketPriorityBadge from '../components/TicketPriorityBadge.vue'
import { useTicketsStore } from '../stores/tickets'
import type { Ticket, TicketStatus } from '../types'

const router = useRouter()
const toast = useToast()
const store = useTicketsStore()

const statusFilter = ref<TicketStatus | ''>('')
const categoryFilter = ref('')

const statusOptions = [
  { label: 'Все статусы', value: '' },
  { label: 'Новый', value: 'new' },
  { label: 'В работе', value: 'in_progress' },
  { label: 'Ожидает ответа', value: 'waiting_for_user' },
  { label: 'Решён', value: 'resolved' },
  { label: 'Закрыт', value: 'closed' },
]

const categoryOptions = [
  { label: 'Все категории', value: '' },
  { label: 'Доступ', value: 'access' },
  { label: 'Пропуска', value: 'pass' },
  { label: 'Шлагбаум', value: 'gate' },
  { label: 'Уведомления', value: 'notifications' },
  { label: 'Общее', value: 'general' },
  { label: 'Другое', value: 'other' },
]

const categoryLabels: Record<string, string> = {
  access: 'Доступ',
  pass: 'Пропуска',
  gate: 'Шлагбаум',
  notifications: 'Уведомления',
  general: 'Общее',
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

function getCategoryLabel(category: string): string {
  return categoryLabels[category] || category
}

async function loadTickets(page?: number) {
  try {
    await store.fetchTickets(page, {
      status: statusFilter.value || undefined,
      category: categoryFilter.value || undefined,
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

function onRowClick(event: { data: Ticket }) {
  router.push(`/tickets/${event.data.id}`)
}

function goToCreate() {
  router.push('/tickets/create')
}

onMounted(() => {
  loadTickets(1)
})
</script>

<template>
  <div class="tickets-page">
    <Toolbar class="tickets-toolbar">
      <template #start>
        <div class="toolbar-filters">
          <Select
            v-model="statusFilter"
            :options="statusOptions"
            option-label="label"
            option-value="value"
            placeholder="Все статусы"
            class="filter-select"
            @change="onFilterChange"
          />
          <Select
            v-model="categoryFilter"
            :options="categoryOptions"
            option-label="label"
            option-value="value"
            placeholder="Все категории"
            class="filter-select"
            @change="onFilterChange"
          />
        </div>
      </template>
      <template #end>
        <Button
          label="Создать заявку"
          icon="pi pi-plus"
          @click="goToCreate"
        />
      </template>
    </Toolbar>

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

      <Column field="title" header="Тема" style="min-width: 250px">
        <template #body="{ data }">
          <span class="ticket-title">{{ data.title }}</span>
        </template>
      </Column>

      <Column field="category" header="Категория" style="width: 140px">
        <template #body="{ data }">
          {{ getCategoryLabel(data.category) }}
        </template>
      </Column>

      <Column field="status" header="Статус" style="width: 150px">
        <template #body="{ data }">
          <TicketStatusBadge :status="data.status" />
        </template>
      </Column>

      <Column field="priority" header="Приоритет" style="width: 140px">
        <template #body="{ data }">
          <TicketPriorityBadge :priority="data.priority" />
        </template>
      </Column>

      <Column field="created_at" header="Создана" style="width: 170px">
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
  gap: 16px;
}

.tickets-toolbar {
  border-radius: 8px;
}

.toolbar-filters {
  display: flex;
  gap: 12px;
}

.filter-select {
  min-width: 180px;
}

.tickets-table {
  cursor: pointer;
}

.ticket-title {
  font-weight: 500;
  color: #1e293b;
}

.ticket-date {
  font-size: 0.875rem;
  color: #64748b;
}

.empty-message {
  text-align: center;
  padding: 2rem;
  color: #94a3b8;
}
</style>

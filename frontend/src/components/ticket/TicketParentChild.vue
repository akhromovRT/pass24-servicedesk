<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import Button from 'primevue/button'
import Dialog from 'primevue/dialog'
import InputText from 'primevue/inputtext'
import Panel from 'primevue/panel'
import TicketStatusBadge from '../TicketStatusBadge.vue'
import { useToast } from 'primevue/usetoast'
import { api } from '../../api/client'
import type { Ticket, TicketStatus, TicketPriority, PaginatedResponse } from '../../types'

interface ChildTicket {
  id: string
  title: string
  status: TicketStatus
  priority: TicketPriority
  created_at: string
}

const props = defineProps<{
  ticket: Ticket
}>()

const emit = defineEmits<{
  updated: []
}>()

const router = useRouter()
const toast = useToast()

const childTickets = ref<ChildTicket[]>([])
const childrenCount = ref(0)
const parentTicket = ref<{ id: string; title: string } | null>(null)

const dialogVisible = ref(false)
const searchQuery = ref('')
const searchResults = ref<Ticket[]>([])
const searchLoading = ref(false)

let searchDebounce: ReturnType<typeof setTimeout> | null = null

function shortId(id: string): string {
  return id.replace(/-/g, '').slice(0, 8).toUpperCase()
}

async function loadChildren() {
  try {
    const data = await api.get<{ count: number; items: ChildTicket[] }>(`/tickets/${props.ticket.id}/children`)
    childTickets.value = data.items || []
    childrenCount.value = data.count || 0
  } catch {
    childTickets.value = []
    childrenCount.value = 0
  }
}

async function loadParent() {
  if (!props.ticket.parent_ticket_id) { parentTicket.value = null; return }
  try {
    const data = await api.get<Ticket>(`/tickets/${props.ticket.parent_ticket_id}`)
    parentTicket.value = { id: data.id, title: data.title }
  } catch { parentTicket.value = null }
}

function openDialog() {
  searchQuery.value = ''
  searchResults.value = []
  dialogVisible.value = true
}

function onSearchInput() {
  if (searchDebounce) clearTimeout(searchDebounce)
  const q = searchQuery.value.trim()
  if (!q) { searchResults.value = []; return }
  searchDebounce = setTimeout(async () => {
    searchLoading.value = true
    try {
      const data = await api.get<PaginatedResponse<Ticket>>(
        `/tickets/?q=${encodeURIComponent(q)}&per_page=10&page=1`,
      )
      searchResults.value = (data.items || []).filter(t => t.id !== props.ticket.id)
    } catch { searchResults.value = [] }
    finally { searchLoading.value = false }
  }, 300)
}

async function linkToParent(parentId: string) {
  try {
    await api.put(`/tickets/${props.ticket.id}/parent`, { parent_ticket_id: parentId })
    dialogVisible.value = false
    await loadParent()
    emit('updated')
    toast.add({ severity: 'success', summary: 'Привязано к Problem', life: 2000 })
  } catch (e: any) {
    toast.add({ severity: 'error', summary: 'Ошибка', detail: e.message, life: 4000 })
  }
}

async function unlinkFromParent() {
  try {
    await api.delete(`/tickets/${props.ticket.id}/parent`)
    parentTicket.value = null
    emit('updated')
    toast.add({ severity: 'success', summary: 'Отвязано от Problem', life: 2000 })
  } catch (e: any) {
    toast.add({ severity: 'error', summary: 'Ошибка', detail: e.message, life: 4000 })
  }
}

onMounted(() => {
  loadChildren()
  loadParent()
})

defineExpose({ loadChildren, loadParent })
</script>

<template>
  <Panel header="Связанные тикеты" toggleable collapsed class="sidebar-panel">
    <!-- Parent -->
    <div v-if="parentTicket" class="parent-block">
      <div class="block-label">Problem (родительский):</div>
      <div class="linked-ticket-item">
        <a class="ticket-link" @click="router.push(`/tickets/${parentTicket.id}`)">
          #{{ shortId(parentTicket.id) }} {{ parentTicket.title }}
        </a>
        <Button icon="pi pi-times" text severity="danger" size="small" @click="unlinkFromParent" />
      </div>
    </div>

    <!-- Children -->
    <div v-if="childTickets.length > 0" class="children-block">
      <div class="block-label">Инциденты ({{ childrenCount }}):</div>
      <div v-for="child in childTickets" :key="child.id" class="linked-ticket-item">
        <div class="child-info">
          <a class="ticket-link" @click="router.push(`/tickets/${child.id}`)">
            #{{ shortId(child.id) }}
          </a>
          <span class="child-title">{{ child.title }}</span>
        </div>
        <TicketStatusBadge :status="child.status" />
      </div>
    </div>

    <Button
      v-if="!parentTicket"
      label="Привязать к Problem"
      icon="pi pi-link"
      text
      size="small"
      @click="openDialog"
      class="mt-2"
    />

    <Dialog v-model:visible="dialogVisible" header="Привязать к Problem-тикету" modal :style="{ width: '500px' }">
      <InputText v-model="searchQuery" placeholder="Поиск тикетов..." class="w-full mb-3" @input="onSearchInput" />
      <div v-if="searchLoading" class="text-center p-3"><i class="pi pi-spin pi-spinner"></i></div>
      <div v-for="t in searchResults" :key="t.id" class="search-result-item" @click="linkToParent(t.id)">
        <span class="search-id">#{{ shortId(t.id) }}</span>
        <span>{{ t.title }}</span>
        <TicketStatusBadge :status="t.status" />
      </div>
    </Dialog>
  </Panel>
</template>

<style scoped>
.block-label { font-size: 12px; color: #64748b; font-weight: 600; text-transform: uppercase; margin-bottom: 6px; }
.linked-ticket-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 6px 0;
  border-bottom: 1px solid #f1f5f9;
}
.child-info { display: flex; align-items: center; gap: 6px; flex: 1; min-width: 0; }
.child-title { font-size: 13px; color: #475569; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.ticket-link { color: #2563eb; cursor: pointer; font-size: 13px; font-family: monospace; }
.ticket-link:hover { text-decoration: underline; }
.parent-block, .children-block { margin-bottom: 12px; }
.search-result-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  cursor: pointer;
  border-radius: 6px;
  font-size: 14px;
}
.search-result-item:hover { background: #f1f5f9; }
.search-id { font-family: monospace; color: #64748b; }
</style>

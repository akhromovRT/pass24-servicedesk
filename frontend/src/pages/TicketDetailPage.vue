<script setup lang="ts">
import { onMounted, onUnmounted, computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import Button from 'primevue/button'
import Dialog from 'primevue/dialog'
import Tag from 'primevue/tag'
import { useToast } from 'primevue/usetoast'
import TicketStatusBadge from '../components/TicketStatusBadge.vue'
import TicketPriorityBadge from '../components/TicketPriorityBadge.vue'
import TicketConversation from '../components/ticket/TicketConversation.vue'
import TicketComposeArea from '../components/ticket/TicketComposeArea.vue'
import TicketSidebar from '../components/ticket/TicketSidebar.vue'
import { useTicketsStore } from '../stores/tickets'
import { useAuthStore } from '../stores/auth'
import { useTicketPreview } from '../composables/useTicketPreview'
import type { TicketStatus } from '../types'

const route = useRoute()
const router = useRouter()
const toast = useToast()
const store = useTicketsStore()
const auth = useAuthStore()

const isStaff = computed(() =>
  auth.user?.role === 'support_agent' || auth.user?.role === 'admin'
)

const ticket = computed(() => store.currentTicket)

const {
  previewVisible, previewUrl, previewFile, previewLoading,
  isImage, isPdf, isText,
  openPreview, closePreview, downloadAttachment,
} = useTicketPreview()

const categoryLabels: Record<string, string> = {
  registration: 'Регистрация',
  passes: 'Пропуска',
  recognition: 'Распознавание',
  app_issues: 'Приложение',
  objects: 'Объекты',
  trusted_persons: 'Доверенные',
  equipment_issues: 'Оборудование',
  consultation: 'Консультация',
  feature_request: 'Предложение',
  other: 'Другое',
}

function formatDate(dateStr: string): string {
  return new Intl.DateTimeFormat('ru-RU', {
    day: 'numeric',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(dateStr))
}

async function loadTicket() {
  const id = route.params.id as string
  try {
    await store.fetchTicket(id)
  } catch (e: any) {
    toast.add({
      severity: 'error',
      summary: 'Ошибка',
      detail: e.message || 'Не удалось загрузить заявку',
      life: 4000,
    })
    router.push('/')
  }
}

async function handleStatusChange(newStatus: TicketStatus) {
  if (!ticket.value) return
  try {
    await store.updateStatus(ticket.value.id, newStatus)
    toast.add({ severity: 'success', summary: 'Статус обновлён', life: 2000 })
  } catch (e: any) {
    toast.add({ severity: 'error', summary: 'Ошибка', detail: e.message, life: 4000 })
  }
}

async function handleCommentSubmitted() {
  await loadTicket()
}

async function handleFileUploaded() {
  await loadTicket()
}

async function handleAssigned(assigneeId: string | null) {
  if (!ticket.value) return
  try {
    await store.assignTicket(ticket.value.id, assigneeId)
    toast.add({ severity: 'success', summary: assigneeId ? 'Назначено' : 'Назначение снято', life: 2000 })
  } catch (e: any) {
    toast.add({ severity: 'error', summary: 'Ошибка', detail: e.message, life: 4000 })
  }
}

async function handleMacroApplied() {
  await loadTicket()
}

function goBack() {
  router.push('/')
}

// Polling для обновления комментариев (каждые 15 сек)
let pollInterval: ReturnType<typeof setInterval> | null = null

watch(() => route.params.id, (newId, oldId) => {
  if (newId && newId !== oldId) loadTicket()
})

onMounted(() => {
  loadTicket()

  pollInterval = setInterval(async () => {
    if (!ticket.value) return
    const prevCount = ticket.value.comments?.length || 0
    try {
      await store.fetchTicket(route.params.id as string)
      const newCount = ticket.value?.comments?.length || 0
      if (newCount > prevCount) {
        toast.add({
          severity: 'info',
          summary: 'Новый комментарий',
          detail: `Ответ от ${ticket.value?.comments[newCount - 1]?.author_name || 'пользователя'}`,
          life: 5000,
        })
      }
    } catch {}
  }, 15000)
})

onUnmounted(() => {
  if (pollInterval) clearInterval(pollInterval)
})
</script>

<template>
  <div class="ticket-detail-page">
    <!-- Header -->
    <div class="ticket-header">
      <Button
        label="Назад"
        icon="pi pi-arrow-left"
        severity="secondary"
        text
        size="small"
        @click="goBack"
      />
      <div class="header-info" v-if="ticket">
        <span class="ticket-id">#{{ ticket.id.replace(/-/g, '').slice(0, 8).toUpperCase() }}</span>
        <h1 class="ticket-title">{{ ticket.title }}</h1>
        <div class="ticket-meta">
          <TicketStatusBadge :status="ticket.status" :simplified="!isStaff" />
          <TicketPriorityBadge :priority="ticket.priority" />
          <Tag
            v-if="ticket.category"
            :value="categoryLabels[ticket.category] || ticket.category"
            severity="secondary"
          />
          <Tag v-if="ticket.urgent" value="Срочная" severity="danger" />
          <span class="ticket-date">{{ formatDate(ticket.created_at) }}</span>
        </div>
      </div>
    </div>

    <!-- Loading -->
    <div v-if="store.loading && !ticket" class="loading-state">
      <i class="pi pi-spin pi-spinner" style="font-size: 2rem; color: #94a3b8"></i>
    </div>

    <!-- 2-Column Layout -->
    <div v-if="ticket" class="ticket-layout">
      <!-- Center: Conversation -->
      <div class="ticket-center">
        <TicketConversation
          :ticket="ticket"
          :is-staff="isStaff"
          @preview-attachment="openPreview"
        />
        <TicketComposeArea
          :ticket-id="ticket.id"
          :is-staff="isStaff"
          @submitted="handleCommentSubmitted"
          @file-uploaded="handleFileUploaded"
        />
      </div>

      <!-- Right: Sidebar (staff only on desktop, simplified for users) -->
      <div v-if="isStaff" class="ticket-sidebar-col">
        <TicketSidebar
          :ticket="ticket"
          :is-staff="isStaff"
          @status-changed="handleStatusChange"
          @assigned="handleAssigned"
          @macro-applied="handleMacroApplied"
        />
      </div>
    </div>

    <!-- Attachment Preview Dialog -->
    <Dialog
      v-model:visible="previewVisible"
      :header="previewFile?.filename || 'Предпросмотр'"
      modal
      :style="{ width: '80vw', maxWidth: '900px' }"
      @hide="closePreview"
    >
      <div class="preview-container">
        <div v-if="previewLoading" class="preview-loading">
          <i class="pi pi-spin pi-spinner" style="font-size: 2rem"></i>
        </div>
        <template v-else-if="previewUrl">
          <img v-if="isImage" :src="previewUrl" class="preview-image" />
          <iframe v-else-if="isPdf" :src="previewUrl" class="preview-pdf" />
          <iframe v-else-if="isText" :src="previewUrl" class="preview-text" />
          <div v-else class="preview-unsupported">
            <i class="pi pi-file" style="font-size: 3rem; color: #94a3b8"></i>
            <p>Предпросмотр недоступен для этого типа файла</p>
          </div>
        </template>
      </div>
      <template #footer>
        <Button label="Скачать" icon="pi pi-download" @click="downloadAttachment" />
        <Button label="Закрыть" severity="secondary" @click="closePreview" />
      </template>
    </Dialog>
  </div>
</template>

<style scoped>
.ticket-detail-page {
  display: flex;
  flex-direction: column;
  height: calc(100vh - 80px);
  overflow: hidden;
}

.ticket-header {
  display: flex;
  align-items: flex-start;
  gap: 16px;
  padding: 16px 24px;
  border-bottom: 1px solid #e2e8f0;
  background: #fff;
  flex-shrink: 0;
}

.header-info {
  flex: 1;
  min-width: 0;
}

.ticket-id {
  font-family: 'SF Mono', Monaco, monospace;
  font-size: 12px;
  color: #94a3b8;
}

.ticket-title {
  font-size: 18px;
  font-weight: 600;
  color: #0f172a;
  margin: 4px 0 8px;
  line-height: 1.3;
}

.ticket-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.ticket-date {
  font-size: 12px;
  color: #94a3b8;
}

/* 2-Column Layout */
.ticket-layout {
  display: grid;
  grid-template-columns: 1fr 380px;
  flex: 1;
  overflow: hidden;
}

.ticket-center {
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.ticket-sidebar-col {
  border-left: 1px solid #e2e8f0;
  overflow-y: auto;
  background: #fafbfc;
}

/* Loading */
.loading-state {
  display: flex;
  justify-content: center;
  align-items: center;
  flex: 1;
}

/* Preview */
.preview-container {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 400px;
  max-height: 75vh;
  background: #f8fafc;
  border-radius: 8px;
  padding: 12px;
}

.preview-loading { color: #94a3b8; }

.preview-image {
  max-width: 100%;
  max-height: 70vh;
  object-fit: contain;
  border-radius: 4px;
}

.preview-pdf,
.preview-text {
  width: 100%;
  height: 70vh;
  border: none;
  background: white;
  border-radius: 4px;
}

.preview-unsupported {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  color: #64748b;
}

/* Responsive */
@media (max-width: 1024px) {
  .ticket-layout {
    grid-template-columns: 1fr;
  }

  .ticket-sidebar-col {
    border-left: none;
    border-top: 1px solid #e2e8f0;
    max-height: 50vh;
  }
}
</style>

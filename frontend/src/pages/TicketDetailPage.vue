<script setup lang="ts">
import { onMounted, ref, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import Card from 'primevue/card'
import Tag from 'primevue/tag'
import Timeline from 'primevue/timeline'
import Button from 'primevue/button'
import Textarea from 'primevue/textarea'
import Divider from 'primevue/divider'
import { useToast } from 'primevue/usetoast'
import TicketStatusBadge from '../components/TicketStatusBadge.vue'
import TicketPriorityBadge from '../components/TicketPriorityBadge.vue'
import { useTicketsStore } from '../stores/tickets'
import type { TicketStatus } from '../types'

const route = useRoute()
const router = useRouter()
const toast = useToast()
const store = useTicketsStore()

const commentText = ref('')
const submittingComment = ref(false)

const categoryLabels: Record<string, string> = {
  access: 'Доступ',
  pass: 'Пропуска',
  gate: 'Шлагбаум',
  notifications: 'Уведомления',
  general: 'Общее',
  other: 'Другое',
}

interface StatusTransition {
  label: string
  target: TicketStatus
  severity?: string
  icon?: string
}

const statusTransitions: Record<TicketStatus, StatusTransition[]> = {
  new: [
    { label: 'Взять в работу', target: 'in_progress', severity: 'warn', icon: 'pi pi-play' },
    { label: 'Решить', target: 'resolved', severity: 'success', icon: 'pi pi-check' },
  ],
  in_progress: [
    { label: 'Ожидать ответа', target: 'waiting_for_user', severity: 'secondary', icon: 'pi pi-clock' },
    { label: 'Решить', target: 'resolved', severity: 'success', icon: 'pi pi-check' },
  ],
  waiting_for_user: [
    { label: 'Вернуть в работу', target: 'in_progress', severity: 'warn', icon: 'pi pi-replay' },
    { label: 'Решить', target: 'resolved', severity: 'success', icon: 'pi pi-check' },
  ],
  resolved: [
    { label: 'Закрыть', target: 'closed', severity: 'contrast', icon: 'pi pi-lock' },
    { label: 'Переоткрыть', target: 'in_progress', severity: 'warn', icon: 'pi pi-refresh' },
  ],
  closed: [],
}

const ticket = computed(() => store.currentTicket)

const availableTransitions = computed(() => {
  if (!ticket.value) return []
  return statusTransitions[ticket.value.status] || []
})

function formatDate(dateStr: string): string {
  return new Intl.DateTimeFormat('ru-RU', {
    day: 'numeric',
    month: 'long',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(dateStr))
}

function formatShortDate(dateStr: string): string {
  return new Intl.DateTimeFormat('ru-RU', {
    day: 'numeric',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(dateStr))
}

function getCategoryLabel(category: string): string {
  return categoryLabels[category] || category
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

async function changeStatus(newStatus: TicketStatus) {
  if (!ticket.value) return
  try {
    await store.updateStatus(ticket.value.id, newStatus)
    toast.add({
      severity: 'success',
      summary: 'Статус обновлён',
      detail: `Статус заявки изменён`,
      life: 3000,
    })
  } catch (e: any) {
    toast.add({
      severity: 'error',
      summary: 'Ошибка',
      detail: e.message || 'Не удалось изменить статус',
      life: 4000,
    })
  }
}

async function submitComment() {
  if (!ticket.value || !commentText.value.trim()) return
  submittingComment.value = true
  try {
    await store.addComment(ticket.value.id, commentText.value.trim())
    commentText.value = ''
    toast.add({
      severity: 'success',
      summary: 'Комментарий добавлен',
      life: 2000,
    })
  } catch (e: any) {
    toast.add({
      severity: 'error',
      summary: 'Ошибка',
      detail: e.message || 'Не удалось добавить комментарий',
      life: 4000,
    })
  } finally {
    submittingComment.value = false
  }
}

function goBack() {
  router.push('/')
}

onMounted(() => {
  loadTicket()
})
</script>

<template>
  <div class="ticket-detail-page">
    <Button
      label="Назад к заявкам"
      icon="pi pi-arrow-left"
      severity="secondary"
      text
      class="back-button"
      @click="goBack"
    />

    <div v-if="store.loading && !ticket" class="loading-state">
      <i class="pi pi-spin pi-spinner" style="font-size: 2rem; color: #94a3b8"></i>
    </div>

    <template v-if="ticket">
      <!-- Заголовок заявки -->
      <Card class="ticket-header-card">
        <template #content>
          <div class="ticket-header">
            <h2 class="ticket-title">{{ ticket.title }}</h2>
            <div class="ticket-meta">
              <TicketStatusBadge :status="ticket.status" />
              <TicketPriorityBadge :priority="ticket.priority" />
              <Tag
                v-if="ticket.category"
                :value="getCategoryLabel(ticket.category)"
                severity="secondary"
              />
              <Tag
                v-if="ticket.urgent"
                value="Срочная"
                severity="danger"
                icon="pi pi-exclamation-triangle"
              />
            </div>
            <div class="ticket-dates">
              <span>Создана: {{ formatDate(ticket.created_at) }}</span>
              <span v-if="ticket.updated_at !== ticket.created_at">
                Обновлена: {{ formatDate(ticket.updated_at) }}
              </span>
            </div>
          </div>

          <!-- Кнопки смены статуса -->
          <div v-if="availableTransitions.length" class="status-actions">
            <Button
              v-for="transition in availableTransitions"
              :key="transition.target"
              :label="transition.label"
              :icon="transition.icon"
              :severity="transition.severity as any"
              outlined
              size="small"
              @click="changeStatus(transition.target)"
            />
          </div>
        </template>
      </Card>

      <!-- Описание -->
      <Card class="section-card">
        <template #title>Описание</template>
        <template #content>
          <p class="ticket-description">{{ ticket.description }}</p>
          <p v-if="ticket.contact" class="ticket-contact">
            <i class="pi pi-phone"></i> {{ ticket.contact }}
          </p>
        </template>
      </Card>

      <!-- История событий -->
      <Card v-if="ticket.events.length" class="section-card">
        <template #title>История</template>
        <template #content>
          <Timeline :value="ticket.events" class="events-timeline">
            <template #content="{ item }">
              <div class="event-item">
                <span class="event-description">{{ item.description }}</span>
                <span class="event-date">{{ formatShortDate(item.created_at) }}</span>
              </div>
            </template>
          </Timeline>
        </template>
      </Card>

      <!-- Комментарии -->
      <Card class="section-card">
        <template #title>
          Комментарии
          <span v-if="ticket.comments.length" class="comments-count">
            ({{ ticket.comments.length }})
          </span>
        </template>
        <template #content>
          <div v-if="ticket.comments.length" class="comments-list">
            <div
              v-for="comment in ticket.comments"
              :key="comment.id"
              class="comment-item"
            >
              <div class="comment-header">
                <span class="comment-author">{{ comment.author_name }}</span>
                <span class="comment-date">{{ formatShortDate(comment.created_at) }}</span>
              </div>
              <p class="comment-text">{{ comment.text }}</p>
            </div>
          </div>
          <p v-else class="no-comments">Комментариев пока нет</p>

          <Divider />

          <div class="add-comment">
            <Textarea
              v-model="commentText"
              placeholder="Напишите комментарий..."
              rows="3"
              auto-resize
              fluid
            />
            <Button
              label="Отправить"
              icon="pi pi-send"
              :disabled="!commentText.trim()"
              :loading="submittingComment"
              class="comment-submit"
              @click="submitComment"
            />
          </div>
        </template>
      </Card>
    </template>
  </div>
</template>

<style scoped>
.ticket-detail-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
  max-width: 800px;
  margin: 0 auto;
}

.back-button {
  align-self: flex-start;
}

.loading-state {
  display: flex;
  justify-content: center;
  padding: 3rem;
}

.ticket-header {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.ticket-title {
  font-size: 1.375rem;
  font-weight: 600;
  color: #1e293b;
  margin: 0;
}

.ticket-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}

.ticket-dates {
  display: flex;
  gap: 16px;
  font-size: 0.8125rem;
  color: #94a3b8;
}

.status-actions {
  display: flex;
  gap: 8px;
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid #e2e8f0;
}

.section-card {
  width: 100%;
}

.ticket-description {
  white-space: pre-wrap;
  line-height: 1.6;
  color: #334155;
  margin: 0;
}

.ticket-contact {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 12px;
  font-size: 0.875rem;
  color: #64748b;
}

.events-timeline {
  padding: 0;
}

.event-item {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.event-description {
  font-size: 0.875rem;
  color: #334155;
}

.event-date {
  font-size: 0.75rem;
  color: #94a3b8;
}

.comments-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.comments-count {
  font-size: 0.875rem;
  font-weight: 400;
  color: #94a3b8;
}

.comment-item {
  padding: 12px 16px;
  background: #f8fafc;
  border-radius: 8px;
  border: 1px solid #e2e8f0;
}

.comment-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
}

.comment-author {
  font-weight: 600;
  font-size: 0.875rem;
  color: #1e293b;
}

.comment-date {
  font-size: 0.75rem;
  color: #94a3b8;
}

.comment-text {
  margin: 0;
  font-size: 0.875rem;
  line-height: 1.5;
  color: #334155;
  white-space: pre-wrap;
}

.no-comments {
  text-align: center;
  color: #94a3b8;
  padding: 1rem 0;
  margin: 0;
}

.add-comment {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.comment-submit {
  align-self: flex-end;
}
</style>

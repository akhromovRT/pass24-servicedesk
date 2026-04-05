<script setup lang="ts">
import { onMounted, onUnmounted, ref, computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import Card from 'primevue/card'
import Tag from 'primevue/tag'
import Timeline from 'primevue/timeline'
import Button from 'primevue/button'
import Textarea from 'primevue/textarea'
import InputText from 'primevue/inputtext'
import Checkbox from 'primevue/checkbox'
import Divider from 'primevue/divider'
import Dialog from 'primevue/dialog'
import FileUpload from 'primevue/fileupload'
import { useToast } from 'primevue/usetoast'
import TicketStatusBadge from '../components/TicketStatusBadge.vue'
import TicketPriorityBadge from '../components/TicketPriorityBadge.vue'
import { useTicketsStore } from '../stores/tickets'
import { useAuthStore } from '../stores/auth'
import { api } from '../api/client'
import type { TicketStatus, Attachment, TicketPriority, PaginatedResponse, Ticket } from '../types'

const route = useRoute()
const router = useRouter()
const toast = useToast()
const store = useTicketsStore()

const auth = useAuthStore()
const commentText = ref('')
const isInternalComment = ref(false)
const submittingComment = ref(false)
const uploadingFile = ref(false)

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

const typeLabels: Record<string, string> = {
  incident: 'Инцидент',
  problem: 'Проблема',
  question: 'Вопрос',
  request: 'Запрос',
  feature_request: 'Предложение',
}

const sourceLabels: Record<string, string> = {
  web: 'Веб-портал',
  email: 'Email',
  telegram: 'Telegram',
  api: 'API',
  phone: 'Телефон',
}

const isStaff = computed(() =>
  auth.user?.role === 'support_agent' || auth.user?.role === 'admin'
)

// Агентские инструменты
interface Agent { id: string; full_name: string; email: string }
interface ResponseTemplate { id: string; name: string; body: string; usage_count: number }
interface MacroActions { status?: string; comment?: string; is_internal_comment?: boolean; assign_self?: boolean; assignment_group?: string }
interface MacroItem { id: string; name: string; icon?: string; actions: MacroActions }

const agents = ref<Agent[]>([])
const templates = ref<ResponseTemplate[]>([])
const macros = ref<MacroItem[]>([])

async function loadAgentTools() {
  if (!isStaff.value) return
  try {
    const [a, t, m] = await Promise.all([
      (await import('../api/client')).api.get<Agent[]>('/tickets/agents/list'),
      (await import('../api/client')).api.get<ResponseTemplate[]>('/tickets/templates'),
      (await import('../api/client')).api.get<MacroItem[]>('/tickets/macros'),
    ])
    agents.value = a
    templates.value = t
    macros.value = m
  } catch {}
}

async function assignToMe() {
  if (!ticket.value || !auth.user) return
  try {
    await store.assignTicket(ticket.value.id, auth.user.id)
    await loadTicket()
    toast.add({ severity: 'success', summary: 'Назначено вам', life: 2000 })
  } catch (e: any) {
    toast.add({ severity: 'error', summary: 'Ошибка', detail: e.message, life: 4000 })
  }
}

async function assignToAgent(agent_id: string | null) {
  if (!ticket.value) return
  try {
    await store.assignTicket(ticket.value.id, agent_id)
    await loadTicket()
    toast.add({ severity: 'success', summary: agent_id ? 'Назначен агент' : 'Снят', life: 2000 })
  } catch (e: any) {
    toast.add({ severity: 'error', summary: 'Ошибка', detail: e.message, life: 4000 })
  }
}

function insertTemplate(t: ResponseTemplate) {
  commentText.value = (commentText.value ? commentText.value + '\n\n' : '') + t.body
  // fire-and-forget usage counter
  import('../api/client').then(({ api }) => api.post(`/tickets/templates/${t.id}/use`))
}

async function runMacro(m: MacroItem) {
  if (!ticket.value) return
  try {
    await store.applyMacro(ticket.value.id, m.id)
    await loadTicket()
    toast.add({ severity: 'success', summary: `Применён: ${m.name}`, life: 2000 })
  } catch (e: any) {
    toast.add({ severity: 'error', summary: 'Ошибка', detail: e.message, life: 4000 })
  }
}

const agentName = computed(() => {
  if (!ticket.value?.assignee_id) return null
  const a = agents.value.find(x => x.id === ticket.value!.assignee_id)
  return a?.full_name || 'Неизвестный'
})

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
    if (isStaff.value) {
      await Promise.all([loadArticleLinks(), loadChildren(), loadParent()])
    }
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
    await store.addComment(ticket.value.id, commentText.value.trim(), isInternalComment.value)
    commentText.value = ''
    isInternalComment.value = false
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

async function onFileUpload(event: { files: File[] }) {
  if (!ticket.value || !event.files.length) return
  uploadingFile.value = true
  try {
    const file = event.files[0]
    const formData = new FormData()
    formData.append('file', file)
    const token = localStorage.getItem('access_token')
    const resp = await fetch(`/tickets/${ticket.value.id}/attachments`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${token}` },
      body: formData,
    })
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({ detail: 'Ошибка загрузки' }))
      throw new Error(err.detail)
    }
    await loadTicket()
    toast.add({ severity: 'success', summary: 'Файл загружен', life: 2000 })
  } catch (e: any) {
    toast.add({ severity: 'error', summary: 'Ошибка', detail: e.message, life: 4000 })
  } finally {
    uploadingFile.value = false
  }
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} Б`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} КБ`
  return `${(bytes / 1024 / 1024).toFixed(1)} МБ`
}

// ---------- Preview вложений ----------
const previewVisible = ref(false)
const previewUrl = ref<string>('')         // blob: URL для отображения
const previewFile = ref<Attachment | null>(null)
const previewLoading = ref(false)

async function openAttachment(att: Attachment) {
  // Закрываем предыдущий blob URL чтобы не течь память
  if (previewUrl.value) {
    URL.revokeObjectURL(previewUrl.value)
    previewUrl.value = ''
  }
  previewFile.value = att
  previewVisible.value = true
  previewLoading.value = true
  try {
    const token = localStorage.getItem('access_token')
    const resp = await fetch(`/tickets/${att.ticket_id}/attachments/${att.id}`, {
      headers: { Authorization: `Bearer ${token}` },
    })
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
    const blob = await resp.blob()
    previewUrl.value = URL.createObjectURL(blob)
  } catch (e: any) {
    toast.add({ severity: 'error', summary: 'Ошибка', detail: e.message, life: 4000 })
    previewVisible.value = false
  } finally {
    previewLoading.value = false
  }
}

function closePreview() {
  previewVisible.value = false
  if (previewUrl.value) {
    URL.revokeObjectURL(previewUrl.value)
    previewUrl.value = ''
  }
  previewFile.value = null
}

function downloadAttachment() {
  if (!previewUrl.value || !previewFile.value) return
  const a = document.createElement('a')
  a.href = previewUrl.value
  a.download = previewFile.value.filename
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
}

const isImage = computed(() => previewFile.value?.content_type.startsWith('image/') ?? false)
const isPdf = computed(() => previewFile.value?.content_type === 'application/pdf')
const isText = computed(() => previewFile.value?.content_type.startsWith('text/') ?? false)

function goBack() {
  router.push('/')
}

// ---------- KB Article Links ----------
type RelationType = 'helped' | 'related' | 'created_from'

interface ArticleLink {
  id: string
  ticket_id: string
  article_id: string
  article_title: string
  article_slug: string
  relation_type: RelationType
  linked_by: string
  created_at: string
}

interface ArticleSearchResult {
  id: string
  title: string
  slug: string
  category: string
}

const articleLinks = ref<ArticleLink[]>([])
const articleDialogVisible = ref(false)
const articleSearchQuery = ref('')
const articleSearchResults = ref<ArticleSearchResult[]>([])
const articleSearchLoading = ref(false)
const selectedRelationType = ref<RelationType>('helped')

// KB improvement: если клиент пришёл из статьи БЗ
const createdFromArticle = computed(() =>
  articleLinks.value.find(l => l.relation_type === 'created_from')
)
const improvementText = ref('')
const submittingImprovement = ref(false)
const improvementSubmitted = ref(false)

async function submitImprovement() {
  if (!ticket.value || !createdFromArticle.value) return
  submittingImprovement.value = true
  try {
    const { api } = await import('../api/client')
    await api.post(`/tickets/${ticket.value.id}/kb-improvement`, {
      article_id: createdFromArticle.value.article_id,
      suggestion: improvementText.value.trim(),
    })
    improvementSubmitted.value = true
    improvementText.value = ''
    toast.add({ severity: 'success', summary: 'Предложение отправлено', life: 3000 })
  } catch (e: any) {
    toast.add({ severity: 'error', summary: 'Ошибка', detail: e.message, life: 4000 })
  } finally {
    submittingImprovement.value = false
  }
}

const relationLabels: Record<RelationType, string> = {
  helped: 'Помогла решить',
  related: 'Связана',
  created_from: 'Создана из тикета',
}

const relationSeverities: Record<RelationType, string> = {
  helped: 'success',
  related: 'info',
  created_from: 'warn',
}

let articleSearchDebounce: ReturnType<typeof setTimeout> | null = null

async function loadArticleLinks() {
  if (!ticket.value || !isStaff.value) return
  try {
    articleLinks.value = await api.get<ArticleLink[]>(`/tickets/${ticket.value.id}/articles`)
  } catch {
    // тихо
  }
}

function openArticleDialog() {
  articleSearchQuery.value = ''
  articleSearchResults.value = []
  selectedRelationType.value = 'helped'
  articleDialogVisible.value = true
}

function onArticleSearchInput() {
  if (articleSearchDebounce) clearTimeout(articleSearchDebounce)
  const q = articleSearchQuery.value.trim()
  if (!q) {
    articleSearchResults.value = []
    return
  }
  articleSearchDebounce = setTimeout(async () => {
    articleSearchLoading.value = true
    try {
      const data = await api.get<{ items: ArticleSearchResult[] }>(
        `/knowledge/search?query=${encodeURIComponent(q)}&per_page=5`,
      )
      articleSearchResults.value = data.items || []
    } catch {
      articleSearchResults.value = []
    } finally {
      articleSearchLoading.value = false
    }
  }, 300)
}

async function linkArticle(articleId: string) {
  if (!ticket.value) return
  try {
    await api.post(`/tickets/${ticket.value.id}/articles`, {
      article_id: articleId,
      relation_type: selectedRelationType.value,
    })
    articleDialogVisible.value = false
    await loadArticleLinks()
    toast.add({ severity: 'success', summary: 'Статья привязана', life: 2000 })
  } catch (e: any) {
    toast.add({ severity: 'error', summary: 'Ошибка', detail: e.message, life: 4000 })
  }
}

async function unlinkArticle(linkId: string) {
  if (!ticket.value) return
  try {
    await api.delete(`/tickets/${ticket.value.id}/articles/${linkId}`)
    await loadArticleLinks()
    toast.add({ severity: 'success', summary: 'Статья отвязана', life: 2000 })
  } catch (e: any) {
    toast.add({ severity: 'error', summary: 'Ошибка', detail: e.message, life: 4000 })
  }
}

function goToArticle(slug: string) {
  router.push(`/knowledge/${slug}`)
}

// ---------- Parent-Child (Problem → Incidents) ----------
interface ChildTicket {
  id: string
  title: string
  status: TicketStatus
  priority: TicketPriority
  created_at: string
}

interface ChildrenResponse {
  count: number
  items: ChildTicket[]
}

const childTickets = ref<ChildTicket[]>([])
const childrenCount = ref(0)
const parentTicket = ref<{ id: string; title: string } | null>(null)
const parentDialogVisible = ref(false)
const parentSearchQuery = ref('')
const parentSearchResults = ref<Ticket[]>([])
const parentSearchLoading = ref(false)

let parentSearchDebounce: ReturnType<typeof setTimeout> | null = null

async function loadChildren() {
  if (!ticket.value || !isStaff.value) return
  try {
    const data = await api.get<ChildrenResponse>(`/tickets/${ticket.value.id}/children`)
    childTickets.value = data.items || []
    childrenCount.value = data.count || 0
  } catch {
    childTickets.value = []
    childrenCount.value = 0
  }
}

async function loadParent() {
  if (!ticket.value || !isStaff.value || !ticket.value.parent_ticket_id) {
    parentTicket.value = null
    return
  }
  try {
    const data = await api.get<Ticket>(`/tickets/${ticket.value.parent_ticket_id}`)
    parentTicket.value = { id: data.id, title: data.title }
  } catch {
    parentTicket.value = null
  }
}

function openParentDialog() {
  parentSearchQuery.value = ''
  parentSearchResults.value = []
  parentDialogVisible.value = true
}

function onParentSearchInput() {
  if (parentSearchDebounce) clearTimeout(parentSearchDebounce)
  const q = parentSearchQuery.value.trim()
  if (!q) {
    parentSearchResults.value = []
    return
  }
  parentSearchDebounce = setTimeout(async () => {
    parentSearchLoading.value = true
    try {
      const data = await api.get<PaginatedResponse<Ticket>>(
        `/tickets/?q=${encodeURIComponent(q)}&per_page=10&page=1`,
      )
      parentSearchResults.value = (data.items || []).filter(t => t.id !== ticket.value?.id)
    } catch {
      parentSearchResults.value = []
    } finally {
      parentSearchLoading.value = false
    }
  }, 300)
}

async function linkToParent(parentId: string) {
  if (!ticket.value) return
  try {
    await api.put(`/tickets/${ticket.value.id}/parent`, { parent_ticket_id: parentId })
    parentDialogVisible.value = false
    await loadTicket()
    await loadParent()
    toast.add({ severity: 'success', summary: 'Привязано к Problem', life: 2000 })
  } catch (e: any) {
    toast.add({ severity: 'error', summary: 'Ошибка', detail: e.message, life: 4000 })
  }
}

async function unlinkFromParent() {
  if (!ticket.value) return
  try {
    await api.delete(`/tickets/${ticket.value.id}/parent`)
    await loadTicket()
    parentTicket.value = null
    toast.add({ severity: 'success', summary: 'Отвязано от Problem', life: 2000 })
  } catch (e: any) {
    toast.add({ severity: 'error', summary: 'Ошибка', detail: e.message, life: 4000 })
  }
}

function goToTicket(id: string) {
  router.push(`/tickets/${id}`)
}

function shortId(id: string): string {
  return id.replace(/-/g, '').slice(0, 8).toUpperCase()
}

const statusLabels: Record<TicketStatus, string> = {
  new: 'Новая',
  in_progress: 'В работе',
  waiting_for_user: 'Ждёт ответа',
  resolved: 'Решена',
  closed: 'Закрыта',
}

const priorityLabels: Record<TicketPriority, string> = {
  low: 'Низкий',
  normal: 'Обычный',
  high: 'Высокий',
  critical: 'Критический',
}

const statusSeverities: Record<TicketStatus, string> = {
  new: 'info',
  in_progress: 'warn',
  waiting_for_user: 'secondary',
  resolved: 'success',
  closed: 'contrast',
}

const prioritySeverities: Record<TicketPriority, string> = {
  low: 'secondary',
  normal: 'info',
  high: 'warn',
  critical: 'danger',
}

// Polling для обновления комментариев (каждые 15 сек)
let pollInterval: ReturnType<typeof setInterval> | null = null

watch(() => route.params.id, (newId, oldId) => {
  if (newId && newId !== oldId) {
    loadTicket()
  }
})

onMounted(() => {
  loadTicket()
  loadAgentTools()

  // Auto-refresh для агентов — показывать новые комментарии
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
          detail: `Получен ответ от ${ticket.value?.comments[newCount - 1]?.author_name || 'пользователя'}`,
          life: 5000,
        })
      }
    } catch {
      // Игнорируем ошибки polling
    }
  }, 15000)
})

onUnmounted(() => {
  if (pollInterval) clearInterval(pollInterval)
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
        <template #title>
          <div class="card-title-row"><i class="pi pi-file-edit" /> Описание</div>
        </template>
        <template #content>
          <p class="ticket-description">{{ ticket.description }}</p>
        </template>
      </Card>

      <!-- Информация -->
      <Card class="section-card">
        <template #title>
          <div class="card-title-row"><i class="pi pi-info-circle" /> Информация</div>
        </template>
        <template #content>
          <div class="info-grid">
            <!-- Контакт -->
            <div v-if="ticket.contact_email || ticket.contact_phone || ticket.contact_name || ticket.company" class="info-block" style="--accent:#3b82f6">
              <div class="info-header">
                <i class="pi pi-user info-icon" />
                <span class="info-title">Контакт</span>
              </div>
              <div class="info-items">
                <div v-if="ticket.contact_name" class="info-item">
                  <span class="info-label">Имя</span>
                  <span class="info-value">{{ ticket.contact_name }}</span>
                </div>
                <div v-if="ticket.contact_email" class="info-item">
                  <span class="info-label">Email</span>
                  <a :href="`mailto:${ticket.contact_email}`" class="info-value info-link">{{ ticket.contact_email }}</a>
                </div>
                <div v-if="ticket.contact_phone" class="info-item">
                  <span class="info-label">Телефон</span>
                  <a :href="`tel:${ticket.contact_phone}`" class="info-value info-link">{{ ticket.contact_phone }}</a>
                </div>
                <div v-if="ticket.company" class="info-item">
                  <span class="info-label">Компания</span>
                  <span class="info-value">{{ ticket.company }}</span>
                </div>
              </div>
            </div>

            <!-- Объект -->
            <div v-if="ticket.object_name || ticket.access_point || ticket.object_address" class="info-block" style="--accent:#8b5cf6">
              <div class="info-header">
                <i class="pi pi-building info-icon" />
                <span class="info-title">Объект</span>
              </div>
              <div class="info-items">
                <div v-if="ticket.object_name" class="info-item">
                  <span class="info-label">Название</span>
                  <span class="info-value">{{ ticket.object_name }}</span>
                </div>
                <div v-if="ticket.object_address" class="info-item">
                  <span class="info-label">Адрес</span>
                  <span class="info-value">{{ ticket.object_address }}</span>
                </div>
                <div v-if="ticket.access_point" class="info-item">
                  <span class="info-label">КПП / дверь</span>
                  <span class="info-value">{{ ticket.access_point }}</span>
                </div>
              </div>
            </div>

            <!-- Классификация -->
            <div v-if="ticket.product || ticket.ticket_type || ticket.source" class="info-block" style="--accent:#10b981">
              <div class="info-header">
                <i class="pi pi-tag info-icon" />
                <span class="info-title">Классификация</span>
              </div>
              <div class="info-items">
                <div v-if="ticket.product" class="info-item">
                  <span class="info-label">Продукт</span>
                  <span class="info-value">{{ productLabels[ticket.product] || ticket.product }}</span>
                </div>
                <div v-if="ticket.ticket_type" class="info-item">
                  <span class="info-label">Тип</span>
                  <span class="info-value">{{ typeLabels[ticket.ticket_type] || ticket.ticket_type }}</span>
                </div>
                <div v-if="ticket.source" class="info-item">
                  <span class="info-label">Источник</span>
                  <span class="info-value">{{ sourceLabels[ticket.source] || ticket.source }}</span>
                </div>
              </div>
            </div>

            <!-- Техника -->
            <div v-if="ticket.device_type || ticket.app_version || ticket.error_message" class="info-block" style="--accent:#f59e0b">
              <div class="info-header">
                <i class="pi pi-desktop info-icon" />
                <span class="info-title">Техническая информация</span>
              </div>
              <div class="info-items">
                <div v-if="ticket.device_type" class="info-item">
                  <span class="info-label">Устройство</span>
                  <span class="info-value">{{ ticket.device_type }}</span>
                </div>
                <div v-if="ticket.app_version" class="info-item">
                  <span class="info-label">Версия</span>
                  <span class="info-value info-mono">v{{ ticket.app_version }}</span>
                </div>
                <div v-if="ticket.error_message" class="info-item">
                  <span class="info-label">Ошибка</span>
                  <span class="info-value info-mono">{{ ticket.error_message }}</span>
                </div>
              </div>
            </div>
          </div>

          <!-- SLA -->
          <div v-if="isStaff" class="sla-section">
            <Divider />
            <div class="sla-header">
              <i class="pi pi-clock" />
              <span>SLA — соблюдение сроков</span>
            </div>
            <div class="sla-cards">
              <div class="sla-card" :class="ticket.first_response_at ? 'done' : 'pending'">
                <div class="sla-card-label">Первый ответ</div>
                <div class="sla-card-value">
                  <template v-if="ticket.first_response_at">
                    <i class="pi pi-check-circle" /> {{ formatDate(ticket.first_response_at) }}
                  </template>
                  <template v-else>
                    <i class="pi pi-hourglass" /> Ожидает ответа
                  </template>
                </div>
                <div class="sla-card-target">Цель: {{ ticket.sla_response_hours || 4 }} часов</div>
              </div>
              <div class="sla-card" :class="ticket.resolved_at ? 'done' : 'pending'">
                <div class="sla-card-label">Решение</div>
                <div class="sla-card-value">
                  <template v-if="ticket.resolved_at">
                    <i class="pi pi-check-circle" /> {{ formatDate(ticket.resolved_at) }}
                  </template>
                  <template v-else>
                    <i class="pi pi-spin pi-spinner" /> В процессе
                  </template>
                </div>
                <div class="sla-card-target">Цель: {{ ticket.sla_resolve_hours || 24 }} часов</div>
              </div>
            </div>
          </div>
        </template>
      </Card>

      <!-- Вложения -->
      <Card class="section-card">
        <template #title>
          Вложения
          <span v-if="ticket.attachments.length" class="comments-count">
            ({{ ticket.attachments.length }})
          </span>
        </template>
        <template #content>
          <div v-if="ticket.attachments.length" class="attachments-list">
            <button
              v-for="att in ticket.attachments"
              :key="att.id"
              type="button"
              class="attachment-item"
              @click="openAttachment(att)"
            >
              <i :class="att.content_type.startsWith('image/') ? 'pi pi-image' : 'pi pi-file'" />
              <span class="att-name">{{ att.filename }}</span>
              <span class="att-size">{{ formatFileSize(att.size) }}</span>
            </button>
          </div>
          <p v-else class="no-comments">Вложений нет</p>
          <Divider />
          <FileUpload
            mode="basic"
            :auto="true"
            choose-label="Загрузить файл"
            :disabled="uploadingFile"
            accept="image/*,.pdf,.doc,.docx,.txt"
            :max-file-size="10485760"
            @select="onFileUpload"
          />
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

      <!-- Агентская панель (только для staff) -->
      <Card v-if="isStaff" class="section-card agent-panel">
        <template #title>Управление заявкой</template>
        <template #content>
          <div class="agent-panel-grid">
            <!-- Назначение -->
            <div class="panel-block">
              <div class="panel-label">Назначено:</div>
              <div class="panel-row">
                <span v-if="agentName" class="assignee-name">{{ agentName }}</span>
                <span v-else class="assignee-none">не назначен</span>
                <div class="panel-actions">
                  <Button
                    v-if="ticket.assignee_id !== auth.user?.id"
                    label="Взять себе" icon="pi pi-user-plus"
                    size="small" severity="secondary" outlined
                    @click="assignToMe"
                  />
                  <select
                    v-model="ticket.assignee_id"
                    class="agent-select"
                    @change="assignToAgent(($event.target as HTMLSelectElement).value || null)"
                  >
                    <option value="">— не назначен —</option>
                    <option v-for="a in agents" :key="a.id" :value="a.id">{{ a.full_name }}</option>
                  </select>
                </div>
              </div>
            </div>

            <!-- Макросы -->
            <div v-if="macros.length" class="panel-block">
              <div class="panel-label">Быстрые действия:</div>
              <div class="macros-row">
                <Button
                  v-for="m in macros" :key="m.id"
                  :label="m.name" :icon="m.icon || 'pi pi-bolt'"
                  size="small" severity="secondary" outlined
                  @click="runMacro(m)"
                />
              </div>
            </div>
          </div>
        </template>
      </Card>

      <!-- Связанные статьи (KB) — только для staff -->
      <Card v-if="isStaff" class="section-card">
        <template #title>
          <div class="card-title-row"><i class="pi pi-book" /> Связанные статьи</div>
        </template>
        <template #content>
          <div v-if="articleLinks.length" class="linked-articles-list">
            <div
              v-for="link in articleLinks"
              :key="link.id"
              class="linked-article-item"
            >
              <button
                type="button"
                class="linked-article-title"
                @click="goToArticle(link.article_slug)"
              >
                <i class="pi pi-file" />
                <span>{{ link.article_title }}</span>
              </button>
              <Tag
                :value="relationLabels[link.relation_type]"
                :severity="relationSeverities[link.relation_type] as any"
                class="relation-tag"
              />
              <Button
                icon="pi pi-trash"
                severity="danger"
                text
                rounded
                size="small"
                aria-label="Отвязать"
                @click="unlinkArticle(link.id)"
              />
            </div>
          </div>
          <p v-else class="no-comments">Статьи не привязаны</p>
          <Divider />
          <Button
            label="Привязать статью"
            icon="pi pi-plus"
            size="small"
            severity="secondary"
            outlined
            @click="openArticleDialog"
          />

          <!-- Блок: клиент пришёл из статьи БЗ → предложение улучшить -->
          <div v-if="createdFromArticle" class="improve-article-block">
            <Divider />
            <div class="improve-hint">
              <i class="pi pi-info-circle" />
              <div>
                <b>Клиент пришёл из этой статьи</b> и не нашёл ответа.
                После решения тикета предложите улучшение — чтобы такие вопросы
                больше не возникали.
              </div>
            </div>
            <Textarea
              v-model="improvementText"
              placeholder="Что стоит добавить/изменить в статье? Например: 'Добавить шаг про сброс приложения', 'Описать кейс на iOS 17', 'Привести скриншот кнопки'"
              rows="3"
              auto-resize
              fluid
              class="improve-input"
            />
            <Button
              label="Отправить предложение"
              icon="pi pi-send"
              size="small"
              :disabled="improvementText.trim().length < 10"
              :loading="submittingImprovement"
              class="improve-submit"
              @click="submitImprovement"
            />
            <p v-if="improvementSubmitted" class="improve-success">
              <i class="pi pi-check-circle" /> Спасибо! Предложение отправлено администратору.
            </p>
          </div>
        </template>
      </Card>

      <!-- Связь с Problem — только для staff -->
      <Card v-if="isStaff" class="section-card">
        <template #title>
          <div class="card-title-row"><i class="pi pi-sitemap" /> Связь с Problem</div>
        </template>
        <template #content>
          <!-- Ticket linked to a parent -->
          <template v-if="ticket.parent_ticket_id">
            <div class="parent-banner">
              <i class="pi pi-link parent-banner-icon" />
              <div class="parent-banner-content">
                <div class="parent-banner-label">Связан с Problem</div>
                <button
                  type="button"
                  class="parent-banner-link"
                  @click="goToTicket(ticket.parent_ticket_id!)"
                >
                  #{{ shortId(ticket.parent_ticket_id) }}<template v-if="parentTicket"> — {{ parentTicket.title }}</template>
                </button>
              </div>
              <Button
                label="Отвязать"
                icon="pi pi-times"
                severity="secondary"
                outlined
                size="small"
                @click="unlinkFromParent"
              />
            </div>
          </template>

          <!-- Ticket has children (is a Problem) -->
          <template v-else-if="childrenCount > 0">
            <div class="children-header">
              Связанные инциденты ({{ childrenCount }})
            </div>
            <div class="children-list">
              <button
                v-for="child in childTickets"
                :key="child.id"
                type="button"
                class="child-item"
                @click="goToTicket(child.id)"
              >
                <span class="child-id">#{{ shortId(child.id) }}</span>
                <span class="child-title">{{ child.title }}</span>
                <Tag
                  :value="statusLabels[child.status]"
                  :severity="statusSeverities[child.status] as any"
                  class="child-tag"
                />
                <Tag
                  :value="priorityLabels[child.priority]"
                  :severity="prioritySeverities[child.priority] as any"
                  class="child-tag"
                />
              </button>
            </div>
          </template>

          <!-- Regular ticket, not linked -->
          <template v-else>
            <p class="no-comments">Заявка не связана с Problem</p>
            <Divider />
            <Button
              label="Привязать к Problem"
              icon="pi pi-link"
              size="small"
              severity="secondary"
              outlined
              @click="openParentDialog"
            />
          </template>
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
              :class="['comment-item', { 'comment-internal': comment.is_internal }]"
            >
              <div class="comment-header">
                <span class="comment-author">{{ comment.author_name }}</span>
                <Tag v-if="comment.is_internal" value="Внутренний" severity="warn" class="internal-tag" />
                <span class="comment-date">{{ formatShortDate(comment.created_at) }}</span>
              </div>
              <p class="comment-text">{{ comment.text }}</p>
            </div>
          </div>
          <p v-else class="no-comments">Комментариев пока нет</p>

          <Divider />

          <div class="add-comment">
            <!-- Templates (для агентов) -->
            <div v-if="isStaff && templates.length" class="templates-row">
              <span class="templates-label">Шаблоны:</span>
              <button
                v-for="t in templates" :key="t.id"
                type="button"
                class="template-chip"
                :title="t.body"
                @click="insertTemplate(t)"
              >
                {{ t.name }}
              </button>
            </div>

            <Textarea
              v-model="commentText"
              placeholder="Напишите комментарий..."
              rows="3"
              auto-resize
              fluid
            />
            <div class="comment-actions">
              <div v-if="isStaff" class="internal-check">
                <Checkbox v-model="isInternalComment" input-id="internal" :binary="true" />
                <label for="internal">Внутренний (не виден клиенту)</label>
              </div>
              <Button
                label="Отправить"
                icon="pi pi-send"
                :disabled="!commentText.trim()"
                :loading="submittingComment"
                @click="submitComment"
              />
            </div>
          </div>
        </template>
      </Card>
    </template>

    <!-- Preview модальное окно -->
    <Dialog
      v-model:visible="previewVisible"
      modal
      :header="previewFile?.filename || 'Вложение'"
      :style="{ width: '80vw', maxWidth: '1000px' }"
      :breakpoints="{ '960px': '95vw' }"
      @hide="closePreview"
    >
      <div class="preview-container">
        <div v-if="previewLoading" class="preview-loading">
          <i class="pi pi-spin pi-spinner" style="font-size: 2rem" />
        </div>
        <template v-else-if="previewUrl">
          <img v-if="isImage" :src="previewUrl" :alt="previewFile?.filename" class="preview-image" />
          <iframe
            v-else-if="isPdf"
            :src="previewUrl"
            class="preview-pdf"
            :title="previewFile?.filename"
          />
          <iframe
            v-else-if="isText"
            :src="previewUrl"
            class="preview-text"
            :title="previewFile?.filename"
          />
          <div v-else class="preview-unsupported">
            <i class="pi pi-file" style="font-size: 3rem; color: #94a3b8" />
            <p>Предпросмотр недоступен для этого типа файла</p>
            <p class="preview-filetype">{{ previewFile?.content_type }}</p>
          </div>
        </template>
      </div>
      <template #footer>
        <Button label="Скачать" icon="pi pi-download" severity="secondary" outlined @click="downloadAttachment" />
        <Button label="Закрыть" icon="pi pi-times" @click="closePreview" />
      </template>
    </Dialog>

    <!-- Диалог поиска статей KB -->
    <Dialog
      v-model:visible="articleDialogVisible"
      modal
      header="Привязать статью"
      :style="{ width: '560px' }"
      :breakpoints="{ '640px': '95vw' }"
    >
      <div class="search-dialog">
        <div class="search-relation-row">
          <label class="search-relation-label">Тип связи:</label>
          <select v-model="selectedRelationType" class="search-relation-select">
            <option value="helped">Помогла решить</option>
            <option value="related">Связана</option>
            <option value="created_from">Создана из тикета</option>
          </select>
        </div>
        <InputText
          v-model="articleSearchQuery"
          placeholder="Поиск по базе знаний..."
          fluid
          autofocus
          @input="onArticleSearchInput"
        />
        <div v-if="articleSearchLoading" class="search-loading">
          <i class="pi pi-spin pi-spinner" /> Поиск...
        </div>
        <div v-else-if="articleSearchResults.length" class="search-results">
          <button
            v-for="r in articleSearchResults"
            :key="r.id"
            type="button"
            class="search-result-item"
            @click="linkArticle(r.id)"
          >
            <span class="search-result-title">{{ r.title }}</span>
            <span class="search-result-meta">{{ r.category }}</span>
          </button>
        </div>
        <p v-else-if="articleSearchQuery" class="search-empty">Ничего не найдено</p>
      </div>
    </Dialog>

    <!-- Диалог поиска родительского тикета -->
    <Dialog
      v-model:visible="parentDialogVisible"
      modal
      header="Привязать к Problem"
      :style="{ width: '560px' }"
      :breakpoints="{ '640px': '95vw' }"
    >
      <div class="search-dialog">
        <InputText
          v-model="parentSearchQuery"
          placeholder="Поиск заявки по названию или номеру..."
          fluid
          autofocus
          @input="onParentSearchInput"
        />
        <div v-if="parentSearchLoading" class="search-loading">
          <i class="pi pi-spin pi-spinner" /> Поиск...
        </div>
        <div v-else-if="parentSearchResults.length" class="search-results">
          <button
            v-for="t in parentSearchResults"
            :key="t.id"
            type="button"
            class="search-result-item"
            @click="linkToParent(t.id)"
          >
            <span class="search-result-id">#{{ shortId(t.id) }}</span>
            <span class="search-result-title">{{ t.title }}</span>
            <Tag
              :value="statusLabels[t.status]"
              :severity="statusSeverities[t.status] as any"
              class="search-result-tag"
            />
          </button>
        </div>
        <p v-else-if="parentSearchQuery" class="search-empty">Ничего не найдено</p>
      </div>
    </Dialog>
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
  line-height: 1.7;
  color: #334155;
  margin: 0;
  font-size: 15px;
}

.card-title-row {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 15px;
  font-weight: 600;
  color: #0f172a;
}
.card-title-row i { color: #3b82f6; font-size: 16px; }

/* Info grid — красивые блоки с цветными акцентами */
.info-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 12px;
}

.info-block {
  background: #fafbfc;
  border: 1px solid #f1f5f9;
  border-left: 3px solid var(--accent);
  border-radius: 10px;
  padding: 14px 16px;
}

.info-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
}

.info-icon {
  color: var(--accent);
  font-size: 15px;
}

.info-title {
  font-size: 12px;
  font-weight: 700;
  color: #64748b;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.info-items {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.info-item {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.info-label {
  font-size: 11px;
  color: #94a3b8;
  text-transform: uppercase;
  letter-spacing: 0.03em;
}

.info-value {
  font-size: 14px;
  color: #1e293b;
  font-weight: 500;
  word-break: break-word;
}

.info-link {
  color: #3b82f6;
  text-decoration: none;
}
.info-link:hover { text-decoration: underline; }

.info-mono {
  font-family: 'SF Mono', Monaco, monospace;
  font-size: 13px;
  background: #f1f5f9;
  padding: 2px 6px;
  border-radius: 4px;
  display: inline-block;
  width: fit-content;
}

/* SLA section */
.sla-section { margin-top: 8px; }

.sla-header {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  font-weight: 600;
  color: #64748b;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  margin-bottom: 12px;
}
.sla-header i { color: #3b82f6; font-size: 14px; }

.sla-cards {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

.sla-card {
  padding: 14px 16px;
  border-radius: 10px;
  border: 1px solid #f1f5f9;
  background: #fafbfc;
  transition: all 0.15s;
}

.sla-card.done {
  background: linear-gradient(135deg, #ecfdf5, #f0fdf4);
  border-color: #a7f3d0;
}
.sla-card.done .sla-card-value { color: #047857; }

.sla-card.pending {
  background: linear-gradient(135deg, #fef3c7, #fffbeb);
  border-color: #fde68a;
}
.sla-card.pending .sla-card-value { color: #92400e; }

.sla-card-label {
  font-size: 11px;
  font-weight: 700;
  color: #64748b;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  margin-bottom: 6px;
}

.sla-card-value {
  font-size: 14px;
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 4px;
}
.sla-card-value i { font-size: 14px; }

.sla-card-target {
  font-size: 12px;
  color: #94a3b8;
}

@media (max-width: 600px) {
  .sla-cards { grid-template-columns: 1fr; }
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

.sla-info {
  margin-top: 8px;
}

.sla-row {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 0.875rem;
  margin-bottom: 6px;
}

.sla-label {
  font-weight: 500;
  min-width: 110px;
}

.sla-target {
  color: #94a3b8;
  font-size: 0.8rem;
}

.attachments-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.attachment-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  text-decoration: none;
  color: #1e293b;
  font-size: 0.875rem;
  font-family: inherit;
  text-align: left;
  cursor: pointer;
  transition: background 0.15s, border-color 0.15s;
}

.attachment-item:hover {
  background: #f1f5f9;
  border-color: #cbd5e1;
}

.attachment-item:focus-visible {
  outline: 2px solid #3b82f6;
  outline-offset: 2px;
}

/* Preview модальное окно */
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

.preview-loading {
  color: #94a3b8;
}

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
  text-align: center;
}

.preview-filetype {
  font-family: 'SF Mono', 'Monaco', monospace;
  font-size: 12px;
  color: #94a3b8;
  background: #fff;
  padding: 4px 10px;
  border-radius: 4px;
  border: 1px solid #e2e8f0;
}

.att-name {
  flex: 1;
}

.att-size {
  color: #94a3b8;
  font-size: 0.8rem;
}

.comment-internal {
  border-left: 3px solid #f59e0b !important;
  background: #fffbeb !important;
}

.internal-tag {
  font-size: 0.7rem;
}

.add-comment {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

/* Templates */
.templates-row { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
.templates-label { font-size: 12px; color: #94a3b8; }
.template-chip {
  background: #f1f5f9; border: 1px solid #e2e8f0; border-radius: 14px;
  padding: 4px 10px; font-size: 12px; color: #475569; cursor: pointer;
  transition: background 0.15s, border-color 0.15s; font-family: inherit;
}
.template-chip:hover { background: #e0f2fe; border-color: #7dd3fc; color: #0369a1; }

/* Agent panel */
.agent-panel { border-left: 3px solid #3b82f6; background: #f0f9ff; }
.agent-panel-grid { display: flex; flex-direction: column; gap: 16px; }
.panel-block { display: flex; flex-direction: column; gap: 6px; }
.panel-label { font-size: 12px; color: #64748b; font-weight: 600; }
.panel-row { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.assignee-name { font-weight: 600; color: #1e293b; }
.assignee-none { color: #94a3b8; font-style: italic; }
.panel-actions { display: flex; gap: 8px; align-items: center; margin-left: auto; flex-wrap: wrap; }
.agent-select {
  border: 1px solid #cbd5e1; border-radius: 6px; padding: 4px 8px;
  font-size: 13px; background: white; color: #1e293b;
}
.macros-row { display: flex; gap: 8px; flex-wrap: wrap; }

.comment-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.internal-check {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 0.85rem;
}

.internal-check label {
  cursor: pointer;
  color: #64748b;
}

/* Связанные статьи (KB) */
.linked-articles-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

/* KB improvement block */
.improve-article-block { display: flex; flex-direction: column; gap: 10px; }
.improve-hint {
  display: flex; gap: 10px; align-items: flex-start;
  background: #fef3c7; border: 1px solid #fcd34d; border-radius: 8px;
  padding: 10px 12px; font-size: 13px; color: #78350f; line-height: 1.5;
}
.improve-hint .pi-info-circle { font-size: 16px; color: #d97706; flex-shrink: 0; margin-top: 2px; }
.improve-input { font-size: 13px; }
.improve-submit { align-self: flex-end; }
.improve-success {
  color: #059669; font-size: 13px; display: flex; align-items: center; gap: 6px; margin: 0;
}

.linked-article-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 12px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
}

.linked-article-title {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 8px;
  background: none;
  border: none;
  padding: 0;
  text-align: left;
  font-family: inherit;
  font-size: 14px;
  color: #1e293b;
  cursor: pointer;
  transition: color 0.15s;
}
.linked-article-title:hover { color: #3b82f6; text-decoration: underline; }
.linked-article-title i { color: #94a3b8; font-size: 14px; }

.relation-tag {
  flex-shrink: 0;
}

/* Связь с Problem */
.parent-banner {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  background: linear-gradient(135deg, #eff6ff, #f0f9ff);
  border: 1px solid #bfdbfe;
  border-radius: 10px;
}

.parent-banner-icon {
  color: #3b82f6;
  font-size: 18px;
}

.parent-banner-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.parent-banner-label {
  font-size: 11px;
  color: #64748b;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  font-weight: 700;
}

.parent-banner-link {
  background: none;
  border: none;
  padding: 0;
  text-align: left;
  font-family: inherit;
  font-size: 14px;
  font-weight: 600;
  color: #1e40af;
  cursor: pointer;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.parent-banner-link:hover { text-decoration: underline; }

.children-header {
  font-size: 12px;
  font-weight: 700;
  color: #64748b;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  margin-bottom: 10px;
}

.children-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.child-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  cursor: pointer;
  text-align: left;
  font-family: inherit;
  transition: background 0.15s, border-color 0.15s;
}
.child-item:hover { background: #f1f5f9; border-color: #cbd5e1; }

.child-id {
  font-family: 'SF Mono', Monaco, monospace;
  font-size: 12px;
  font-weight: 600;
  color: #64748b;
  background: #e2e8f0;
  padding: 2px 6px;
  border-radius: 4px;
  flex-shrink: 0;
}

.child-title {
  flex: 1;
  font-size: 14px;
  color: #1e293b;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.child-tag {
  flex-shrink: 0;
}

/* Поисковые диалоги */
.search-dialog {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.search-relation-row {
  display: flex;
  align-items: center;
  gap: 10px;
}

.search-relation-label {
  font-size: 13px;
  color: #64748b;
  font-weight: 500;
}

.search-relation-select {
  flex: 1;
  border: 1px solid #cbd5e1;
  border-radius: 6px;
  padding: 6px 10px;
  font-size: 13px;
  background: white;
  color: #1e293b;
  font-family: inherit;
}

.search-loading {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #94a3b8;
  font-size: 13px;
  padding: 8px 0;
}

.search-results {
  display: flex;
  flex-direction: column;
  gap: 6px;
  max-height: 360px;
  overflow-y: auto;
}

.search-result-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  cursor: pointer;
  text-align: left;
  font-family: inherit;
  transition: background 0.15s, border-color 0.15s;
}
.search-result-item:hover { background: #e0f2fe; border-color: #7dd3fc; }

.search-result-id {
  font-family: 'SF Mono', Monaco, monospace;
  font-size: 12px;
  font-weight: 600;
  color: #64748b;
  background: #e2e8f0;
  padding: 2px 6px;
  border-radius: 4px;
  flex-shrink: 0;
}

.search-result-title {
  flex: 1;
  font-size: 14px;
  color: #1e293b;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.search-result-meta {
  font-size: 12px;
  color: #94a3b8;
  flex-shrink: 0;
}

.search-result-tag {
  flex-shrink: 0;
}

.search-empty {
  text-align: center;
  color: #94a3b8;
  font-size: 13px;
  padding: 1rem 0;
  margin: 0;
}
</style>

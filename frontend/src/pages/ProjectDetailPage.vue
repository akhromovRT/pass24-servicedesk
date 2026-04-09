<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import Button from 'primevue/button'
import Card from 'primevue/card'
import ProgressBar from 'primevue/progressbar'
import Tabs from 'primevue/tabs'
import TabList from 'primevue/tablist'
import Tab from 'primevue/tab'
import TabPanels from 'primevue/tabpanels'
import TabPanel from 'primevue/tabpanel'
import Textarea from 'primevue/textarea'
import InputText from 'primevue/inputtext'
import Checkbox from 'primevue/checkbox'
import Divider from 'primevue/divider'
import Dialog from 'primevue/dialog'
import Select from 'primevue/select'
import DatePicker from 'primevue/datepicker'
import FileUpload from 'primevue/fileupload'
import { useToast } from 'primevue/usetoast'
import ProjectStatusBadge from '../components/ProjectStatusBadge.vue'
import ProjectTypeBadge from '../components/ProjectTypeBadge.vue'
import ProjectTimeline from '../components/ProjectTimeline.vue'
import PhaseCard from '../components/PhaseCard.vue'
import PhaseApproval from '../components/project/PhaseApproval.vue'
import RiskPanel from '../components/project/RiskPanel.vue'
import GanttChart from '../components/project/GanttChart.vue'
import { useProjectsStore } from '../stores/projects'
import { useAuthStore } from '../stores/auth'
import type {
  LinkedTicket,
  ProjectComment,
  ProjectDocument,
  ProjectEvent,
  ProjectStatus,
  ProjectTeamMember,
  TaskPriority,
} from '../types'

const route = useRoute()
const router = useRouter()
const store = useProjectsStore()
const auth = useAuthStore()
const toast = useToast()

const projectId = computed(() => route.params.id as string)
const project = computed(() => store.currentProject)

const isStaff = computed(() =>
  auth.user?.role === 'support_agent' || auth.user?.role === 'admin',
)
const isPropertyManager = computed(() => auth.user?.role === 'property_manager')
const canEdit = computed(() => isStaff.value)

const activeTab = ref('0')

// Таб-данные (загружаются по требованию)
const documents = ref<ProjectDocument[]>([])
const team = ref<ProjectTeamMember[]>([])
const events = ref<ProjectEvent[]>([])
const tickets = ref<LinkedTicket[]>([])
const comments = ref<ProjectComment[]>([])

const newCommentText = ref('')
const newCommentInternal = ref(false)
const postingComment = ref(false)

// FSM transitions
const transitionOptions = computed(() => {
  if (!project.value || !canEdit.value) return []
  const current = project.value.status
  const map: Record<ProjectStatus, { label: string; to: ProjectStatus; severity: string }[]> = {
    draft: [
      { label: 'В планирование', to: 'planning', severity: 'info' },
      { label: 'Отменить', to: 'cancelled', severity: 'danger' },
    ],
    planning: [
      { label: 'Запустить', to: 'in_progress', severity: 'success' },
      { label: 'Отменить', to: 'cancelled', severity: 'danger' },
    ],
    in_progress: [
      { label: 'На паузу', to: 'on_hold', severity: 'warn' },
      { label: 'Завершить', to: 'completed', severity: 'success' },
    ],
    on_hold: [
      { label: 'Продолжить', to: 'in_progress', severity: 'success' },
      { label: 'Отменить', to: 'cancelled', severity: 'danger' },
    ],
    completed: [],
    cancelled: [],
  }
  return map[current] ?? []
})

async function loadProject() {
  try {
    await store.fetchProject(projectId.value)
  } catch (err: any) {
    toast.add({
      severity: 'error',
      summary: 'Ошибка',
      detail: err.message,
      life: 4000,
    })
    router.push('/projects')
  }
}

async function onTransition(newStatus: ProjectStatus) {
  try {
    await store.transitionStatus(projectId.value, newStatus)
    toast.add({ severity: 'success', summary: 'Статус изменён', life: 2000 })
  } catch (err: any) {
    toast.add({ severity: 'error', summary: 'Ошибка', detail: err.message, life: 4000 })
  }
}

async function onStartPhase(phaseId: string) {
  try {
    await store.startPhase(projectId.value, phaseId)
    toast.add({ severity: 'success', summary: 'Фаза запущена', life: 2000 })
  } catch (err: any) {
    toast.add({ severity: 'error', summary: 'Ошибка', detail: err.message, life: 4000 })
  }
}

async function onCompletePhase(phaseId: string) {
  try {
    await store.completePhase(projectId.value, phaseId)
    toast.add({ severity: 'success', summary: 'Фаза завершена', life: 2000 })
  } catch (err: any) {
    toast.add({ severity: 'error', summary: 'Ошибка', detail: err.message, life: 4000 })
  }
}

async function onCompleteTask(taskId: string) {
  try {
    await store.completeTask(projectId.value, taskId)
    toast.add({ severity: 'success', summary: 'Задача выполнена', life: 2000 })
  } catch (err: any) {
    toast.add({ severity: 'error', summary: 'Ошибка', detail: err.message, life: 4000 })
  }
}

async function onCancelTask(taskId: string) {
  try {
    await store.updateTaskStatus(projectId.value, taskId, 'cancelled')
    toast.add({ severity: 'success', summary: 'Задача отменена', life: 2000 })
  } catch (err: any) {
    toast.add({ severity: 'error', summary: 'Ошибка', detail: err.message, life: 4000 })
  }
}

async function loadTab(tabName: string) {
  activeTab.value = tabName
  if (tabName === 'documents') documents.value = await store.fetchDocuments(projectId.value)
  else if (tabName === 'team') team.value = await store.fetchTeam(projectId.value)
  else if (tabName === 'events') events.value = await store.fetchEvents(projectId.value)
  else if (tabName === 'tickets') tickets.value = await store.fetchLinkedTickets(projectId.value)
  else if (tabName === 'comments') comments.value = await store.fetchComments(projectId.value)
}

async function postComment() {
  if (!newCommentText.value.trim()) return
  postingComment.value = true
  try {
    await store.addComment(projectId.value, newCommentText.value, newCommentInternal.value)
    newCommentText.value = ''
    newCommentInternal.value = false
    comments.value = await store.fetchComments(projectId.value)
    toast.add({ severity: 'success', summary: 'Комментарий добавлен', life: 2000 })
  } catch (err: any) {
    toast.add({ severity: 'error', summary: 'Ошибка', detail: err.message, life: 4000 })
  } finally {
    postingComment.value = false
  }
}

// --- Add task from PhaseCard ---
async function onAddTask(phaseId: string, title: string, priority: TaskPriority, isMilestone: boolean) {
  try {
    await store.createTask(projectId.value, phaseId, { title, priority, is_milestone: isMilestone })
    toast.add({ severity: 'success', summary: 'Задача добавлена', life: 2000 })
  } catch (err: any) {
    toast.add({ severity: 'error', summary: 'Ошибка', detail: err.message, life: 4000 })
  }
}

// --- Update phase dates from PhaseCard ---
async function onUpdateDates(phaseId: string, startDate: string | null, endDate: string | null) {
  try {
    await store.updatePhase(projectId.value, phaseId, {
      planned_start_date: startDate,
      planned_end_date: endDate,
    })
    toast.add({ severity: 'success', summary: 'Даты обновлены', life: 2000 })
  } catch (err: any) {
    toast.add({ severity: 'error', summary: 'Ошибка', detail: err.message, life: 4000 })
  }
}

// --- Upload document ---
const uploadingDoc = ref(false)
const docTypeOptions = [
  { label: 'Договор', value: 'contract' },
  { label: 'ТЗ / Спецификация', value: 'specification' },
  { label: 'Акт', value: 'act' },
  { label: 'Схема', value: 'diagram' },
  { label: 'Фото', value: 'photo' },
  { label: 'Отчёт', value: 'report' },
  { label: 'Другое', value: 'other' },
]
const selectedDocType = ref('other')

async function onUploadDoc(event: { files: File | File[] }) {
  const file = Array.isArray(event.files) ? event.files[0] : event.files
  if (!file) return
  uploadingDoc.value = true
  try {
    await store.uploadDocument(projectId.value, file, selectedDocType.value)
    documents.value = await store.fetchDocuments(projectId.value)
    toast.add({ severity: 'success', summary: 'Документ загружен', life: 2000 })
  } catch (err: any) {
    toast.add({ severity: 'error', summary: 'Ошибка загрузки', detail: err.message, life: 4000 })
  } finally {
    uploadingDoc.value = false
  }
}

async function onDeleteDoc(docId: string) {
  try {
    await store.deleteDocument(projectId.value, docId)
    documents.value = documents.value.filter(d => d.id !== docId)
    toast.add({ severity: 'success', summary: 'Документ удалён', life: 2000 })
  } catch (err: any) {
    toast.add({ severity: 'error', summary: 'Ошибка', detail: err.message, life: 4000 })
  }
}

// --- Edit project dialog ---
const showEditDialog = ref(false)
const editForm = ref({ name: '', customer_company: '', object_name: '', object_address: '', notes: '', planned_start_date: null as Date | null, planned_end_date: null as Date | null })
const savingEdit = ref(false)

function openEditDialog() {
  if (!project.value) return
  editForm.value = {
    name: project.value.name,
    customer_company: project.value.customer_company,
    object_name: project.value.object_name,
    object_address: project.value.object_address || '',
    notes: project.value.notes || '',
    planned_start_date: project.value.planned_start_date ? new Date(project.value.planned_start_date) : null,
    planned_end_date: project.value.planned_end_date ? new Date(project.value.planned_end_date) : null,
  }
  showEditDialog.value = true
}

async function saveEdit() {
  savingEdit.value = true
  try {
    await store.updateProject(projectId.value, {
      name: editForm.value.name,
      customer_company: editForm.value.customer_company,
      object_name: editForm.value.object_name,
      object_address: editForm.value.object_address || undefined,
      notes: editForm.value.notes || undefined,
      planned_start_date: editForm.value.planned_start_date?.toISOString().slice(0, 10),
      planned_end_date: editForm.value.planned_end_date?.toISOString().slice(0, 10),
    })
    showEditDialog.value = false
    toast.add({ severity: 'success', summary: 'Проект обновлён', life: 2000 })
  } catch (err: any) {
    toast.add({ severity: 'error', summary: 'Ошибка', detail: err.message, life: 4000 })
  } finally {
    savingEdit.value = false
  }
}

function formatDate(d: string | null): string {
  if (!d) return '—'
  return new Date(d).toLocaleDateString('ru-RU', {
    day: 'numeric', month: 'long', year: 'numeric',
  })
}

function formatDateTime(d: string): string {
  return new Date(d).toLocaleString('ru-RU', {
    day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit',
  })
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} Б`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} КБ`
  return `${(bytes / (1024 * 1024)).toFixed(1)} МБ`
}

function downloadDocument(docId: string) {
  window.open(`/projects/${projectId.value}/documents/${docId}/download`, '_blank')
}

onMounted(loadProject)
</script>

<template>
  <div class="project-detail-page">
    <Button icon="pi pi-arrow-left" label="К списку" text @click="router.push('/projects')" />

    <div v-if="store.loading && !project" class="loading">
      <i class="pi pi-spin pi-spinner" /> Загрузка проекта...
    </div>

    <template v-else-if="project">
      <!-- Заголовок + метрики -->
      <div class="project-header">
        <div class="project-title">
          <span class="project-code">{{ project.code }}</span>
          <h1>{{ project.name }}</h1>
          <div class="project-badges">
            <ProjectStatusBadge :status="project.status" />
            <ProjectTypeBadge :type="project.project_type" />
          </div>
        </div>
        <div class="project-actions" v-if="canEdit">
          <Button label="Редактировать" icon="pi pi-pencil" severity="secondary" size="small" @click="openEditDialog" />
          <Button
            v-for="t in transitionOptions"
            :key="t.to"
            :label="t.label"
            :severity="t.severity as any"
            size="small"
            @click="onTransition(t.to)"
          />
        </div>
      </div>

      <!-- Обзорные карточки -->
      <div class="overview-grid">
        <Card class="info-card">
          <template #title>Клиент</template>
          <template #content>
            <div class="info-row"><i class="pi pi-briefcase" /> {{ project.customer_company }}</div>
            <div class="info-row"><i class="pi pi-map-marker" /> {{ project.object_name }}</div>
            <div v-if="project.object_address" class="info-row">
              <i class="pi pi-home" /> {{ project.object_address }}
            </div>
          </template>
        </Card>

        <Card class="info-card">
          <template #title>Сроки</template>
          <template #content>
            <div class="info-row"><i class="pi pi-calendar" /> Старт: {{ formatDate(project.planned_start_date) }}</div>
            <div class="info-row"><i class="pi pi-flag" /> Финиш: {{ formatDate(project.planned_end_date) }}</div>
            <div v-if="project.actual_start_date" class="info-row">
              <i class="pi pi-play" /> Фактический старт: {{ formatDate(project.actual_start_date) }}
            </div>
          </template>
        </Card>

        <Card class="info-card">
          <template #title>Прогресс</template>
          <template #content>
            <div class="progress-big">{{ project.progress_pct }}%</div>
            <ProgressBar :value="project.progress_pct" :show-value="false" />
            <div class="info-row" style="margin-top: 8px">
              <i class="pi pi-list" /> Открытых задач: {{ project.open_tasks_count }}
            </div>
            <div class="info-row">
              <i class="pi pi-file" /> Документов: {{ project.document_count }}
            </div>
          </template>
        </Card>
      </div>

      <!-- Табы -->
      <Tabs :value="activeTab" @update:value="(val) => loadTab(String(val))">
        <TabList>
          <Tab value="0">Этапы</Tab>
          <Tab value="gantt">Gantt</Tab>
          <Tab value="timeline">Timeline</Tab>
          <Tab value="documents">Документы</Tab>
          <Tab value="team">Команда</Tab>
          <Tab value="risks" v-if="isStaff">Риски</Tab>
          <Tab value="tickets">Тикеты</Tab>
          <Tab value="comments">Комментарии</Tab>
          <Tab value="events">История</Tab>
        </TabList>
        <TabPanels>
          <!-- Этапы + задачи -->
          <TabPanel value="0">
            <div class="phases-list">
              <div v-for="phase in project.phases" :key="phase.id" class="phase-with-approval">
                <PhaseCard
                  :phase="phase"
                  :can-edit="canEdit"
                  @start="onStartPhase"
                  @complete="onCompletePhase"
                  @task-complete="onCompleteTask"
                  @task-cancel="onCancelTask"
                  @add-task="onAddTask"
                  @update-dates="onUpdateDates"
                />
                <PhaseApproval
                  :project-id="projectId"
                  :phase-id="phase.id"
                  :phase-status="phase.status"
                  :is-property-manager="isPropertyManager"
                  :is-staff="isStaff"
                />
              </div>
            </div>
          </TabPanel>

          <!-- Gantt -->
          <TabPanel value="gantt">
            <GanttChart
              :phases="project.phases"
              :planned-start="project.planned_start_date"
              :planned-end="project.planned_end_date"
            />
          </TabPanel>

          <!-- Timeline -->
          <TabPanel value="timeline">
            <ProjectTimeline :phases="project.phases" />
          </TabPanel>

          <!-- Risks -->
          <TabPanel v-if="isStaff" value="risks">
            <RiskPanel :project-id="projectId" />
          </TabPanel>

          <!-- Documents -->
          <TabPanel value="documents">
            <!-- Upload form -->
            <div class="upload-section">
              <Select v-model="selectedDocType" :options="docTypeOptions" option-label="label" option-value="value" placeholder="Тип документа" class="doc-type-select" />
              <FileUpload
                mode="basic"
                :auto="true"
                choose-label="Загрузить файл"
                :custom-upload="true"
                @uploader="onUploadDoc"
                accept=".pdf,.docx,.xlsx,.jpg,.jpeg,.png,.txt"
                :max-file-size="20000000"
              />
            </div>
            <Divider v-if="documents.length" />
            <div v-if="documents.length === 0" class="empty-panel">Документов пока нет</div>
            <div v-else class="docs-list">
              <div v-for="doc in documents" :key="doc.id" class="doc-item">
                <i class="pi pi-file" />
                <div class="doc-info">
                  <strong>{{ doc.name }}</strong>
                  <span class="doc-meta">{{ doc.filename }} · {{ formatSize(doc.size) }} · {{ formatDateTime(doc.created_at) }}</span>
                </div>
                <Button icon="pi pi-download" size="small" text @click="downloadDocument(doc.id)" />
                <Button v-if="canEdit" icon="pi pi-trash" size="small" text severity="danger" @click="onDeleteDoc(doc.id)" />
              </div>
            </div>
          </TabPanel>

          <!-- Team -->
          <TabPanel value="team">
            <div v-if="team.length === 0" class="empty-panel">Участники команды не назначены</div>
            <div v-else class="team-list">
              <div v-for="member in team" :key="member.id" class="team-item">
                <div class="team-avatar">{{ (member.user_name || '?').charAt(0) }}</div>
                <div class="team-info">
                  <strong>{{ member.user_name || member.user_id }}</strong>
                  <span>{{ member.user_email }} · {{ member.team_role }}</span>
                </div>
                <span v-if="member.is_primary" class="primary-badge">Основной</span>
              </div>
            </div>
          </TabPanel>

          <!-- Tickets -->
          <TabPanel value="tickets">
            <div v-if="tickets.length === 0" class="empty-panel">Связанных тикетов нет</div>
            <div v-else class="tickets-list">
              <div
                v-for="ticket in tickets"
                :key="ticket.id"
                class="ticket-item"
                :class="{ blocker: ticket.is_implementation_blocker }"
                @click="router.push(`/tickets/${ticket.id}`)"
              >
                <span v-if="ticket.is_implementation_blocker" class="blocker-badge">Блокер</span>
                <strong>{{ ticket.title }}</strong>
                <span class="ticket-meta">{{ ticket.status }} · {{ ticket.priority }} · {{ formatDateTime(ticket.created_at) }}</span>
              </div>
            </div>
          </TabPanel>

          <!-- Comments -->
          <TabPanel value="comments">
            <div class="comments-form">
              <Textarea
                v-model="newCommentText"
                placeholder="Добавить комментарий..."
                rows="3"
                autoResize
                class="comment-input"
              />
              <div class="comment-actions">
                <label v-if="isStaff" class="internal-checkbox">
                  <Checkbox v-model="newCommentInternal" :binary="true" />
                  Внутренний (только PASS24)
                </label>
                <Button
                  label="Отправить"
                  icon="pi pi-send"
                  :loading="postingComment"
                  :disabled="!newCommentText.trim()"
                  @click="postComment"
                />
              </div>
            </div>
            <Divider />
            <div v-if="comments.length === 0" class="empty-panel">Комментариев пока нет</div>
            <div v-else class="comments-list">
              <div
                v-for="c in comments"
                :key="c.id"
                class="comment-item"
                :class="{ internal: c.is_internal }"
              >
                <div class="comment-header">
                  <strong>{{ c.author_name }}</strong>
                  <span v-if="c.is_internal" class="internal-badge">Внутренний</span>
                  <span class="comment-date">{{ formatDateTime(c.created_at) }}</span>
                </div>
                <p class="comment-text">{{ c.text }}</p>
              </div>
            </div>
          </TabPanel>

          <!-- Events -->
          <TabPanel value="events">
            <div v-if="events.length === 0" class="empty-panel">Событий пока нет</div>
            <div v-else class="events-list">
              <div v-for="event in events" :key="event.id" class="event-item">
                <span class="event-type">{{ event.event_type }}</span>
                <span class="event-desc">{{ event.description }}</span>
                <span class="event-date">{{ formatDateTime(event.created_at) }}</span>
              </div>
            </div>
          </TabPanel>
        </TabPanels>
      </Tabs>
    </template>

    <!-- Edit project dialog -->
    <Dialog v-model:visible="showEditDialog" header="Редактирование проекта" :modal="true" :style="{ width: '600px' }">
      <div class="edit-form">
        <div class="field">
          <label>Название</label>
          <InputText v-model="editForm.name" />
        </div>
        <div class="field-row">
          <div class="field">
            <label>Компания</label>
            <InputText v-model="editForm.customer_company" />
          </div>
          <div class="field">
            <label>Объект</label>
            <InputText v-model="editForm.object_name" />
          </div>
        </div>
        <div class="field">
          <label>Адрес</label>
          <InputText v-model="editForm.object_address" />
        </div>
        <div class="field-row">
          <div class="field">
            <label>Плановый старт</label>
            <DatePicker v-model="editForm.planned_start_date" date-format="dd.mm.yy" show-icon />
          </div>
          <div class="field">
            <label>Плановый финиш</label>
            <DatePicker v-model="editForm.planned_end_date" date-format="dd.mm.yy" show-icon />
          </div>
        </div>
        <div class="field">
          <label>Примечания</label>
          <Textarea v-model="editForm.notes" rows="3" auto-resize />
        </div>
      </div>
      <template #footer>
        <Button label="Отмена" severity="secondary" text @click="showEditDialog = false" />
        <Button label="Сохранить" icon="pi pi-check" :loading="savingEdit" @click="saveEdit" />
      </template>
    </Dialog>
  </div>
</template>

<style scoped>
.project-detail-page {
  max-width: 1400px;
  margin: 0 auto;
  padding: 24px;
}
.loading {
  padding: 48px;
  text-align: center;
  color: #64748b;
}
.project-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin: 16px 0 24px;
  gap: 16px;
}
.project-code {
  font-family: monospace;
  font-size: 0.85rem;
  color: #64748b;
  font-weight: 600;
}
.project-title h1 {
  margin: 4px 0 8px;
  font-size: 1.75rem;
}
.project-badges {
  display: flex;
  gap: 12px;
  align-items: center;
}
.project-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
.overview-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  gap: 16px;
  margin-bottom: 24px;
}
.info-card {
  height: 100%;
}
.info-row {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 0.875rem;
  color: #64748b;
  padding: 4px 0;
}
.info-row i {
  color: #94a3b8;
  width: 16px;
}
.progress-big {
  font-size: 2rem;
  font-weight: 600;
  color: #3b82f6;
  margin-bottom: 8px;
}
.phases-list {
  margin-top: 16px;
}
.empty-panel {
  padding: 32px;
  text-align: center;
  color: #94a3b8;
}
.docs-list, .team-list, .tickets-list, .comments-list, .events-list {
  margin-top: 16px;
}
.doc-item, .team-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 12px;
  border-bottom: 1px solid #f1f5f9;
}
.doc-item i {
  color: #94a3b8;
}
.doc-info, .team-info {
  flex: 1;
  display: flex;
  flex-direction: column;
}
.doc-meta, .team-info span {
  font-size: 0.8rem;
  color: #64748b;
}
.team-avatar {
  width: 36px;
  height: 36px;
  background: #3b82f6;
  color: white;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 600;
}
.primary-badge {
  font-size: 0.7rem;
  padding: 2px 8px;
  background: #dbeafe;
  color: #1e40af;
  border-radius: 4px;
  font-weight: 600;
}
.ticket-item {
  padding: 10px 12px;
  border-bottom: 1px solid #f1f5f9;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 12px;
}
.ticket-item:hover { background: #f8fafc; }
.ticket-item.blocker { border-left: 3px solid #ef4444; background: #fef2f2; }
.blocker-badge {
  font-size: 0.7rem;
  padding: 2px 8px;
  background: #ef4444;
  color: white;
  border-radius: 4px;
  font-weight: 600;
}
.ticket-meta { font-size: 0.75rem; color: #64748b; margin-left: auto; }
.comments-form { padding: 16px 0; }
.comment-input { width: 100%; }
.comment-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 8px;
}
.internal-checkbox {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 0.875rem;
  color: #64748b;
}
.comment-item {
  padding: 12px;
  border-bottom: 1px solid #f1f5f9;
}
.comment-item.internal { background: #fef9c3; border-left: 3px solid #eab308; padding-left: 9px; }
.comment-header {
  display: flex;
  gap: 12px;
  align-items: center;
  margin-bottom: 6px;
}
.internal-badge {
  font-size: 0.7rem;
  padding: 2px 6px;
  background: #eab308;
  color: white;
  border-radius: 3px;
}
.comment-date { font-size: 0.75rem; color: #94a3b8; margin-left: auto; }
.comment-text { margin: 0; color: #1e293b; white-space: pre-wrap; }
.event-item {
  display: grid;
  grid-template-columns: 180px 1fr auto;
  gap: 12px;
  padding: 8px 12px;
  border-bottom: 1px solid #f1f5f9;
  font-size: 0.875rem;
}
.event-type {
  font-family: monospace;
  font-size: 0.75rem;
  color: #3b82f6;
  font-weight: 600;
}
.event-date { color: #94a3b8; font-size: 0.8rem; }
.upload-section { display: flex; align-items: center; gap: 12px; padding: 12px 0; }
.doc-type-select { min-width: 180px; }
.edit-form { display: flex; flex-direction: column; gap: 16px; }
.edit-form .field { display: flex; flex-direction: column; gap: 6px; flex: 1; }
.edit-form .field label { font-size: 0.85rem; color: #475569; font-weight: 500; }
.edit-form .field-row { display: flex; gap: 12px; }
</style>

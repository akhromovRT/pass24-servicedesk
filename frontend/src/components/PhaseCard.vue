<script setup lang="ts">
import { ref } from 'vue'
import Button from 'primevue/button'
import InputText from 'primevue/inputtext'
import Checkbox from 'primevue/checkbox'
import DatePicker from 'primevue/datepicker'
import ProgressBar from 'primevue/progressbar'
import TaskRow from './TaskRow.vue'
import type { ProjectPhase, PhaseStatus, TaskPriority } from '../types'

const props = defineProps<{
  phase: ProjectPhase
  canEdit: boolean
}>()

const emit = defineEmits<{
  start: [phaseId: string]
  complete: [phaseId: string]
  taskComplete: [taskId: string]
  taskCancel: [taskId: string]
  addTask: [phaseId: string, title: string, priority: TaskPriority, isMilestone: boolean]
  updateDates: [phaseId: string, startDate: string | null, endDate: string | null]
}>()

const expanded = ref(false)

// Add task form
const showAddTask = ref(false)
const newTaskTitle = ref('')
const newTaskMilestone = ref(false)
const addingTask = ref(false)

// Date editing
const editingDates = ref(false)
const editStartDate = ref<Date | null>(null)
const editEndDate = ref<Date | null>(null)

function startEditDates() {
  editStartDate.value = props.phase.planned_start_date ? new Date(props.phase.planned_start_date) : null
  editEndDate.value = props.phase.planned_end_date ? new Date(props.phase.planned_end_date) : null
  editingDates.value = true
}

function saveDates() {
  emit(
    'updateDates',
    props.phase.id,
    editStartDate.value ? editStartDate.value.toISOString().slice(0, 10) : null,
    editEndDate.value ? editEndDate.value.toISOString().slice(0, 10) : null,
  )
  editingDates.value = false
}

function submitTask() {
  if (!newTaskTitle.value.trim()) return
  addingTask.value = true
  emit('addTask', props.phase.id, newTaskTitle.value.trim(), 'normal', newTaskMilestone.value)
  newTaskTitle.value = ''
  newTaskMilestone.value = false
  showAddTask.value = false
  addingTask.value = false
}

const statusLabels: Record<PhaseStatus, string> = {
  pending: 'Ожидает старта',
  in_progress: 'В работе',
  completed: 'Завершена',
  blocked: 'Заблокирована',
  skipped: 'Пропущена',
}

const statusColors: Record<PhaseStatus, string> = {
  pending: '#94a3b8',
  in_progress: '#3b82f6',
  completed: '#10b981',
  blocked: '#ef4444',
  skipped: '#cbd5e1',
}

function formatDate(d: string | null): string {
  if (!d) return '—'
  return new Date(d).toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' })
}
</script>

<template>
  <div class="phase-card" :class="{ expanded }">
    <div class="phase-header" @click="expanded = !expanded">
      <div class="phase-info">
        <div class="phase-title-row">
          <span class="phase-order">{{ phase.order_num }}</span>
          <strong>{{ phase.name }}</strong>
          <span class="phase-status" :style="{ color: statusColors[phase.status] }">
            {{ statusLabels[phase.status] }}
          </span>
        </div>
        <div class="phase-meta">
          <!-- Dates: inline edit or display -->
          <span v-if="!editingDates" @click.stop="canEdit && startEditDates()" :class="{ editable: canEdit }">
            <i class="pi pi-calendar" />
            {{ formatDate(phase.planned_start_date) }} — {{ formatDate(phase.planned_end_date) }}
          </span>
          <span v-else class="date-edit-inline" @click.stop>
            <DatePicker v-model="editStartDate" date-format="dd.mm.yy" show-icon :input-style="{ width: '110px', fontSize: '0.8rem' }" />
            <span>—</span>
            <DatePicker v-model="editEndDate" date-format="dd.mm.yy" show-icon :input-style="{ width: '110px', fontSize: '0.8rem' }" />
            <Button icon="pi pi-check" size="small" text rounded severity="success" @click.stop="saveDates" />
            <Button icon="pi pi-times" size="small" text rounded severity="secondary" @click.stop="editingDates = false" />
          </span>
          <span>
            <i class="pi pi-list" />
            {{ phase.tasks.filter(t => t.status === 'done').length }}/{{ phase.tasks.filter(t => t.status !== 'cancelled').length }} задач
          </span>
        </div>
        <div class="phase-progress">
          <ProgressBar :value="phase.progress_pct" :show-value="false" />
        </div>
      </div>
      <div class="phase-controls">
        <Button
          v-if="canEdit && phase.status === 'pending'"
          label="Старт" size="small" severity="info" icon="pi pi-play"
          @click.stop="$emit('start', phase.id)"
        />
        <Button
          v-if="canEdit && (phase.status === 'in_progress' || phase.status === 'blocked')"
          label="Завершить" size="small" severity="success" icon="pi pi-check"
          @click.stop="$emit('complete', phase.id)"
        />
        <i :class="expanded ? 'pi pi-chevron-up' : 'pi pi-chevron-down'" class="expand-icon" />
      </div>
    </div>
    <div v-if="expanded" class="phase-body">
      <p v-if="phase.description" class="phase-description">{{ phase.description }}</p>
      <div v-if="phase.tasks.length === 0 && !showAddTask" class="no-tasks">Задач пока нет</div>
      <div v-else class="task-list">
        <TaskRow
          v-for="task in phase.tasks" :key="task.id"
          :task="task" :can-edit="canEdit"
          @complete="$emit('taskComplete', $event)"
          @cancel="$emit('taskCancel', $event)"
        />
      </div>
      <!-- Add task inline form -->
      <div v-if="canEdit" class="add-task-section">
        <div v-if="showAddTask" class="add-task-form">
          <InputText
            v-model="newTaskTitle"
            placeholder="Название задачи..."
            class="task-title-input"
            @keyup.enter="submitTask"
          />
          <label class="milestone-check">
            <Checkbox v-model="newTaskMilestone" :binary="true" />
            <span>Milestone</span>
          </label>
          <Button icon="pi pi-check" size="small" severity="success" :disabled="!newTaskTitle.trim()" @click="submitTask" />
          <Button icon="pi pi-times" size="small" severity="secondary" text @click="showAddTask = false; newTaskTitle = ''" />
        </div>
        <Button
          v-else
          label="Добавить задачу" icon="pi pi-plus" size="small" text severity="secondary"
          @click="showAddTask = true"
        />
      </div>
    </div>
  </div>
</template>

<style scoped>
.phase-card { background: white; border: 1px solid #e2e8f0; border-radius: 8px; margin-bottom: 12px; overflow: hidden; transition: box-shadow 0.15s ease; }
.phase-card.expanded { box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05); }
.phase-header { display: flex; align-items: center; justify-content: space-between; padding: 16px; cursor: pointer; gap: 16px; transition: background 0.15s ease; }
.phase-header:hover { background: #f8fafc; }
.phase-info { flex: 1; min-width: 0; }
.phase-title-row { display: flex; align-items: center; gap: 12px; margin-bottom: 6px; }
.phase-order { display: inline-flex; align-items: center; justify-content: center; min-width: 28px; height: 28px; background: #f1f5f9; color: #475569; border-radius: 14px; font-size: 0.8rem; font-weight: 600; }
.phase-title-row strong { font-size: 1rem; color: #1e293b; flex: 1; }
.phase-status { font-size: 0.75rem; font-weight: 600; text-transform: uppercase; }
.phase-meta { display: flex; gap: 16px; font-size: 0.8rem; color: #64748b; margin-bottom: 8px; align-items: center; }
.phase-meta i { margin-right: 4px; color: #94a3b8; }
.phase-meta .editable { cursor: pointer; border-bottom: 1px dashed #94a3b8; }
.phase-meta .editable:hover { color: #3b82f6; border-color: #3b82f6; }
.date-edit-inline { display: flex; align-items: center; gap: 6px; }
.phase-progress { max-width: 400px; }
.phase-controls { display: flex; align-items: center; gap: 8px; flex-shrink: 0; }
.expand-icon { color: #94a3b8; font-size: 0.85rem; }
.phase-body { border-top: 1px solid #e2e8f0; padding: 12px 16px; }
.phase-description { color: #64748b; font-size: 0.875rem; margin: 0 0 12px; }
.no-tasks { padding: 20px; text-align: center; color: #94a3b8; font-size: 0.875rem; }
.task-list { margin: 0 -16px; }
.add-task-section { padding: 12px 0 0; }
.add-task-form { display: flex; align-items: center; gap: 8px; }
.task-title-input { flex: 1; }
.milestone-check { display: flex; align-items: center; gap: 4px; font-size: 0.8rem; color: #64748b; white-space: nowrap; }
</style>

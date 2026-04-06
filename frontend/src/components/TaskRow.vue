<script setup lang="ts">
import Button from 'primevue/button'
import type { ProjectTask, TaskStatus } from '../types'

defineProps<{
  task: ProjectTask
  canEdit: boolean
}>()

defineEmits<{
  complete: [taskId: string]
  cancel: [taskId: string]
}>()

const statusLabels: Record<TaskStatus, string> = {
  todo: 'К выполнению',
  in_progress: 'В работе',
  done: 'Выполнено',
  cancelled: 'Отменено',
}

const statusColors: Record<TaskStatus, string> = {
  todo: '#94a3b8',
  in_progress: '#3b82f6',
  done: '#10b981',
  cancelled: '#cbd5e1',
}

function formatDate(d: string | null): string {
  if (!d) return ''
  return new Date(d).toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' })
}
</script>

<template>
  <div class="task-row" :class="{ done: task.status === 'done', cancelled: task.status === 'cancelled' }">
    <div class="task-status-indicator" :style="{ backgroundColor: statusColors[task.status] }" />
    <div class="task-content">
      <div class="task-title-row">
        <span class="task-title">
          <i v-if="task.is_milestone" class="pi pi-flag" title="Milestone" />
          {{ task.title }}
        </span>
        <span class="task-status" :style="{ color: statusColors[task.status] }">
          {{ statusLabels[task.status] }}
        </span>
      </div>
      <div class="task-meta" v-if="task.due_date || task.estimated_hours">
        <span v-if="task.due_date"><i class="pi pi-calendar" /> {{ formatDate(task.due_date) }}</span>
        <span v-if="task.estimated_hours"><i class="pi pi-clock" /> {{ task.estimated_hours }}ч</span>
      </div>
    </div>
    <div v-if="canEdit && task.status !== 'done' && task.status !== 'cancelled'" class="task-actions">
      <Button
        icon="pi pi-check"
        size="small"
        severity="success"
        text
        rounded
        title="Отметить выполненной"
        @click="$emit('complete', task.id)"
      />
      <Button
        icon="pi pi-times"
        size="small"
        severity="secondary"
        text
        rounded
        title="Отменить задачу"
        @click="$emit('cancel', task.id)"
      />
    </div>
  </div>
</template>

<style scoped>
.task-row {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 10px 12px;
  border-bottom: 1px solid #f1f5f9;
  transition: background 0.15s ease;
}
.task-row:hover {
  background: #f8fafc;
}
.task-row.done .task-title,
.task-row.cancelled .task-title {
  text-decoration: line-through;
  color: #94a3b8;
}
.task-status-indicator {
  width: 3px;
  align-self: stretch;
  border-radius: 2px;
  flex-shrink: 0;
}
.task-content {
  flex: 1;
  min-width: 0;
}
.task-title-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}
.task-title {
  font-size: 0.9rem;
  color: #1e293b;
}
.task-title .pi-flag {
  color: #f59e0b;
  margin-right: 4px;
}
.task-status {
  font-size: 0.75rem;
  font-weight: 600;
  flex-shrink: 0;
}
.task-meta {
  font-size: 0.8rem;
  color: #64748b;
  margin-top: 4px;
  display: flex;
  gap: 12px;
}
.task-meta i {
  margin-right: 4px;
}
.task-actions {
  display: flex;
  gap: 4px;
  flex-shrink: 0;
}
</style>

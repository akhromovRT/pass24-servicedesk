<script setup lang="ts">
import { ref } from 'vue'
import Button from 'primevue/button'
import ProgressBar from 'primevue/progressbar'
import TaskRow from './TaskRow.vue'
import type { ProjectPhase, PhaseStatus } from '../types'

defineProps<{
  phase: ProjectPhase
  canEdit: boolean
}>()

defineEmits<{
  start: [phaseId: string]
  complete: [phaseId: string]
  taskComplete: [taskId: string]
  taskCancel: [taskId: string]
}>()

const expanded = ref(false)

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
          <span>
            <i class="pi pi-calendar" />
            {{ formatDate(phase.planned_start_date) }} — {{ formatDate(phase.planned_end_date) }}
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
          label="Старт"
          size="small"
          severity="info"
          icon="pi pi-play"
          @click.stop="$emit('start', phase.id)"
        />
        <Button
          v-if="canEdit && (phase.status === 'in_progress' || phase.status === 'blocked')"
          label="Завершить"
          size="small"
          severity="success"
          icon="pi pi-check"
          @click.stop="$emit('complete', phase.id)"
        />
        <i :class="expanded ? 'pi pi-chevron-up' : 'pi pi-chevron-down'" class="expand-icon" />
      </div>
    </div>
    <div v-if="expanded" class="phase-body">
      <p v-if="phase.description" class="phase-description">{{ phase.description }}</p>
      <div v-if="phase.tasks.length === 0" class="no-tasks">Задач пока нет</div>
      <div v-else class="task-list">
        <TaskRow
          v-for="task in phase.tasks"
          :key="task.id"
          :task="task"
          :can-edit="canEdit"
          @complete="$emit('taskComplete', $event)"
          @cancel="$emit('taskCancel', $event)"
        />
      </div>
    </div>
  </div>
</template>

<style scoped>
.phase-card {
  background: white;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  margin-bottom: 12px;
  overflow: hidden;
  transition: box-shadow 0.15s ease;
}
.phase-card.expanded {
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
}
.phase-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px;
  cursor: pointer;
  gap: 16px;
  transition: background 0.15s ease;
}
.phase-header:hover {
  background: #f8fafc;
}
.phase-info {
  flex: 1;
  min-width: 0;
}
.phase-title-row {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 6px;
}
.phase-order {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 28px;
  height: 28px;
  background: #f1f5f9;
  color: #475569;
  border-radius: 14px;
  font-size: 0.8rem;
  font-weight: 600;
}
.phase-title-row strong {
  font-size: 1rem;
  color: #1e293b;
  flex: 1;
}
.phase-status {
  font-size: 0.75rem;
  font-weight: 600;
  text-transform: uppercase;
}
.phase-meta {
  display: flex;
  gap: 16px;
  font-size: 0.8rem;
  color: #64748b;
  margin-bottom: 8px;
}
.phase-meta i {
  margin-right: 4px;
  color: #94a3b8;
}
.phase-progress {
  max-width: 400px;
}
.phase-controls {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}
.expand-icon {
  color: #94a3b8;
  font-size: 0.85rem;
}
.phase-body {
  border-top: 1px solid #e2e8f0;
  padding: 12px 16px;
}
.phase-description {
  color: #64748b;
  font-size: 0.875rem;
  margin: 0 0 12px;
}
.no-tasks {
  padding: 20px;
  text-align: center;
  color: #94a3b8;
  font-size: 0.875rem;
}
.task-list {
  margin: 0 -16px;
}
</style>

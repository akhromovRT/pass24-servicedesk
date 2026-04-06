<script setup lang="ts">
import Timeline from 'primevue/timeline'
import type { ProjectPhase, PhaseStatus } from '../types'

defineProps<{ phases: ProjectPhase[] }>()

const statusIcons: Record<PhaseStatus, string> = {
  pending: 'pi pi-clock',
  in_progress: 'pi pi-spinner pi-spin',
  completed: 'pi pi-check',
  blocked: 'pi pi-exclamation-triangle',
  skipped: 'pi pi-times',
}

const statusColors: Record<PhaseStatus, string> = {
  pending: '#94a3b8',
  in_progress: '#3b82f6',
  completed: '#10b981',
  blocked: '#ef4444',
  skipped: '#cbd5e1',
}

const statusLabels: Record<PhaseStatus, string> = {
  pending: 'Ожидает',
  in_progress: 'В работе',
  completed: 'Завершена',
  blocked: 'Заблокирована',
  skipped: 'Пропущена',
}

function formatDate(d: string | null): string {
  if (!d) return '—'
  return new Date(d).toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' })
}
</script>

<template>
  <Timeline :value="phases" align="left" layout="vertical" class="phase-timeline">
    <template #marker="slotProps">
      <span
        class="phase-marker"
        :style="{ backgroundColor: statusColors[slotProps.item.status as PhaseStatus] }"
      >
        <i :class="statusIcons[slotProps.item.status as PhaseStatus]" />
      </span>
    </template>
    <template #content="slotProps">
      <div class="phase-timeline-content">
        <div class="phase-header">
          <strong>{{ slotProps.item.order_num }}. {{ slotProps.item.name }}</strong>
          <span class="phase-status-label" :style="{ color: statusColors[slotProps.item.status as PhaseStatus] }">
            {{ statusLabels[slotProps.item.status as PhaseStatus] }}
          </span>
        </div>
        <div class="phase-dates">
          {{ formatDate(slotProps.item.planned_start_date) }} — {{ formatDate(slotProps.item.planned_end_date) }}
          ({{ slotProps.item.planned_duration_days }} дн)
        </div>
        <div v-if="slotProps.item.progress_pct > 0 || slotProps.item.status === 'in_progress'" class="phase-progress">
          {{ slotProps.item.progress_pct }}%
        </div>
      </div>
    </template>
  </Timeline>
</template>

<style scoped>
.phase-timeline {
  padding: 0;
}
.phase-marker {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border-radius: 50%;
  color: white;
}
.phase-marker i {
  font-size: 0.75rem;
}
.phase-timeline-content {
  padding: 4px 0 20px;
}
.phase-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}
.phase-status-label {
  font-size: 0.75rem;
  font-weight: 600;
  text-transform: uppercase;
}
.phase-dates {
  font-size: 0.8rem;
  color: #64748b;
  margin-top: 2px;
}
.phase-progress {
  font-size: 0.85rem;
  color: #3b82f6;
  font-weight: 600;
  margin-top: 4px;
}
</style>

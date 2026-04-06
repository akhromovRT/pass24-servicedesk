<script setup lang="ts">
import Tag from 'primevue/tag'
import type { ProjectStatus } from '../types'

defineProps<{ status: ProjectStatus }>()

const statusLabels: Record<ProjectStatus, string> = {
  draft: 'Черновик',
  planning: 'Планирование',
  in_progress: 'В работе',
  on_hold: 'На паузе',
  completed: 'Завершён',
  cancelled: 'Отменён',
}

const statusSeverity: Record<ProjectStatus, string> = {
  draft: 'secondary',
  planning: 'info',
  in_progress: 'warn',
  on_hold: 'contrast',
  completed: 'success',
  cancelled: 'danger',
}
</script>

<template>
  <Tag :value="statusLabels[status]" :severity="statusSeverity[status]" />
</template>

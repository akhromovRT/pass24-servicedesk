<script setup lang="ts">
import Tag from 'primevue/tag'
import type { TicketPriority } from '../types'

defineProps<{
  priority: TicketPriority
}>()

const priorityLabels: Record<TicketPriority, string> = {
  critical: 'Критический',
  high: 'Высокий',
  normal: 'Обычный',
  low: 'Низкий',
}

const prioritySeverity: Record<TicketPriority, string> = {
  critical: 'danger',
  high: 'warn',
  normal: 'info',
  low: 'secondary',
}
</script>

<template>
  <Tag
    :value="priorityLabels[priority]"
    :severity="prioritySeverity[priority] as any"
  />
</template>

<script setup lang="ts">
import Tag from 'primevue/tag'
import type { TicketStatus } from '../types'

defineProps<{
  status: TicketStatus
}>()

const statusLabels: Record<TicketStatus, string> = {
  new: 'Новый',
  in_progress: 'В работе',
  waiting_for_user: 'Ожидает ответа',
  resolved: 'Решён',
  closed: 'Закрыт',
}

const statusSeverity: Record<TicketStatus, string> = {
  new: 'info',
  in_progress: 'warn',
  waiting_for_user: 'secondary',
  resolved: 'success',
  closed: 'contrast',
}
</script>

<template>
  <Tag
    :value="statusLabels[status]"
    :severity="statusSeverity[status] as any"
  />
</template>

<script setup lang="ts">
import Tag from 'primevue/tag'
import type { TicketStatus } from '../types'

const props = withDefaults(defineProps<{
  status: TicketStatus
  simplified?: boolean
}>(), {
  simplified: false,
})

const statusLabels: Record<TicketStatus, string> = {
  new: 'Новый',
  in_progress: 'В работе',
  waiting_for_user: 'Ожидает ответа',
  resolved: 'Решён',
  closed: 'Закрыт',
}

const userStatusLabels: Record<TicketStatus, string> = {
  new: 'Принята',
  in_progress: 'В работе',
  waiting_for_user: 'Ждёт вашего ответа',
  resolved: 'Решена',
  closed: 'Закрыта',
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
    :value="(simplified ? userStatusLabels : statusLabels)[status]"
    :severity="statusSeverity[status] as any"
  />
</template>

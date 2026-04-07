<script setup lang="ts">
import Tag from 'primevue/tag'
import type { TicketStatus } from '../types'

withDefaults(defineProps<{
  status: TicketStatus
  simplified?: boolean
}>(), {
  simplified: false,
})

const statusLabels: Record<TicketStatus, string> = {
  new: 'Новый',
  in_progress: 'В работе',
  waiting_for_user: 'Ожидает ответа',
  on_hold: 'Отложена',
  engineer_visit: 'Выезд инженера',
  resolved: 'Решён',
  closed: 'Закрыт',
}

const userStatusLabels: Record<TicketStatus, string> = {
  new: 'Принята',
  in_progress: 'В работе',
  waiting_for_user: 'Ждёт вашего ответа',
  on_hold: 'Отложена',
  engineer_visit: 'Инженер выехал',
  resolved: 'Решена',
  closed: 'Закрыта',
}

const statusSeverity: Record<TicketStatus, string> = {
  new: 'info',
  in_progress: 'warn',
  waiting_for_user: 'secondary',
  on_hold: 'secondary',
  engineer_visit: 'info',
  resolved: 'success',
  closed: 'contrast',
}

const statusColors: Record<TicketStatus, string> = {
  new: '#3b82f6',
  in_progress: '#f59e0b',
  waiting_for_user: '#8b5cf6',
  on_hold: '#6366f1',
  engineer_visit: '#0ea5e9',
  resolved: '#10b981',
  closed: '#64748b',
}
</script>

<template>
  <Tag
    :value="(simplified ? userStatusLabels : statusLabels)[status]"
    :severity="statusSeverity[status] as any"
    :style="(status === 'on_hold' || status === 'engineer_visit') ? { backgroundColor: statusColors[status], color: '#fff' } : undefined"
  />
</template>

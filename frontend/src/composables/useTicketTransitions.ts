import { computed, type Ref } from 'vue'
import type { TicketStatus } from '../types'

interface StatusTransition {
  label: string
  value: TicketStatus
  icon: string
  color: string
}

const TRANSITIONS: Record<TicketStatus, StatusTransition[]> = {
  new: [
    { label: 'Взять в работу', value: 'in_progress', icon: 'pi pi-play', color: '#f59e0b' },
    { label: 'Решить', value: 'resolved', icon: 'pi pi-check', color: '#10b981' },
  ],
  in_progress: [
    { label: 'Ожидать ответа', value: 'waiting_for_user', icon: 'pi pi-clock', color: '#8b5cf6' },
    { label: 'Отложить', value: 'on_hold', icon: 'pi pi-pause', color: '#6366f1' },
    { label: 'Выезд инженера', value: 'engineer_visit', icon: 'pi pi-car', color: '#0ea5e9' },
    { label: 'Решить', value: 'resolved', icon: 'pi pi-check', color: '#10b981' },
  ],
  waiting_for_user: [
    { label: 'Вернуть в работу', value: 'in_progress', icon: 'pi pi-replay', color: '#f59e0b' },
    { label: 'Решить', value: 'resolved', icon: 'pi pi-check', color: '#10b981' },
  ],
  on_hold: [
    { label: 'Вернуть в работу', value: 'in_progress', icon: 'pi pi-replay', color: '#f59e0b' },
    { label: 'Решить', value: 'resolved', icon: 'pi pi-check', color: '#10b981' },
  ],
  engineer_visit: [
    { label: 'Вернуть в работу', value: 'in_progress', icon: 'pi pi-replay', color: '#f59e0b' },
    { label: 'Ожидать ответа', value: 'waiting_for_user', icon: 'pi pi-clock', color: '#8b5cf6' },
    { label: 'Решить', value: 'resolved', icon: 'pi pi-check', color: '#10b981' },
  ],
  resolved: [
    { label: 'Закрыть', value: 'closed', icon: 'pi pi-lock', color: '#64748b' },
    { label: 'Переоткрыть', value: 'in_progress', icon: 'pi pi-refresh', color: '#f59e0b' },
  ],
  closed: [],
}

const STATUS_LABELS: Record<TicketStatus, string> = {
  new: 'Новый',
  in_progress: 'В работе',
  waiting_for_user: 'Ожидает ответа',
  on_hold: 'Отложена',
  engineer_visit: 'Выезд инженера',
  resolved: 'Решён',
  closed: 'Закрыт',
}

const STATUS_COLORS: Record<TicketStatus, string> = {
  new: '#3b82f6',
  in_progress: '#f59e0b',
  waiting_for_user: '#8b5cf6',
  on_hold: '#6366f1',
  engineer_visit: '#0ea5e9',
  resolved: '#10b981',
  closed: '#64748b',
}

export function useTicketTransitions(currentStatus: Ref<TicketStatus | undefined>) {
  const validTransitions = computed(() => {
    if (!currentStatus.value) return []
    return TRANSITIONS[currentStatus.value] || []
  })

  const statusOptions = computed(() => {
    if (!currentStatus.value) return []
    return [
      { label: STATUS_LABELS[currentStatus.value], value: currentStatus.value, color: STATUS_COLORS[currentStatus.value] },
      ...validTransitions.value.map(t => ({ label: t.label, value: t.value, color: t.color })),
    ]
  })

  return { validTransitions, statusOptions, STATUS_LABELS, STATUS_COLORS }
}

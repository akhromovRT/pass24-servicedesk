// Реактивный обёртка над utils/sla.ts. Используется в TicketSlaProgress.vue
// для двух полосок (response + resolve) с автоматическим пересчётом
// при изменении ticket-prop.

import { computed, isRef, ref, type Ref } from 'vue'
import {
  buildActiveProgress,
  buildResolveProgress,
  buildResponseProgress,
  getPauseLabel,
  type SlaProgress,
} from '../utils/sla'
import type { Ticket } from '../types'

export function useSlaProgress(ticketSource: Ref<Ticket> | Ticket) {
  const ticketRef = isRef(ticketSource) ? ticketSource : ref(ticketSource)

  const responseProgress = computed<SlaProgress | null>(() =>
    buildResponseProgress(ticketRef.value),
  )
  const resolveProgress = computed<SlaProgress | null>(() =>
    buildResolveProgress(ticketRef.value),
  )
  const activeProgress = computed<SlaProgress | null>(() =>
    buildActiveProgress(ticketRef.value),
  )
  const isPaused = computed<boolean>(() => !!ticketRef.value.sla_is_paused)
  const pauseLabel = computed<string | null>(() => getPauseLabel(ticketRef.value))

  return {
    responseProgress,
    resolveProgress,
    activeProgress,
    isPaused,
    pauseLabel,
  }
}

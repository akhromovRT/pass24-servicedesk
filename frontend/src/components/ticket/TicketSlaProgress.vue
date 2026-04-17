<script setup lang="ts">
import { computed } from 'vue'
import ProgressBar from 'primevue/progressbar'
import type { Ticket } from '../../types'
import { parseUTC } from '../../utils/date'

const props = defineProps<{
  ticket: Ticket
}>()

function calcElapsedHours(createdAt: string, completedAt: string | null, pausedAt: string | null, totalPauseSeconds: number): number {
  const start = parseUTC(createdAt).getTime()
  const end = completedAt ? parseUTC(completedAt).getTime() : Date.now()
  let pauseMs = totalPauseSeconds * 1000
  if (pausedAt && !completedAt) {
    pauseMs += Date.now() - parseUTC(pausedAt).getTime()
  }
  return Math.max(0, (end - start - pauseMs) / (1000 * 60 * 60))
}

function getColor(pct: number): string {
  if (pct < 50) return '#10b981'
  if (pct < 75) return '#f59e0b'
  if (pct < 90) return '#f97316'
  return '#ef4444'
}

function formatRemaining(hours: number): string {
  if (hours <= 0) return 'Просрочено'
  if (hours < 1) return `${Math.round(hours * 60)} мин`
  if (hours < 24) return `${Math.round(hours)} ч`
  const days = Math.floor(hours / 24)
  const h = Math.round(hours % 24)
  return h > 0 ? `${days} д ${h} ч` : `${days} д`
}

const responseProgress = computed(() => {
  const t = props.ticket
  if (!t.sla_response_hours) return null
  const elapsed = calcElapsedHours(t.created_at, t.first_response_at, t.sla_paused_at, t.sla_total_pause_seconds)
  const pct = Math.min(100, Math.round((elapsed / t.sla_response_hours) * 100))
  const remaining = t.sla_response_hours - elapsed
  return {
    pct,
    color: getColor(pct),
    remaining: t.first_response_at ? 'Выполнено' : formatRemaining(remaining),
    completed: !!t.first_response_at,
  }
})

const resolveProgress = computed(() => {
  const t = props.ticket
  if (!t.sla_resolve_hours) return null
  const elapsed = calcElapsedHours(t.created_at, t.resolved_at, t.sla_paused_at, t.sla_total_pause_seconds)
  const pct = Math.min(100, Math.round((elapsed / t.sla_resolve_hours) * 100))
  const remaining = t.sla_resolve_hours - elapsed
  return {
    pct,
    color: getColor(pct),
    remaining: t.resolved_at ? 'Выполнено' : formatRemaining(remaining),
    completed: !!t.resolved_at,
  }
})

type PauseSource = 'reply' | 'status'

interface PauseInfo {
  source: PauseSource
  label: string
}

const pauseInfo = computed<PauseInfo | null>(() => {
  const t = props.ticket
  // Статус-пауза имеет приоритет в тексте (точнее описывает причину).
  if (t.sla_paused_by_status) {
    const statusLabel = t.status === 'on_hold' ? 'Отложена' : 'Ожидает ответа'
    return { source: 'status', label: `⏸ SLA на паузе — статус «${statusLabel}»` }
  }
  if (t.sla_paused_by_reply) {
    return { source: 'reply', label: '⏸ SLA на паузе — ждём ответ клиента' }
  }
  return null
})
</script>

<template>
  <div class="sla-progress">
    <div v-if="responseProgress" class="sla-item">
      <div class="sla-header">
        <span class="sla-label">Первый ответ</span>
        <span class="sla-remaining" :style="{ color: responseProgress.completed ? '#10b981' : responseProgress.color }">
          {{ responseProgress.remaining }}
        </span>
      </div>
      <ProgressBar
        :value="responseProgress.pct"
        :showValue="false"
        :style="{ height: '6px' }"
        :pt="{ value: { style: { backgroundColor: responseProgress.color } } }"
      />
    </div>
    <div v-if="resolveProgress" class="sla-item">
      <div class="sla-header">
        <span class="sla-label">Решение</span>
        <span class="sla-remaining" :style="{ color: pauseInfo ? '#94a3b8' : (resolveProgress.completed ? '#10b981' : resolveProgress.color) }">
          {{ pauseInfo ? 'На паузе' : resolveProgress.remaining }}
        </span>
      </div>
      <ProgressBar
        :value="resolveProgress.pct"
        :showValue="false"
        :style="{ height: '6px' }"
        :pt="{ value: { style: { backgroundColor: pauseInfo ? '#94a3b8' : resolveProgress.color } } }"
      />
      <div v-if="pauseInfo" class="sla-pause-badge">{{ pauseInfo.label }}</div>
    </div>
    <div v-if="!responseProgress && !resolveProgress" class="sla-empty">
      SLA не настроен
    </div>
  </div>
</template>

<style scoped>
.sla-progress {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.sla-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.sla-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.sla-label {
  font-size: 0.75rem;
  color: #64748b;
  font-weight: 500;
}

.sla-remaining {
  font-size: 0.75rem;
  font-weight: 600;
}

.sla-empty {
  font-size: 0.8125rem;
  color: #94a3b8;
  font-style: italic;
}

.sla-pause-badge {
  margin-top: 4px;
  font-size: 0.75rem;
  color: #64748b;
  background: #f1f5f9;
  padding: 4px 8px;
  border-radius: 4px;
  font-weight: 500;
}
</style>

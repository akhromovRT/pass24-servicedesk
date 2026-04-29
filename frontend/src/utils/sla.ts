// Чистые функции форматирования SLA: единая логика для composable и списка тикетов.
// Все вычисления используют поля, которые бэк уже посчитал в бизнес-часах
// (sla_*_remaining_seconds, sla_is_paused). Без `Date.now()`.

import type { Ticket } from '../types'

const COLOR_GREEN = '#10b981'
const COLOR_YELLOW = '#f59e0b'
const COLOR_ORANGE = '#f97316'
const COLOR_RED = '#ef4444'
const COLOR_GRAY = '#94a3b8'

export interface SlaProgress {
  pct: number          // 0..100
  color: string        // hex
  label: string        // «2 ч 15 мин», «Просрочено на 1 ч 5 мин», «На паузе», «Выполнено»
  completed: boolean   // SLA уже выполнен (first_response_at / resolved_at)
  paused: boolean      // sla_is_paused
  overdue: boolean     // remaining < 0
}

function colorByPct(pct: number): string {
  if (pct < 50) return COLOR_GREEN
  if (pct < 75) return COLOR_YELLOW
  if (pct < 90) return COLOR_ORANGE
  return COLOR_RED
}

function formatDuration(seconds: number): string {
  if (seconds < 60) return '< 1 мин'
  if (seconds < 3600) return `${Math.round(seconds / 60)} мин`
  if (seconds < 86400) {
    const h = Math.floor(seconds / 3600)
    const m = Math.round((seconds % 3600) / 60)
    return m > 0 ? `${h} ч ${m} мин` : `${h} ч`
  }
  const d = Math.floor(seconds / 86400)
  const h = Math.round((seconds % 86400) / 3600)
  return h > 0 ? `${d} д ${h} ч` : `${d} д`
}

function buildLabel(opts: {
  remaining: number | null
  paused: boolean
  completed: boolean
}): string {
  if (opts.completed) return 'Выполнено'
  if (opts.paused) return 'На паузе'
  if (opts.remaining === null) return ''
  if (opts.remaining < 0) return `Просрочено на ${formatDuration(-opts.remaining)}`
  return formatDuration(opts.remaining)
}

function buildProgress(opts: {
  totalHours: number | null
  remainingSeconds: number | null
  completed: boolean
  paused: boolean
}): SlaProgress | null {
  if (opts.totalHours == null) return null

  if (opts.completed) {
    return {
      pct: 100,
      color: COLOR_GREEN,
      label: 'Выполнено',
      completed: true,
      paused: false,
      overdue: false,
    }
  }

  if (opts.paused) {
    return {
      pct: opts.remainingSeconds != null
        ? Math.max(0, Math.min(100, Math.round((1 - opts.remainingSeconds / (opts.totalHours * 3600)) * 100)))
        : 0,
      color: COLOR_GRAY,
      label: buildLabel({ remaining: opts.remainingSeconds, paused: true, completed: false }),
      completed: false,
      paused: true,
      overdue: opts.remainingSeconds != null && opts.remainingSeconds < 0,
    }
  }

  if (opts.remainingSeconds == null) {
    return null
  }

  const overdue = opts.remainingSeconds < 0
  const totalSec = opts.totalHours * 3600
  const pct = overdue
    ? 100
    : Math.max(0, Math.min(100, Math.round((1 - opts.remainingSeconds / totalSec) * 100)))
  const color = overdue ? COLOR_RED : colorByPct(pct)

  return {
    pct,
    color,
    label: buildLabel({ remaining: opts.remainingSeconds, paused: false, completed: false }),
    completed: false,
    paused: false,
    overdue,
  }
}

export function buildResponseProgress(ticket: Ticket): SlaProgress | null {
  return buildProgress({
    totalHours: ticket.sla_response_hours,
    remainingSeconds: ticket.sla_response_remaining_seconds,
    completed: ticket.first_response_at != null,
    paused: !!ticket.sla_is_paused,
  })
}

export function buildResolveProgress(ticket: Ticket): SlaProgress | null {
  return buildProgress({
    totalHours: ticket.sla_resolve_hours,
    remainingSeconds: ticket.sla_resolve_remaining_seconds,
    completed: ticket.resolved_at != null,
    paused: !!ticket.sla_is_paused,
  })
}

/** Активная фаза: пока нет first_response_at — это response, иначе resolve.
 * Используется в TicketsPage для одной полоски на тикет. */
export function buildActiveProgress(ticket: Ticket): SlaProgress | null {
  return ticket.first_response_at == null
    ? buildResponseProgress(ticket)
    : buildResolveProgress(ticket)
}

export function getPauseLabel(ticket: Ticket): string | null {
  if (!ticket.sla_is_paused) return null
  if (ticket.sla_paused_by_status) {
    const statusLabel = ticket.status === 'on_hold' ? 'Отложена' : 'Ожидание ответа клиента'
    return `⏸ SLA на паузе — статус «${statusLabel}»`
  }
  if (ticket.sla_paused_by_reply) {
    return '⏸ SLA на паузе — ждём ответ клиента'
  }
  return '⏸ SLA на паузе'
}

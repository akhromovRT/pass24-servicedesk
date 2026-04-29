import { describe, it, expect } from 'vitest'
import { ref } from 'vue'
import {
  buildActiveProgress,
  buildResponseProgress,
  buildResolveProgress,
  getPauseLabel,
} from '../../utils/sla'
import { useSlaProgress } from '../useSlaProgress'
import type { Ticket } from '../../types'

function makeTicket(overrides: Partial<Ticket> = {}): Ticket {
  // Минимальный shape — composable использует только SLA-поля.
  return {
    id: 't1',
    creator_id: 'u',
    assignee_id: null,
    title: 't',
    description: '',
    product: null,
    category: null,
    ticket_type: null,
    source: null,
    status: 'in_progress',
    priority: 'normal',
    object_name: null,
    object_address: null,
    access_point: null,
    contact_name: null,
    contact_email: null,
    contact_phone: null,
    company: null,
    customer_id: null,
    customer_is_permanent: null,
    device_type: null,
    app_version: null,
    error_message: null,
    urgent: false,
    created_at: '2026-05-04T09:00:00',
    updated_at: '2026-05-04T09:00:00',
    first_response_at: null,
    resolved_at: null,
    sla_response_hours: 4,
    sla_resolve_hours: 8,
    sla_breached: false,
    sla_paused_at: null,
    sla_total_pause_seconds: 0,
    sla_paused_by_status: false,
    sla_paused_by_reply: false,
    sla_response_due_at: null,
    sla_resolve_due_at: null,
    sla_response_remaining_seconds: null,
    sla_resolve_remaining_seconds: null,
    sla_remaining_seconds: null,
    sla_is_paused: false,
    has_unread_reply: false,
    parent_ticket_id: null,
    implementation_project_id: null,
    is_implementation_blocker: false,
    satisfaction_rating: null,
    satisfaction_comment: null,
    satisfaction_submitted_at: null,
    events: [],
    comments: [],
    attachments: [],
    ...overrides,
  } as Ticket
}

describe('buildResolveProgress', () => {
  it('25% прошло (зелёный) при remaining = 6ч из 8ч', () => {
    const t = makeTicket({
      sla_resolve_hours: 8,
      sla_resolve_remaining_seconds: 6 * 3600,
      first_response_at: '2026-05-04T09:30:00',
    })
    const p = buildResolveProgress(t)
    expect(p).not.toBeNull()
    expect(p!.pct).toBe(25)
    expect(p!.color).toBe('#10b981') // green
    expect(p!.label).toBe('6 ч')
    expect(p!.completed).toBe(false)
    expect(p!.paused).toBe(false)
    expect(p!.overdue).toBe(false)
  })

  it('75% прошло (оранжевый) при remaining = 2ч из 8ч', () => {
    const t = makeTicket({
      sla_resolve_hours: 8,
      sla_resolve_remaining_seconds: 2 * 3600,
    })
    const p = buildResolveProgress(t)
    expect(p!.pct).toBe(75)
    expect(p!.color).toBe('#f97316') // orange
    expect(p!.label).toBe('2 ч')
  })

  it('paused → серый, label «На паузе»', () => {
    const t = makeTicket({
      sla_resolve_hours: 8,
      sla_resolve_remaining_seconds: 4 * 3600,
      sla_is_paused: true,
      sla_paused_at: '2026-05-04T10:00:00',
      sla_paused_by_reply: true,
    })
    const p = buildResolveProgress(t)
    expect(p!.color).toBe('#94a3b8') // gray
    expect(p!.label).toBe('На паузе')
    expect(p!.paused).toBe(true)
  })

  it('просрочено: remaining = -8100 → «Просрочено на 2 ч 15 мин», красный', () => {
    const t = makeTicket({
      sla_resolve_hours: 8,
      sla_resolve_remaining_seconds: -8100,
    })
    const p = buildResolveProgress(t)
    expect(p!.label).toBe('Просрочено на 2 ч 15 мин')
    expect(p!.color).toBe('#ef4444')
    expect(p!.pct).toBe(100)
    expect(p!.overdue).toBe(true)
  })

  it('resolved_at задан → completed, зелёный, «Выполнено»', () => {
    const t = makeTicket({
      sla_resolve_hours: 8,
      sla_resolve_remaining_seconds: 0,
      resolved_at: '2026-05-04T15:00:00',
    })
    const p = buildResolveProgress(t)
    expect(p!.completed).toBe(true)
    expect(p!.label).toBe('Выполнено')
    expect(p!.color).toBe('#10b981')
    expect(p!.pct).toBe(100)
  })

  it('sla_resolve_remaining_seconds = null → null (skeleton)', () => {
    const t = makeTicket({
      sla_resolve_hours: 8,
      sla_resolve_remaining_seconds: null,
    })
    expect(buildResolveProgress(t)).toBeNull()
  })

  it('sla_resolve_hours = null → null', () => {
    const t = makeTicket({ sla_resolve_hours: null })
    expect(buildResolveProgress(t)).toBeNull()
  })
})

describe('buildResponseProgress', () => {
  it('first_response_at задан → completed', () => {
    const t = makeTicket({
      first_response_at: '2026-05-04T09:30:00',
      sla_response_remaining_seconds: 1800,
    })
    const p = buildResponseProgress(t)
    expect(p!.completed).toBe(true)
    expect(p!.label).toBe('Выполнено')
  })

  it('меньше минуты остатка → «< 1 мин»', () => {
    const t = makeTicket({
      sla_response_hours: 1,
      sla_response_remaining_seconds: 30,
    })
    const p = buildResponseProgress(t)
    expect(p!.label).toBe('< 1 мин')
  })
})

describe('buildActiveProgress', () => {
  it('нет first_response_at → активная фаза = response', () => {
    const t = makeTicket({
      first_response_at: null,
      sla_response_hours: 4,
      sla_response_remaining_seconds: 7200,
      sla_resolve_hours: 8,
      sla_resolve_remaining_seconds: 25200,
    })
    const p = buildActiveProgress(t)
    // 7200/14400 = 50% потрачено → pct=50, label «2 ч»
    expect(p!.pct).toBe(50)
    expect(p!.label).toBe('2 ч')
  })

  it('first_response_at задан → активная фаза = resolve', () => {
    const t = makeTicket({
      first_response_at: '2026-05-04T09:30:00',
      sla_response_remaining_seconds: -1800,  // response уже не активен
      sla_resolve_hours: 8,
      sla_resolve_remaining_seconds: 4 * 3600,
    })
    const p = buildActiveProgress(t)
    expect(p!.label).toBe('4 ч')  // от resolve
    expect(p!.pct).toBe(50)
  })
})

describe('getPauseLabel', () => {
  it('paused_by_status / on_hold → «Отложена»', () => {
    const t = makeTicket({
      sla_is_paused: true,
      sla_paused_by_status: true,
      status: 'on_hold',
    })
    expect(getPauseLabel(t)).toBe('⏸ SLA на паузе — статус «Отложена»')
  })

  it('paused_by_status / waiting_for_user → «Ожидание ответа клиента»', () => {
    const t = makeTicket({
      sla_is_paused: true,
      sla_paused_by_status: true,
      status: 'waiting_for_user',
    })
    expect(getPauseLabel(t)).toBe('⏸ SLA на паузе — статус «Ожидание ответа клиента»')
  })

  it('paused_by_reply', () => {
    const t = makeTicket({
      sla_is_paused: true,
      sla_paused_by_reply: true,
    })
    expect(getPauseLabel(t)).toBe('⏸ SLA на паузе — ждём ответ клиента')
  })

  it('not paused → null', () => {
    const t = makeTicket({ sla_is_paused: false })
    expect(getPauseLabel(t)).toBeNull()
  })
})

describe('useSlaProgress (reactive)', () => {
  it('реактивно пересчитывается при смене ticket', () => {
    const t = ref(
      makeTicket({
        sla_resolve_hours: 8,
        sla_resolve_remaining_seconds: 6 * 3600,
        first_response_at: '2026-05-04T09:30:00',
      }),
    )
    const { resolveProgress, isPaused } = useSlaProgress(t)
    expect(resolveProgress.value!.pct).toBe(25)
    expect(isPaused.value).toBe(false)

    // Меняем ticket — composable должен пересчитать
    t.value = {
      ...t.value,
      sla_resolve_remaining_seconds: 1 * 3600,
      sla_is_paused: true,
      sla_paused_at: '2026-05-04T10:00:00',
    }
    expect(resolveProgress.value!.color).toBe('#94a3b8')
    expect(isPaused.value).toBe(true)
  })

  it('принимает обычный объект Ticket (не Ref)', () => {
    const t = makeTicket({
      sla_resolve_hours: 8,
      sla_resolve_remaining_seconds: 4 * 3600,
      first_response_at: '2026-05-04T09:30:00',
    })
    const { resolveProgress } = useSlaProgress(t)
    expect(resolveProgress.value!.pct).toBe(50)
  })
})

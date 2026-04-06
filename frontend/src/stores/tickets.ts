import { defineStore } from 'pinia'
import { ref } from 'vue'
import { api } from '../api/client'
import type {
  Ticket,
  TicketCreate,
  TicketComment,
  TicketStatus,
  PaginatedResponse,
} from '../types'

export interface TicketFilters {
  status?: string[]
  category?: string[]
  product?: string[]
  type?: string[]
  creator_id?: string
  my?: boolean
  q?: string
  view?: string
  sort?: string
}

export interface TicketStats {
  total: number
  open: number
  overdue: number
  waiting: number
  urgent: number
  new: number
}

export interface SavedView {
  id: string
  name: string
  icon: string | null
  filters: Record<string, any>
  owner_id: string
  is_shared: boolean
  sort_order: number
  usage_count: number
  created_at: string
}

export interface SavedViewCreate {
  name: string
  icon?: string | null
  filters: Record<string, any>
  is_shared?: boolean
  sort_order?: number
}

export const useTicketsStore = defineStore('tickets', () => {
  const tickets = ref<Ticket[]>([])
  const currentTicket = ref<Ticket | null>(null)
  const total = ref(0)
  const page = ref(1)
  const loading = ref(false)
  const filters = ref<TicketFilters>({})
  const stats = ref<TicketStats>({ total: 0, open: 0, overdue: 0, waiting: 0, urgent: 0, new: 0 })
  const savedViews = ref<SavedView[]>([])

  async function fetchTickets(p?: number, f?: TicketFilters) {
    loading.value = true
    try {
      if (p !== undefined) page.value = p
      if (f !== undefined) filters.value = f

      const params = new URLSearchParams()
      params.set('page', String(page.value))
      params.set('per_page', '20')

      // Массивы → через запятую
      if (filters.value.status?.length) params.set('status', filters.value.status.join(','))
      if (filters.value.category?.length) params.set('category', filters.value.category.join(','))
      if (filters.value.product?.length) params.set('product', filters.value.product.join(','))
      if (filters.value.type?.length) params.set('type', filters.value.type.join(','))
      if (filters.value.creator_id) params.set('creator_id', filters.value.creator_id)
      if (filters.value.my) params.set('my', 'true')
      if (filters.value.q) params.set('q', filters.value.q)
      if (filters.value.view) params.set('view', filters.value.view)
      if (filters.value.sort) params.set('sort', filters.value.sort)

      const data = await api.get<PaginatedResponse<Ticket>>(
        `/tickets/?${params.toString()}`,
      )
      tickets.value = data.items
      total.value = data.total
    } finally {
      loading.value = false
    }
  }

  async function fetchStats() {
    try {
      stats.value = await api.get<TicketStats>('/tickets/stats')
    } catch {
      // silent
    }
  }

  async function fetchTicket(id: string) {
    loading.value = true
    try {
      currentTicket.value = await api.get<Ticket>(`/tickets/${id}`)
    } finally {
      loading.value = false
    }
  }

  async function createTicket(data: TicketCreate): Promise<Ticket> {
    loading.value = true
    try {
      return await api.post<Ticket>('/tickets/', data)
    } finally {
      loading.value = false
    }
  }

  async function updateStatus(id: string, newStatus: TicketStatus): Promise<Ticket> {
    const ticket = await api.post<Ticket>(`/tickets/${id}/status`, {
      new_status: newStatus,
    })
    currentTicket.value = ticket
    return ticket
  }

  async function addComment(id: string, text: string, is_internal = false): Promise<TicketComment> {
    const comment = await api.post<TicketComment>(`/tickets/${id}/comments`, {
      text,
      is_internal,
    })
    if (currentTicket.value && currentTicket.value.id === id) {
      currentTicket.value.comments.push(comment)
    }
    return comment
  }

  async function deleteTicket(id: string): Promise<void> {
    await api.delete<void>(`/tickets/${id}`)
    tickets.value = tickets.value.filter((t) => t.id !== id)
    if (currentTicket.value?.id === id) {
      currentTicket.value = null
    }
  }

  async function assignTicket(id: string, assignee_id: string | null): Promise<Ticket> {
    const ticket = await api.put<Ticket>(`/tickets/${id}/assignment`, { assignee_id })
    if (currentTicket.value?.id === id) currentTicket.value = ticket
    return ticket
  }

  async function bulkAction(ticket_ids: string[], action: string, value?: string): Promise<number> {
    const r = await api.post<{ updated: number }>('/tickets/bulk', { ticket_ids, action, value })
    return r.updated
  }

  async function mergeTicket(sourceId: string, targetId: string): Promise<Ticket> {
    return await api.post<Ticket>(`/tickets/${sourceId}/merge`, { target_ticket_id: targetId })
  }

  async function applyMacro(ticketId: string, macroId: string): Promise<Ticket> {
    const ticket = await api.post<Ticket>(`/tickets/${ticketId}/apply-macro`, { macro_id: macroId })
    if (currentTicket.value?.id === ticketId) currentTicket.value = ticket
    return ticket
  }

  async function fetchSavedViews(): Promise<SavedView[]> {
    try {
      const data = await api.get<SavedView[]>('/tickets/saved-views')
      savedViews.value = data
      return data
    } catch {
      savedViews.value = []
      return []
    }
  }

  async function createSavedView(data: SavedViewCreate): Promise<SavedView> {
    return await api.post<SavedView>('/tickets/saved-views', data)
  }

  async function deleteSavedView(id: string): Promise<void> {
    await api.delete<void>(`/tickets/saved-views/${id}`)
    savedViews.value = savedViews.value.filter((v) => v.id !== id)
  }

  function recordViewUsage(id: string): void {
    // fire and forget
    api.post<void>(`/tickets/saved-views/${id}/use`).catch(() => {
      // silent
    })
  }

  return {
    tickets,
    currentTicket,
    total,
    page,
    loading,
    filters,
    stats,
    savedViews,
    fetchTickets,
    fetchStats,
    fetchTicket,
    createTicket,
    updateStatus,
    addComment,
    deleteTicket,
    assignTicket,
    bulkAction,
    mergeTicket,
    applyMacro,
    fetchSavedViews,
    createSavedView,
    deleteSavedView,
    recordViewUsage,
  }
})

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
  status?: TicketStatus | ''
  category?: string
  object_id?: string
  creator_id?: string
  my?: boolean
}

export const useTicketsStore = defineStore('tickets', () => {
  const tickets = ref<Ticket[]>([])
  const currentTicket = ref<Ticket | null>(null)
  const total = ref(0)
  const page = ref(1)
  const loading = ref(false)
  const filters = ref<TicketFilters>({})

  async function fetchTickets(p?: number, f?: TicketFilters) {
    loading.value = true
    try {
      if (p !== undefined) page.value = p
      if (f !== undefined) filters.value = f

      const params = new URLSearchParams()
      params.set('page', String(page.value))
      params.set('per_page', '20')
      if (filters.value.status) params.set('status', filters.value.status)
      if (filters.value.category) params.set('category', filters.value.category)
      if (filters.value.object_id) params.set('object_id', filters.value.object_id)
      if (filters.value.creator_id) params.set('creator_id', filters.value.creator_id)
      if (filters.value.my) params.set('my', 'true')

      const data = await api.get<PaginatedResponse<Ticket>>(
        `/tickets/?${params.toString()}`,
      )
      tickets.value = data.items
      total.value = data.total
    } finally {
      loading.value = false
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
      const ticket = await api.post<Ticket>('/tickets/', data)
      return ticket
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

  return {
    tickets,
    currentTicket,
    total,
    page,
    loading,
    filters,
    fetchTickets,
    fetchTicket,
    createTicket,
    updateStatus,
    addComment,
    deleteTicket,
  }
})

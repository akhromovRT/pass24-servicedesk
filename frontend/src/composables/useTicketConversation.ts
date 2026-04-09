import { computed, type Ref } from 'vue'
import type { Ticket, TicketComment, TicketEvent } from '../types'
import { parseUTC } from '../utils/date'

export interface TimelineItem {
  type: 'comment' | 'event'
  data: TicketComment | TicketEvent
  timestamp: Date
}

export function useTicketConversation(ticket: Ref<Ticket | null>) {
  const timeline = computed<TimelineItem[]>(() => {
    if (!ticket.value) return []

    const items: TimelineItem[] = []

    // Add comments
    for (const comment of ticket.value.comments) {
      items.push({
        type: 'comment',
        data: comment,
        timestamp: parseUTC(comment.created_at),
      })
    }

    // Add events
    for (const event of ticket.value.events) {
      items.push({
        type: 'event',
        data: event,
        timestamp: parseUTC(event.created_at),
      })
    }

    // Sort chronologically
    items.sort((a, b) => a.timestamp.getTime() - b.timestamp.getTime())

    return items
  })

  return { timeline }
}

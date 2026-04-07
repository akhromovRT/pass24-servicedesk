<script setup lang="ts">
import Panel from 'primevue/panel'
import type { TicketEvent } from '../../types'

defineProps<{
  events: TicketEvent[]
}>()

function formatDate(iso: string): string {
  const d = new Date(iso)
  return d.toLocaleString('ru-RU', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}
</script>

<template>
  <Panel header="История событий" toggleable collapsed>
    <div v-if="events.length === 0" class="events-empty">
      Нет событий
    </div>
    <ul v-else class="events-list">
      <li v-for="event in events" :key="event.id" class="event-item">
        <span class="event-time">{{ formatDate(event.created_at) }}</span>
        <span class="event-desc">{{ event.description }}</span>
      </li>
    </ul>
  </Panel>
</template>

<style scoped>
.events-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.event-item {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding-bottom: 8px;
  border-bottom: 1px solid #f1f5f9;
}

.event-item:last-child {
  border-bottom: none;
  padding-bottom: 0;
}

.event-time {
  font-size: 0.75rem;
  color: #94a3b8;
  font-variant-numeric: tabular-nums;
}

.event-desc {
  font-size: 0.8125rem;
  color: #475569;
}

.events-empty {
  font-size: 0.8125rem;
  color: #94a3b8;
  font-style: italic;
}
</style>

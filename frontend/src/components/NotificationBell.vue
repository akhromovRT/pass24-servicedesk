<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import Button from 'primevue/button'
import OverlayPanel from 'primevue/overlaypanel'
import Badge from 'primevue/badge'
import { api } from '../api/client'

interface UnreadTicket {
  id: string
  title: string
  status: string
  priority: string
  contact_name: string | null
  contact_email: string | null
  updated_at: string
}

interface UnreadResponse {
  count: number
  items: UnreadTicket[]
}

const router = useRouter()
const op = ref<InstanceType<typeof OverlayPanel> | null>(null)
const unreadCount = ref(0)
const unreadItems = ref<UnreadTicket[]>([])
const loading = ref(false)

let pollTimer: ReturnType<typeof setInterval> | null = null

async function loadUnread() {
  try {
    const data = await api.get<UnreadResponse>('/tickets/notifications/unread')
    const prevCount = unreadCount.value
    unreadCount.value = data.count
    unreadItems.value = data.items
    // Звуковой сигнал при появлении нового уведомления (опционально)
    if (data.count > prevCount && prevCount > 0) {
      // Тихий "ping" через AudioContext
      try {
        const ctx = new AudioContext()
        const osc = ctx.createOscillator()
        const gain = ctx.createGain()
        osc.connect(gain)
        gain.connect(ctx.destination)
        osc.frequency.value = 880
        gain.gain.value = 0.1
        osc.start()
        setTimeout(() => { osc.stop(); ctx.close() }, 150)
      } catch {}
    }
  } catch {
    // ignore — просто не обновляем
  }
}

async function toggle(event: Event) {
  op.value?.toggle(event)
  loading.value = true
  await loadUnread()
  loading.value = false
}

function openTicket(ticketId: string) {
  op.value?.hide()
  router.push(`/tickets/${ticketId}`)
  // Обновим счётчик после перехода (сервер сам сбросит флаг при get)
  setTimeout(loadUnread, 500)
}

function formatDate(iso: string): string {
  const d = new Date(iso)
  const now = new Date()
  const diffMs = now.getTime() - d.getTime()
  const diffMin = Math.floor(diffMs / 60000)
  if (diffMin < 1) return 'только что'
  if (diffMin < 60) return `${diffMin} мин назад`
  const diffHours = Math.floor(diffMin / 60)
  if (diffHours < 24) return `${diffHours} ч назад`
  return new Intl.DateTimeFormat('ru-RU', { day: 'numeric', month: 'short' }).format(d)
}

const priorityColors: Record<string, string> = {
  critical: '#dc2626',
  high: '#f59e0b',
  normal: '#3b82f6',
  low: '#94a3b8',
}

onMounted(() => {
  loadUnread()
  pollTimer = setInterval(loadUnread, 20000)  // каждые 20 сек
})

onUnmounted(() => {
  if (pollTimer) clearInterval(pollTimer)
})
</script>

<template>
  <div class="notification-bell">
    <Button
      icon="pi pi-bell"
      severity="secondary"
      text
      rounded
      size="small"
      class="bell-button"
      :aria-label="`Уведомления: ${unreadCount}`"
      @click="toggle"
    >
      <i class="pi pi-bell" />
      <Badge
        v-if="unreadCount > 0"
        :value="unreadCount > 99 ? '99+' : String(unreadCount)"
        severity="danger"
        class="bell-badge"
      />
    </Button>

    <OverlayPanel ref="op" class="notifications-panel">
      <div class="panel-header">
        <h3>Новые ответы клиентов</h3>
        <span class="panel-count">{{ unreadCount }}</span>
      </div>

      <div v-if="loading" class="panel-loading">
        <i class="pi pi-spin pi-spinner" />
      </div>

      <div v-else-if="unreadItems.length === 0" class="panel-empty">
        <i class="pi pi-inbox" />
        <p>Нет новых ответов</p>
      </div>

      <ul v-else class="panel-list">
        <li
          v-for="item in unreadItems"
          :key="item.id"
          class="panel-item"
          @click="openTicket(item.id)"
        >
          <div
            class="priority-dot"
            :style="{ backgroundColor: priorityColors[item.priority] || '#94a3b8' }"
          />
          <div class="item-content">
            <div class="item-title">{{ item.title }}</div>
            <div class="item-meta">
              <span v-if="item.contact_name">{{ item.contact_name }}</span>
              <span v-else-if="item.contact_email">{{ item.contact_email }}</span>
              <span class="item-dot">·</span>
              <span>{{ formatDate(item.updated_at) }}</span>
            </div>
          </div>
          <i class="pi pi-angle-right item-arrow" />
        </li>
      </ul>
    </OverlayPanel>
  </div>
</template>

<style scoped>
.notification-bell {
  position: relative;
}

.bell-button {
  position: relative;
}

.bell-badge {
  position: absolute;
  top: -2px;
  right: -2px;
  min-width: 18px;
  height: 18px;
  font-size: 10px;
}

.notifications-panel {
  width: 380px;
  max-width: 95vw;
}

:global(.notifications-panel .p-overlaypanel-content) {
  padding: 0;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 14px 16px;
  border-bottom: 1px solid #e2e8f0;
}

.panel-header h3 {
  font-size: 14px;
  font-weight: 600;
  color: #1e293b;
  margin: 0;
}

.panel-count {
  font-size: 12px;
  color: #64748b;
  background: #f1f5f9;
  padding: 2px 8px;
  border-radius: 10px;
}

.panel-loading,
.panel-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 32px 16px;
  color: #94a3b8;
}

.panel-empty i {
  font-size: 32px;
}

.panel-empty p {
  margin: 0;
  font-size: 13px;
}

.panel-list {
  list-style: none;
  margin: 0;
  padding: 0;
  max-height: 400px;
  overflow-y: auto;
}

.panel-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  cursor: pointer;
  border-bottom: 1px solid #f1f5f9;
  transition: background 0.15s;
}

.panel-item:last-child {
  border-bottom: none;
}

.panel-item:hover {
  background: #f8fafc;
}

.priority-dot {
  flex: 0 0 auto;
  width: 8px;
  height: 8px;
  border-radius: 50%;
}

.item-content {
  flex: 1;
  min-width: 0;
}

.item-title {
  font-size: 13px;
  font-weight: 500;
  color: #1e293b;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.item-meta {
  font-size: 11px;
  color: #64748b;
  display: flex;
  align-items: center;
  gap: 4px;
  margin-top: 2px;
}

.item-dot {
  color: #cbd5e1;
}

.item-arrow {
  color: #cbd5e1;
  font-size: 12px;
}
</style>

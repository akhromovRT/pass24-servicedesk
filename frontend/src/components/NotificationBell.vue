<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import OverlayPanel from 'primevue/overlaypanel'
import { api } from '../api/client'

interface NotificationItem {
  id: string
  title: string
  status: string
  priority: string
  contact_name: string | null
  contact_email: string | null
  updated_at: string
  is_unread: boolean
}

interface RecentResponse {
  unread_count: number
  items: NotificationItem[]
}

type Mode = 'compact' | 'expanded'

const COMPACT_LIMIT = 10
const EXPANDED_PERIOD_DAYS = 30
const EXPANDED_LIMIT = 200
const POLL_INTERVAL_MS = 20_000

const router = useRouter()
const op = ref<InstanceType<typeof OverlayPanel> | null>(null)
const unreadCount = ref(0)
const items = ref<NotificationItem[]>([])
const loading = ref(false)
const mode = ref<Mode>('compact')

let pollTimer: ReturnType<typeof setInterval> | null = null

async function loadNotifications(target: Mode = mode.value) {
  loading.value = true
  try {
    const params =
      target === 'compact'
        ? `?limit=${COMPACT_LIMIT}`
        : `?limit=${EXPANDED_LIMIT}&period_days=${EXPANDED_PERIOD_DAYS}`
    const data = await api.get<RecentResponse>(`/tickets/notifications/recent${params}`)
    const prevCount = unreadCount.value
    unreadCount.value = data.unread_count
    items.value = data.items
    mode.value = target
    // Тихий "ping" когда появилось новое уведомление в фоне
    if (data.unread_count > prevCount && prevCount > 0) {
      try {
        const ctx = new AudioContext()
        const osc = ctx.createOscillator()
        const gain = ctx.createGain()
        osc.connect(gain)
        gain.connect(ctx.destination)
        osc.frequency.value = 880
        gain.gain.value = 0.1
        osc.start()
        setTimeout(() => {
          osc.stop()
          ctx.close()
        }, 150)
      } catch {
        // AudioContext недоступен — нормально
      }
    }
  } catch {
    // ignore — просто не обновляем
  } finally {
    loading.value = false
  }
}

async function pollUnreadOnly() {
  // Фоновый polling: тянем тот же compact-список, чтобы не сбивать UI при разворнутой панели
  if (mode.value === 'expanded') return
  await loadNotifications('compact')
}

async function toggle(event: Event) {
  op.value?.toggle(event)
  // При открытии — обновляем актуальный список
  await loadNotifications(mode.value)
}

function openTicket(ticketId: string) {
  op.value?.hide()
  router.push(`/tickets/${ticketId}`)
  // Обновим счётчик после перехода (сервер сам сбросит флаг при get)
  setTimeout(() => loadNotifications('compact'), 500)
}

async function showAll() {
  await loadNotifications('expanded')
}

async function collapse() {
  await loadNotifications('compact')
}

const headerTitle = computed(() =>
  mode.value === 'compact' ? 'Уведомления' : 'Все уведомления за 30 дней',
)

const hasMoreToShow = computed(() => items.value.length >= COMPACT_LIMIT)

function formatDate(iso: string): string {
  const d = new Date(iso)
  const now = new Date()
  const diffMs = now.getTime() - d.getTime()
  const diffMin = Math.floor(diffMs / 60000)
  if (diffMin < 1) return 'только что'
  if (diffMin < 60) return `${diffMin} мин назад`
  const diffHours = Math.floor(diffMin / 60)
  if (diffHours < 24) return `${diffHours} ч назад`
  const diffDays = Math.floor(diffHours / 24)
  if (diffDays < 7) return `${diffDays} дн назад`
  return new Intl.DateTimeFormat('ru-RU', { day: 'numeric', month: 'short' }).format(d)
}

const priorityColors: Record<string, string> = {
  critical: '#dc2626',
  high: '#f59e0b',
  normal: '#3b82f6',
  low: '#94a3b8',
}

onMounted(() => {
  loadNotifications('compact')
  pollTimer = setInterval(pollUnreadOnly, POLL_INTERVAL_MS)
})

onUnmounted(() => {
  if (pollTimer) clearInterval(pollTimer)
})
</script>

<template>
  <div class="notification-bell">
    <button
      type="button"
      class="bell-button"
      :class="{ 'has-unread': unreadCount > 0 }"
      :aria-label="`Уведомления: ${unreadCount}`"
      @click="toggle"
    >
      <i class="pi pi-bell bell-icon" />
      <span v-if="unreadCount > 0" class="bell-badge">
        {{ unreadCount > 99 ? '99+' : unreadCount }}
      </span>
    </button>

    <OverlayPanel ref="op" class="notifications-panel" append-to="body">
      <div class="panel-header">
        <h3>{{ headerTitle }}</h3>
        <span v-if="unreadCount > 0" class="panel-count">{{ unreadCount }} непрочит.</span>
      </div>

      <div v-if="loading" class="panel-loading">
        <i class="pi pi-spin pi-spinner" />
      </div>

      <div v-else-if="items.length === 0" class="panel-empty">
        <i class="pi pi-inbox" />
        <p>Нет уведомлений</p>
      </div>

      <ul v-else class="panel-list" :class="{ 'is-expanded': mode === 'expanded' }">
        <li
          v-for="item in items"
          :key="item.id"
          class="panel-item"
          :class="{ 'is-read': !item.is_unread, 'is-unread': item.is_unread }"
          @click="openTicket(item.id)"
        >
          <div
            class="priority-dot"
            :style="{ backgroundColor: priorityColors[item.priority] || '#94a3b8' }"
          />
          <div class="item-content">
            <div class="item-title">
              <span v-if="item.is_unread" class="unread-dot" aria-hidden="true" />
              {{ item.title }}
            </div>
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

      <div v-if="!loading && items.length > 0" class="panel-footer">
        <button
          v-if="mode === 'compact' && hasMoreToShow"
          type="button"
          class="footer-btn"
          @click="showAll"
        >
          Смотреть все
          <i class="pi pi-angle-down" />
        </button>
        <button
          v-else-if="mode === 'expanded'"
          type="button"
          class="footer-btn"
          @click="collapse"
        >
          Свернуть
          <i class="pi pi-angle-up" />
        </button>
      </div>
    </OverlayPanel>
  </div>
</template>

<style scoped>
.notification-bell {
  position: relative;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.bell-button {
  position: relative;
  width: 40px;
  height: 40px;
  border-radius: 50%;
  border: none;
  background: transparent;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: #475569;
  transition: background 0.15s, color 0.15s;
  /* Без overflow: hidden — иначе обрежется индикатор */
  overflow: visible;
}

.bell-button:hover {
  background: #f1f5f9;
  color: #1e293b;
}

.bell-button:focus-visible {
  outline: 2px solid #3b82f6;
  outline-offset: 2px;
}

.bell-button.has-unread {
  color: #1e293b;
}

.bell-icon {
  font-size: 1.25rem;
  line-height: 1;
}

.bell-badge {
  position: absolute;
  top: 2px;
  right: 2px;
  min-width: 18px;
  height: 18px;
  padding: 0 5px;
  border-radius: 9px;
  background: #dc2626;
  color: #fff;
  font-size: 11px;
  font-weight: 600;
  line-height: 18px;
  text-align: center;
  box-shadow: 0 0 0 2px #fff;
  pointer-events: none;
  /* Гарантированно над иконкой и не обрезается */
  z-index: 1;
}

.notifications-panel {
  width: 400px;
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
  color: #b91c1c;
  background: #fee2e2;
  padding: 2px 8px;
  border-radius: 10px;
  font-weight: 500;
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

.panel-list.is-expanded {
  max-height: 60vh;
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

.panel-item.is-unread {
  background: #f0f9ff;
}

.panel-item.is-unread:hover {
  background: #e0f2fe;
}

.panel-item.is-read .item-title,
.panel-item.is-read .item-meta {
  color: #94a3b8;
}

.panel-item.is-read .priority-dot {
  opacity: 0.5;
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
  display: flex;
  align-items: center;
  gap: 6px;
}

.panel-item.is-unread .item-title {
  font-weight: 600;
  color: #0c4a6e;
}

.unread-dot {
  flex: 0 0 auto;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #2563eb;
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

.panel-footer {
  border-top: 1px solid #e2e8f0;
  padding: 8px;
}

.footer-btn {
  width: 100%;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  background: transparent;
  border: none;
  padding: 8px 12px;
  font-size: 13px;
  font-weight: 500;
  color: #2563eb;
  border-radius: 6px;
  cursor: pointer;
  transition: background 0.15s;
}

.footer-btn:hover {
  background: #eff6ff;
}

.footer-btn:focus-visible {
  outline: 2px solid #3b82f6;
  outline-offset: 2px;
}
</style>

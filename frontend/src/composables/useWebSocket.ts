import { ref, onMounted, onUnmounted } from 'vue'

export interface WSMessage {
  event: string
  data: Record<string, any>
}

const listeners = new Set<(msg: WSMessage) => void>()
let socket: WebSocket | null = null
let reconnectTimer: ReturnType<typeof setTimeout> | null = null
const connected = ref(false)

function getWsUrl(): string {
  const token = localStorage.getItem('access_token') || ''
  const proto = location.protocol === 'https:' ? 'wss' : 'ws'
  return `${proto}://${location.host}/ws?token=${token}`
}

function connect() {
  if (socket && (socket.readyState === WebSocket.OPEN || socket.readyState === WebSocket.CONNECTING)) {
    return
  }

  const token = localStorage.getItem('access_token')
  if (!token) return

  socket = new WebSocket(getWsUrl())

  socket.onopen = () => {
    connected.value = true
    if (reconnectTimer) {
      clearTimeout(reconnectTimer)
      reconnectTimer = null
    }
  }

  socket.onmessage = (event) => {
    try {
      const msg: WSMessage = JSON.parse(event.data)
      listeners.forEach(fn => fn(msg))
    } catch {}
  }

  socket.onclose = () => {
    connected.value = false
    socket = null
    // Reconnect через 5 секунд
    if (!reconnectTimer) {
      reconnectTimer = setTimeout(connect, 5000)
    }
  }

  socket.onerror = () => {
    socket?.close()
  }
}

export function useWebSocket(handler?: (msg: WSMessage) => void) {
  onMounted(() => {
    connect()
    if (handler) listeners.add(handler)
  })

  onUnmounted(() => {
    if (handler) listeners.delete(handler)
  })

  return { connected }
}

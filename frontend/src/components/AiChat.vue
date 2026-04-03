<script setup lang="ts">
import { ref, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import Button from 'primevue/button'
import Textarea from 'primevue/textarea'
import { api } from '../api/client'

interface Message {
  role: 'user' | 'assistant'
  content: string
  sources?: string[]
  suggestTicket?: boolean
  ticketData?: TicketData | null
}

interface TicketData {
  title: string
  description: string
  product: string
  category: string
  ticket_type?: string
}

interface ChatResponse {
  reply: string
  sources: string[]
  suggest_ticket: boolean
  ticket_data: TicketData | null
}

const router = useRouter()
const isOpen = ref(false)
const input = ref('')
const messages = ref<Message[]>([])
const loading = ref(false)
const chatBody = ref<HTMLElement | null>(null)

function toggle() {
  isOpen.value = !isOpen.value
  if (isOpen.value && messages.value.length === 0) {
    messages.value.push({
      role: 'assistant',
      content: 'Здравствуйте! Я AI-помощник PASS24 Service Desk. Задайте вопрос о системе контроля доступа, пропусках, приложении или оборудовании — постараюсь помочь.',
    })
  }
}

async function send() {
  const text = input.value.trim()
  if (!text || loading.value) return

  messages.value.push({ role: 'user', content: text })
  input.value = ''
  loading.value = true
  scrollToBottom()

  try {
    const history = messages.value.slice(0, -1).map(m => ({
      role: m.role,
      content: m.content,
    }))

    const resp = await api.post<ChatResponse>('/assistant/chat', {
      message: text,
      history,
    })

    messages.value.push({
      role: 'assistant',
      content: resp.reply,
      sources: resp.sources,
      suggestTicket: resp.suggest_ticket,
      ticketData: resp.ticket_data,
    })
  } catch {
    messages.value.push({
      role: 'assistant',
      content: 'Извините, произошла ошибка. Попробуйте позже или создайте заявку.',
      suggestTicket: true,
    })
  } finally {
    loading.value = false
    scrollToBottom()
  }
}

function scrollToBottom() {
  nextTick(() => {
    if (chatBody.value) {
      chatBody.value.scrollTop = chatBody.value.scrollHeight
    }
  })
}

function onKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    send()
  }
}

function createTicket(data?: TicketData | null) {
  isOpen.value = false
  if (data) {
    const params = new URLSearchParams()
    if (data.title) params.set('title', data.title)
    if (data.description) params.set('description', data.description)
    if (data.product) params.set('product', data.product)
    if (data.category) params.set('category', data.category)
    if (data.ticket_type) params.set('ticket_type', data.ticket_type)
    router.push(`/tickets/create?${params.toString()}`)
  } else {
    router.push('/tickets/create')
  }
}

function formatSourceName(src: string): string {
  return src.replace(/\.md$/, '').split('/').pop() || src
}
</script>

<template>
  <!-- FAB button -->
  <button
    class="chat-fab"
    :class="{ open: isOpen }"
    @click="toggle"
    :aria-label="isOpen ? 'Закрыть чат' : 'AI-помощник'"
  >
    <i :class="isOpen ? 'pi pi-times' : 'pi pi-comment'" />
  </button>

  <!-- Chat panel -->
  <Transition name="chat-slide">
    <div v-if="isOpen" class="chat-panel">
      <!-- Header -->
      <div class="chat-header">
        <div class="chat-header-info">
          <div class="chat-avatar">AI</div>
          <div>
            <div class="chat-header-title">AI-помощник PASS24</div>
            <div class="chat-header-status">Онлайн</div>
          </div>
        </div>
        <button class="chat-close" @click="toggle"><i class="pi pi-minus" /></button>
      </div>

      <!-- Messages -->
      <div ref="chatBody" class="chat-body">
        <div
          v-for="(msg, i) in messages"
          :key="i"
          class="chat-message"
          :class="msg.role"
        >
          <div class="msg-bubble">
            <div class="msg-text" v-html="msg.content.replace(/\n/g, '<br>')"></div>
            <div v-if="msg.sources?.length" class="msg-sources">
              <span class="sources-label">Источники:</span>
              <span v-for="s in msg.sources" :key="s" class="source-tag">{{ formatSourceName(s) }}</span>
            </div>
            <Button
              v-if="msg.suggestTicket"
              label="Создать заявку"
              icon="pi pi-plus"
              size="small"
              class="msg-ticket-btn"
              @click="createTicket(msg.ticketData)"
            />
          </div>
        </div>

        <div v-if="loading" class="chat-message assistant">
          <div class="msg-bubble typing">
            <span class="dot" /><span class="dot" /><span class="dot" />
          </div>
        </div>
      </div>

      <!-- Input -->
      <div class="chat-input">
        <Textarea
          v-model="input"
          placeholder="Задайте вопрос..."
          auto-resize
          :rows="1"
          class="chat-textarea"
          @keydown="onKeydown"
        />
        <Button
          icon="pi pi-send"
          rounded
          :disabled="!input.trim() || loading"
          @click="send"
          class="chat-send"
        />
      </div>
    </div>
  </Transition>
</template>

<style scoped>
/* FAB */
.chat-fab {
  position: fixed;
  bottom: 24px;
  right: 24px;
  width: 56px;
  height: 56px;
  border-radius: 50%;
  background: linear-gradient(135deg, #3b82f6, #1d4ed8);
  color: white;
  border: none;
  cursor: pointer;
  box-shadow: 0 4px 16px rgba(59, 130, 246, 0.4);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 22px;
  transition: all 0.2s;
  z-index: 1000;
}

.chat-fab:hover {
  transform: scale(1.08);
  box-shadow: 0 6px 24px rgba(59, 130, 246, 0.5);
}

.chat-fab.open {
  background: #64748b;
  box-shadow: 0 4px 12px rgba(100, 116, 139, 0.3);
}

/* Panel */
.chat-panel {
  position: fixed;
  bottom: 92px;
  right: 24px;
  width: 400px;
  max-height: 600px;
  background: white;
  border-radius: 16px;
  box-shadow: 0 8px 40px rgba(0, 0, 0, 0.15);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  z-index: 999;
}

/* Slide animation */
.chat-slide-enter-active,
.chat-slide-leave-active {
  transition: all 0.25s ease;
}

.chat-slide-enter-from,
.chat-slide-leave-to {
  opacity: 0;
  transform: translateY(20px) scale(0.95);
}

/* Header */
.chat-header {
  padding: 14px 16px;
  background: linear-gradient(135deg, #0f172a, #1e293b);
  color: white;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.chat-header-info {
  display: flex;
  align-items: center;
  gap: 10px;
}

.chat-avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: linear-gradient(135deg, #3b82f6, #8b5cf6);
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  font-size: 13px;
}

.chat-header-title {
  font-weight: 600;
  font-size: 14px;
}

.chat-header-status {
  font-size: 12px;
  color: #86efac;
}

.chat-close {
  background: none;
  border: none;
  color: #94a3b8;
  cursor: pointer;
  padding: 4px;
  font-size: 16px;
}

.chat-close:hover { color: white; }

/* Body */
.chat-body {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  min-height: 300px;
  max-height: 420px;
}

/* Messages */
.chat-message {
  display: flex;
}

.chat-message.user {
  justify-content: flex-end;
}

.msg-bubble {
  max-width: 85%;
  padding: 10px 14px;
  border-radius: 14px;
  font-size: 14px;
  line-height: 1.5;
}

.chat-message.user .msg-bubble {
  background: #3b82f6;
  color: white;
  border-bottom-right-radius: 4px;
}

.chat-message.assistant .msg-bubble {
  background: #f1f5f9;
  color: #1e293b;
  border-bottom-left-radius: 4px;
}

.msg-text {
  word-wrap: break-word;
}

.msg-sources {
  margin-top: 8px;
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  align-items: center;
}

.sources-label {
  font-size: 11px;
  color: #94a3b8;
}

.source-tag {
  font-size: 11px;
  background: #e2e8f0;
  color: #475569;
  padding: 2px 6px;
  border-radius: 4px;
}

.msg-ticket-btn {
  margin-top: 8px;
}

/* Typing animation */
.typing {
  display: flex;
  gap: 4px;
  align-items: center;
  padding: 12px 18px;
}

.dot {
  width: 8px;
  height: 8px;
  background: #94a3b8;
  border-radius: 50%;
  animation: bounce 1.4s infinite ease-in-out;
}

.dot:nth-child(1) { animation-delay: 0s; }
.dot:nth-child(2) { animation-delay: 0.16s; }
.dot:nth-child(3) { animation-delay: 0.32s; }

@keyframes bounce {
  0%, 80%, 100% { transform: scale(0.6); opacity: 0.4; }
  40% { transform: scale(1); opacity: 1; }
}

/* Input */
.chat-input {
  padding: 12px;
  border-top: 1px solid #f1f5f9;
  display: flex;
  gap: 8px;
  align-items: flex-end;
}

.chat-textarea {
  flex: 1;
}

.chat-textarea :deep(textarea) {
  border-radius: 12px;
  padding: 10px 14px;
  font-size: 14px;
  max-height: 100px;
  resize: none;
}

.chat-send {
  flex-shrink: 0;
}

/* Mobile */
@media (max-width: 480px) {
  .chat-panel {
    width: calc(100vw - 16px);
    right: 8px;
    bottom: 84px;
    max-height: calc(100vh - 120px);
  }

  .chat-fab {
    bottom: 16px;
    right: 16px;
  }
}
</style>

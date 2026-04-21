<script setup lang="ts">
/**
 * Embed-страница AI-чата PASS24 для iframe-виджета на сторонних сайтах.
 *
 * Доступна по адресу: https://support.pass24pro.ru/chat-widget
 *
 * Всегда работает в guest-режиме (без авторизации): использует
 * POST /assistant/chat и POST /tickets/guest для создания заявок.
 *
 * Дизайн: тёмная шапка с AI-аватаром, лента сообщений с серыми/синими
 * пузырями, круглая зелёная кнопка отправки. Управление свёртыванием —
 * у внешнего chat-loader.js (postMessage), страница только рисует
 * содержимое попапа.
 */
import { ref, nextTick, onMounted, computed } from 'vue'
import { api } from '../api/client'

interface TicketData {
  title: string
  description: string
  product: string
  category: string
}

interface ChatResponse {
  reply: string
  sources: string[]
  suggest_ticket: boolean
  ticket_data: TicketData | null
}

interface GuestTicketResponse {
  ticket_id: string
}

type Role = 'user' | 'assistant' | 'system'
interface Message {
  role: Role
  content: string
  suggestTicket?: boolean
  ticketData?: TicketData | null
}

const input = ref('')
const messages = ref<Message[]>([
  {
    role: 'assistant',
    content: 'Здравствуйте! Я AI-помощник PASS24. Задайте вопрос о пропусках, приложении, шлагбаумах или доступе — постараюсь помочь.',
  },
])
const loading = ref(false)
const chatBody = ref<HTMLElement | null>(null)
const inputEl = ref<HTMLInputElement | null>(null)

// Форма создания заявки (если AI предложит)
const showTicketForm = ref(false)
const ticketFormData = ref<TicketData | null>(null)
const ticketEmail = ref('')
const ticketName = ref('')
const ticketPhone = ref('')
const submittingTicket = ref(false)

const userMessageCount = computed(() => messages.value.filter(m => m.role === 'user').length)

function scrollToBottom() {
  nextTick(() => {
    if (chatBody.value) chatBody.value.scrollTop = chatBody.value.scrollHeight
  })
}

async function send() {
  const text = input.value.trim()
  if (!text || loading.value) return

  messages.value.push({ role: 'user', content: text })
  input.value = ''
  loading.value = true
  scrollToBottom()

  try {
    const history = messages.value
      .filter(m => m.role !== 'system')
      .slice(0, -1)
      .map(m => ({ role: m.role, content: m.content }))

    const resp = await api.post<ChatResponse>('/assistant/chat', { message: text, history })
    const shouldSuggest = resp.suggest_ticket || userMessageCount.value >= 4

    messages.value.push({
      role: 'assistant',
      content: resp.reply,
      suggestTicket: shouldSuggest,
      ticketData: resp.ticket_data,
    })
  } catch {
    messages.value.push({
      role: 'assistant',
      content: 'Извините, произошла ошибка. Попробуйте позже или оставьте заявку.',
      suggestTicket: true,
    })
  } finally {
    loading.value = false
    scrollToBottom()
    nextTick(() => inputEl.value?.focus())
  }
}

function openTicketForm(data?: TicketData | null) {
  const lastUser = messages.value.filter(m => m.role === 'user').pop()?.content || ''
  const description = messages.value.filter(m => m.role === 'user').map(m => m.content).join('\n')
  ticketFormData.value = data || {
    title: lastUser.slice(0, 200) || 'Вопрос в AI-чате',
    description: description || lastUser,
    product: 'pass24_online',
    category: 'other',
  }
  showTicketForm.value = true
  scrollToBottom()
}

async function submitTicket() {
  const email = ticketEmail.value.trim()
  if (!email || !ticketFormData.value) return
  submittingTicket.value = true
  try {
    const resp = await api.post<GuestTicketResponse>('/tickets/guest', {
      email,
      name: ticketName.value.trim() || undefined,
      title: ticketFormData.value.title,
      description: ticketFormData.value.description,
      product: ticketFormData.value.product,
      category: ticketFormData.value.category,
      ticket_type: 'problem',
      contact_phone: ticketPhone.value.trim() || undefined,
    })
    showTicketForm.value = false
    messages.value.push({
      role: 'system',
      content: `Заявка создана — номер ${resp.ticket_id.slice(0, 8).toUpperCase()}. Обновления придут на ${email}. Можно отвечать прямо на письма — ответ попадёт в заявку.`,
    })
  } catch (e: any) {
    messages.value.push({
      role: 'system',
      content: `Не удалось создать заявку: ${e?.message || 'неизвестная ошибка'}`,
    })
  } finally {
    submittingTicket.value = false
    scrollToBottom()
  }
}

function onKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    send()
  }
}

// Попросить loader (родительское окно) свернуть виджет
function requestCollapse() {
  if (window.parent !== window) {
    window.parent.postMessage({ type: 'pass24-chat:collapse' }, '*')
  }
}

onMounted(() => {
  nextTick(() => inputEl.value?.focus())
})
</script>

<template>
  <div class="widget-root">
    <div class="widget-card">
      <!-- Header -->
      <header class="widget-header">
        <div class="avatar">AI</div>
        <div class="title-block">
          <div class="title">AI-помощник PASS24</div>
          <div class="subtitle">
            <span class="dot" />
            Онлайн
          </div>
        </div>
        <button
          class="collapse-btn"
          aria-label="Свернуть"
          title="Свернуть"
          @click="requestCollapse"
        >
          <svg width="16" height="2" viewBox="0 0 16 2" fill="none" xmlns="http://www.w3.org/2000/svg">
            <rect width="16" height="2" rx="1" fill="currentColor" />
          </svg>
        </button>
      </header>

      <!-- Messages -->
      <div ref="chatBody" class="widget-body">
        <div
          v-for="(msg, idx) in messages"
          :key="idx"
          :class="['bubble-row', `bubble-row--${msg.role}`]"
        >
          <div :class="['bubble', `bubble--${msg.role}`]">
            <div class="bubble-text">{{ msg.content }}</div>
            <button
              v-if="msg.suggestTicket && !showTicketForm"
              class="ticket-cta"
              @click="openTicketForm(msg.ticketData)"
            >
              Создать заявку в поддержку
            </button>
          </div>
        </div>

        <div v-if="loading" class="typing">
          <span /><span /><span />
        </div>

        <!-- Inline guest-форма создания заявки -->
        <div v-if="showTicketForm" class="ticket-form">
          <div class="form-title">Оставьте email — мы пришлём ответ и номер заявки</div>
          <input v-model="ticketEmail" type="email" placeholder="Ваш email" class="form-input" />
          <input v-model="ticketName" type="text" placeholder="Имя (необязательно)" class="form-input" />
          <input v-model="ticketPhone" type="tel" placeholder="Телефон (необязательно)" class="form-input" />
          <div class="form-actions">
            <button class="btn-ghost" @click="showTicketForm = false">Отмена</button>
            <button
              class="btn-primary"
              :disabled="!ticketEmail.trim() || submittingTicket"
              @click="submitTicket"
            >
              {{ submittingTicket ? 'Отправляем…' : 'Отправить' }}
            </button>
          </div>
        </div>
      </div>

      <!-- Composer -->
      <footer class="widget-footer">
        <input
          ref="inputEl"
          v-model="input"
          type="text"
          class="composer-input"
          placeholder="Задайте вопрос..."
          :disabled="loading"
          @keydown="onKeydown"
        />
        <button
          class="send-btn"
          aria-label="Отправить"
          :disabled="!input.trim() || loading"
          @click="send"
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M3 20V4l18 8-18 8zm2-2.95L16.38 12 5 7v3.5L11 12l-6 1.5v3.55z" fill="currentColor" />
          </svg>
        </button>
      </footer>
    </div>
  </div>
</template>

<style scoped>
/* Контейнер: прозрачный фон, страница полностью отдана виджету */
.widget-root {
  width: 100%;
  height: 100vh;
  padding: 8px;
  box-sizing: border-box;
  background: transparent;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
  color: #1e293b;
}

.widget-card {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  background: #fff;
  border-radius: 20px;
  overflow: hidden;
  box-shadow: 0 24px 48px -12px rgba(15, 23, 42, 0.25);
}

/* Header */
.widget-header {
  background: #0f172a;
  color: #fff;
  padding: 14px 16px;
  display: flex;
  align-items: center;
  gap: 12px;
}

.avatar {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: linear-gradient(135deg, #8b5cf6 0%, #6366f1 100%);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  font-size: 14px;
  letter-spacing: 0.5px;
  flex-shrink: 0;
}

.title-block {
  flex: 1;
  min-width: 0;
}

.title {
  font-weight: 600;
  font-size: 15px;
  line-height: 1.2;
}

.subtitle {
  font-size: 12px;
  color: #10b981;
  margin-top: 2px;
  display: flex;
  align-items: center;
  gap: 5px;
}

.dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #10b981;
}

.collapse-btn {
  background: transparent;
  border: 0;
  color: #fff;
  cursor: pointer;
  padding: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  opacity: 0.85;
  transition: opacity 0.15s;
}
.collapse-btn:hover { opacity: 1; }

/* Messages */
.widget-body {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  background: #fff;
}

.bubble-row { display: flex; }
.bubble-row--user { justify-content: flex-end; }
.bubble-row--assistant,
.bubble-row--system { justify-content: flex-start; }

.bubble {
  max-width: 86%;
  padding: 11px 14px;
  border-radius: 14px;
  font-size: 14px;
  line-height: 1.45;
  word-wrap: break-word;
}

.bubble--assistant {
  background: #f1f5f9;
  color: #1e293b;
  border-bottom-left-radius: 4px;
}

.bubble--user {
  background: #0f172a;
  color: #fff;
  border-bottom-right-radius: 4px;
}

.bubble--system {
  background: #ecfdf5;
  color: #065f46;
  border: 1px solid #a7f3d0;
  font-size: 13px;
}

.bubble-text { white-space: pre-wrap; }

.ticket-cta {
  margin-top: 8px;
  display: inline-block;
  background: #10b981;
  color: #fff;
  border: 0;
  padding: 7px 12px;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
}
.ticket-cta:hover { background: #059669; }

/* Typing indicator */
.typing {
  display: inline-flex;
  gap: 4px;
  padding: 10px 14px;
  background: #f1f5f9;
  border-radius: 14px;
  align-self: flex-start;
  border-bottom-left-radius: 4px;
}
.typing span {
  width: 6px;
  height: 6px;
  background: #94a3b8;
  border-radius: 50%;
  animation: bounce 1.2s infinite;
}
.typing span:nth-child(2) { animation-delay: 0.15s; }
.typing span:nth-child(3) { animation-delay: 0.3s; }

@keyframes bounce {
  0%, 60%, 100% { transform: translateY(0); opacity: 0.5; }
  30% { transform: translateY(-4px); opacity: 1; }
}

/* Ticket form */
.ticket-form {
  padding: 12px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.form-title {
  font-size: 13px;
  color: #475569;
  margin-bottom: 2px;
}

.form-input {
  border: 1px solid #cbd5e1;
  border-radius: 8px;
  padding: 8px 12px;
  font-size: 14px;
  outline: none;
  font-family: inherit;
}
.form-input:focus { border-color: #6366f1; }

.form-actions {
  display: flex;
  gap: 8px;
  justify-content: flex-end;
  margin-top: 4px;
}

.btn-ghost,
.btn-primary {
  padding: 8px 14px;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  border: 0;
}

.btn-ghost {
  background: transparent;
  color: #475569;
}

.btn-primary {
  background: #10b981;
  color: #fff;
}
.btn-primary:disabled {
  background: #cbd5e1;
  cursor: not-allowed;
}

/* Footer (composer) */
.widget-footer {
  padding: 12px 16px;
  background: #fff;
  display: flex;
  align-items: center;
  gap: 10px;
  border-top: 1px solid #f1f5f9;
}

.composer-input {
  flex: 1;
  min-width: 0;
  border: 1px solid #cbd5e1;
  border-radius: 999px;
  padding: 11px 18px;
  font-size: 14px;
  outline: none;
  background: #fff;
  font-family: inherit;
  color: #1e293b;
}
.composer-input::placeholder { color: #94a3b8; }
.composer-input:focus { border-color: #6366f1; }
.composer-input:disabled { background: #f8fafc; }

.send-btn {
  flex-shrink: 0;
  width: 44px;
  height: 44px;
  border-radius: 50%;
  background: #10b981;
  color: #fff;
  border: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: background 0.15s;
}
.send-btn:hover:not(:disabled) { background: #059669; }
.send-btn:disabled {
  background: #cbd5e1;
  cursor: not-allowed;
}
</style>

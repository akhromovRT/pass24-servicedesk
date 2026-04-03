<script setup lang="ts">
import { ref, nextTick, computed } from 'vue'
import { useRouter } from 'vue-router'
import Button from 'primevue/button'
import Textarea from 'primevue/textarea'
import InputText from 'primevue/inputtext'
import { api, isAuthenticated } from '../api/client'

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

interface GuestTicketResponse {
  ticket_id: string
  title: string
  status: string
  auth_required: boolean
}

interface Message {
  role: 'user' | 'assistant' | 'system'
  content: string
  sources?: string[]
  suggestTicket?: boolean
  ticketData?: TicketData | null
}

const router = useRouter()
const isOpen = ref(false)
const input = ref('')
const messages = ref<Message[]>([])
const loading = ref(false)
const chatBody = ref<HTMLElement | null>(null)

// Счётчик сообщений пользователя
const userMessageCount = computed(() =>
  messages.value.filter(m => m.role === 'user').length
)

// Inline ticket form
const showTicketForm = ref(false)
const ticketFormData = ref<TicketData | null>(null)
const ticketEmail = ref('')
const ticketName = ref('')
const ticketPhone = ref('')
const submittingTicket = ref(false)
const ticketSuccess = ref(false)

function toggle() {
  isOpen.value = !isOpen.value
  if (isOpen.value && messages.value.length === 0) {
    messages.value.push({
      role: 'assistant',
      content: 'Здравствуйте! Я AI-помощник PASS24. Задайте вопрос о пропусках, приложении, шлагбаумах или доступе — постараюсь помочь.',
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
    const history = messages.value
      .filter(m => m.role !== 'system')
      .slice(0, -1)
      .map(m => ({ role: m.role, content: m.content }))

    const resp = await api.post<ChatResponse>('/assistant/chat', {
      message: text,
      history,
    })

    const shouldSuggest = resp.suggest_ticket || userMessageCount.value >= 4

    messages.value.push({
      role: 'assistant',
      content: resp.reply,
      sources: resp.sources,
      suggestTicket: shouldSuggest,
      ticketData: resp.ticket_data,
    })

    // Авто-предложение после 4 сообщений
    if (userMessageCount.value === 4 && !resp.suggest_ticket) {
      messages.value.push({
        role: 'system',
        content: 'Если проблема не решена — я могу создать заявку в техподдержку. Это быстро — достаточно указать email.',
        suggestTicket: true,
        ticketData: resp.ticket_data || {
          title: text,
          description: messages.value
            .filter(m => m.role === 'user')
            .map(m => m.content)
            .join('\n'),
          product: 'pass24_online',
          category: 'other',
        },
      })
    }
  } catch {
    messages.value.push({
      role: 'assistant',
      content: 'Извините, произошла ошибка. Попробуйте позже или оставьте заявку.',
      suggestTicket: true,
    })
  } finally {
    loading.value = false
    scrollToBottom()
  }
}

function openTicketForm(data?: TicketData | null) {
  if (isAuthenticated()) {
    // Авторизован — переход на полную форму
    isOpen.value = false
    const params = new URLSearchParams()
    if (data?.title) params.set('title', data.title)
    if (data?.description) params.set('description', data.description)
    if (data?.product) params.set('product', data.product)
    if (data?.category) params.set('category', data.category)
    router.push(`/tickets/create?${params.toString()}`)
    return
  }

  // Не авторизован — показать inline форму
  ticketFormData.value = data || {
    title: messages.value.filter(m => m.role === 'user').pop()?.content || '',
    description: messages.value.filter(m => m.role === 'user').map(m => m.content).join('\n'),
    product: 'pass24_online',
    category: 'other',
  }
  showTicketForm.value = true
  ticketSuccess.value = false
  scrollToBottom()
}

async function submitGuestTicket() {
  if (!ticketEmail.value.trim() || !ticketFormData.value) return
  submittingTicket.value = true

  try {
    const resp = await api.post<GuestTicketResponse>('/tickets/guest', {
      email: ticketEmail.value.trim(),
      name: ticketName.value.trim() || undefined,
      title: ticketFormData.value.title,
      description: ticketFormData.value.description,
      product: ticketFormData.value.product,
      category: ticketFormData.value.category,
      ticket_type: ticketFormData.value.ticket_type || 'problem',
      contact_phone: ticketPhone.value.trim() || undefined,
    })

    ticketSuccess.value = true
    showTicketForm.value = false
    messages.value.push({
      role: 'system',
      content: `Заявка создана! Номер: ${resp.ticket_id.slice(0, 8)}. Все обновления придут на ${ticketEmail.value}. Вы можете отвечать на письма — ответы будут добавлены в заявку.`,
    })
  } catch (e: any) {
    messages.value.push({
      role: 'system',
      content: `Ошибка: ${e.message || 'Не удалось создать заявку'}`,
    })
  } finally {
    submittingTicket.value = false
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
          <div class="msg-bubble" :class="{ 'system-bubble': msg.role === 'system' }">
            <div class="msg-text" v-html="msg.content.replace(/\n/g, '<br>')"></div>
            <div v-if="msg.sources?.length" class="msg-sources">
              <span class="sources-label">Источники:</span>
              <span v-for="s in msg.sources" :key="s" class="source-tag">{{ formatSourceName(s) }}</span>
            </div>
            <Button
              v-if="msg.suggestTicket && !ticketSuccess"
              label="Создать заявку"
              icon="pi pi-plus"
              size="small"
              class="msg-ticket-btn"
              @click="openTicketForm(msg.ticketData)"
            />
          </div>
        </div>

        <!-- Inline ticket form -->
        <div v-if="showTicketForm && !ticketSuccess" class="ticket-form-inline">
          <div class="ticket-form-card">
            <h4>Оставить заявку</h4>
            <p class="ticket-form-hint">Укажите email — мы сообщим о решении</p>
            <div class="form-fields">
              <InputText
                v-model="ticketEmail"
                placeholder="Email *"
                class="form-field"
                type="email"
              />
              <InputText
                v-model="ticketName"
                placeholder="Ваше имя"
                class="form-field"
              />
              <InputText
                v-model="ticketPhone"
                placeholder="Телефон"
                class="form-field"
              />
              <Textarea
                v-model="ticketFormData!.title"
                placeholder="Тема заявки *"
                :rows="1"
                auto-resize
                class="form-field"
              />
              <Textarea
                v-model="ticketFormData!.description"
                placeholder="Описание проблемы"
                :rows="2"
                auto-resize
                class="form-field"
              />
            </div>
            <div class="form-actions">
              <Button
                label="Отправить"
                icon="pi pi-send"
                size="small"
                :loading="submittingTicket"
                :disabled="!ticketEmail.trim() || !ticketFormData?.title?.trim()"
                @click="submitGuestTicket"
              />
              <Button
                label="Отмена"
                severity="secondary"
                text
                size="small"
                @click="showTicketForm = false"
              />
            </div>
          </div>
        </div>

        <!-- Typing -->
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
.chat-fab:hover { transform: scale(1.08); box-shadow: 0 6px 24px rgba(59, 130, 246, 0.5); }
.chat-fab.open { background: #64748b; box-shadow: 0 4px 12px rgba(100, 116, 139, 0.3); }

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

.chat-slide-enter-active, .chat-slide-leave-active { transition: all 0.25s ease; }
.chat-slide-enter-from, .chat-slide-leave-to { opacity: 0; transform: translateY(20px) scale(0.95); }

.chat-header {
  padding: 14px 16px;
  background: linear-gradient(135deg, #0f172a, #1e293b);
  color: white;
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.chat-header-info { display: flex; align-items: center; gap: 10px; }
.chat-avatar {
  width: 36px; height: 36px; border-radius: 50%;
  background: linear-gradient(135deg, #3b82f6, #8b5cf6);
  display: flex; align-items: center; justify-content: center;
  font-weight: 700; font-size: 13px;
}
.chat-header-title { font-weight: 600; font-size: 14px; }
.chat-header-status { font-size: 12px; color: #86efac; }
.chat-close { background: none; border: none; color: #94a3b8; cursor: pointer; padding: 4px; font-size: 16px; }
.chat-close:hover { color: white; }

.chat-body {
  flex: 1; overflow-y: auto; padding: 16px;
  display: flex; flex-direction: column; gap: 10px;
  min-height: 300px; max-height: 420px;
}

.chat-message { display: flex; }
.chat-message.user { justify-content: flex-end; }
.chat-message.system { justify-content: center; }

.msg-bubble {
  max-width: 85%; padding: 10px 14px; border-radius: 14px;
  font-size: 14px; line-height: 1.5;
}
.chat-message.user .msg-bubble { background: #3b82f6; color: white; border-bottom-right-radius: 4px; }
.chat-message.assistant .msg-bubble { background: #f1f5f9; color: #1e293b; border-bottom-left-radius: 4px; }
.system-bubble {
  background: #eff6ff !important; color: #1e40af !important;
  border: 1px solid #bfdbfe; max-width: 95%; text-align: center;
}

.msg-text { word-wrap: break-word; }
.msg-sources { margin-top: 8px; display: flex; flex-wrap: wrap; gap: 4px; align-items: center; }
.sources-label { font-size: 11px; color: #94a3b8; }
.source-tag { font-size: 11px; background: #e2e8f0; color: #475569; padding: 2px 6px; border-radius: 4px; }
.msg-ticket-btn { margin-top: 8px; }

/* Inline ticket form */
.ticket-form-inline { width: 100%; }
.ticket-form-card {
  background: white; border: 2px solid #3b82f6; border-radius: 12px;
  padding: 14px; animation: formAppear 0.3s ease;
}
@keyframes formAppear { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }

.ticket-form-card h4 { margin: 0 0 4px; font-size: 15px; color: #1e293b; }
.ticket-form-hint { font-size: 12px; color: #64748b; margin: 0 0 12px; }
.form-fields { display: flex; flex-direction: column; gap: 8px; }
.form-field { width: 100%; font-size: 13px; }
.form-field :deep(input), .form-field :deep(textarea) { font-size: 13px; padding: 8px 10px; }
.form-actions { display: flex; gap: 8px; margin-top: 10px; }

/* Typing */
.typing { display: flex; gap: 4px; align-items: center; padding: 12px 18px; }
.dot { width: 8px; height: 8px; background: #94a3b8; border-radius: 50%; animation: bounce 1.4s infinite ease-in-out; }
.dot:nth-child(1) { animation-delay: 0s; }
.dot:nth-child(2) { animation-delay: 0.16s; }
.dot:nth-child(3) { animation-delay: 0.32s; }
@keyframes bounce { 0%, 80%, 100% { transform: scale(0.6); opacity: 0.4; } 40% { transform: scale(1); opacity: 1; } }

.chat-input { padding: 12px; border-top: 1px solid #f1f5f9; display: flex; gap: 8px; align-items: flex-end; }
.chat-textarea { flex: 1; }
.chat-textarea :deep(textarea) { border-radius: 12px; padding: 10px 14px; font-size: 14px; max-height: 100px; resize: none; }
.chat-send { flex-shrink: 0; }

@media (max-width: 480px) {
  .chat-panel { width: calc(100vw - 16px); right: 8px; bottom: 84px; max-height: calc(100vh - 120px); }
  .chat-fab { bottom: 16px; right: 16px; }
}
</style>

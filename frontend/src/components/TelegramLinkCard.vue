<script setup lang="ts">
import { ref, computed, onUnmounted, watch } from 'vue'
import QRCode from 'qrcode'
import Card from 'primevue/card'
import Button from 'primevue/button'
import Tag from 'primevue/tag'
import { useToast } from 'primevue/usetoast'
import { useConfirm } from 'primevue/useconfirm'

import { useAuthStore } from '../stores/auth'
import {
  generateTelegramLinkToken,
  unlinkTelegram,
  type TelegramLinkToken,
} from '../api/telegramLink'

const auth = useAuthStore()
const toast = useToast()
const confirm = useConfirm()

const isLinked = computed(() => !!auth.user?.telegram_chat_id)

const generating = ref(false)
const unlinking = ref(false)
const token = ref<TelegramLinkToken | null>(null)
const qrDataUrl = ref<string>('')
const now = ref(Date.now())

let clockTimer: number | null = null
let pollTimer: number | null = null

const expiresAtMs = computed(() => (token.value ? Date.parse(token.value.expires_at) : 0))
const secondsLeft = computed(() =>
  token.value ? Math.max(0, Math.floor((expiresAtMs.value - now.value) / 1000)) : 0,
)
const timerLabel = computed(() => {
  const s = secondsLeft.value
  const mm = String(Math.floor(s / 60)).padStart(2, '0')
  const ss = String(s % 60).padStart(2, '0')
  return `${mm}:${ss}`
})

function startPolling() {
  stopPolling()
  clockTimer = window.setInterval(() => {
    now.value = Date.now()
    if (secondsLeft.value <= 0 && token.value) {
      // Token expired — give up
      token.value = null
      qrDataUrl.value = ''
      stopPolling()
    }
  }, 1000)
  pollTimer = window.setInterval(async () => {
    try {
      await auth.fetchUser()
      if (isLinked.value) {
        token.value = null
        qrDataUrl.value = ''
        stopPolling()
        toast.add({ severity: 'success', summary: 'Telegram привязан', life: 2500 })
      }
    } catch {
      // Silent — network hiccups are fine, retry on next tick
    }
  }, 3000)
}

function stopPolling() {
  if (clockTimer !== null) {
    window.clearInterval(clockTimer)
    clockTimer = null
  }
  if (pollTimer !== null) {
    window.clearInterval(pollTimer)
    pollTimer = null
  }
}

async function handleGenerate() {
  generating.value = true
  try {
    token.value = await generateTelegramLinkToken()
    qrDataUrl.value = await QRCode.toDataURL(token.value.deeplink, {
      errorCorrectionLevel: 'M',
      margin: 1,
      scale: 6,
    })
    now.value = Date.now()
    startPolling()
  } catch (e: any) {
    const msg = e?.message || 'Не удалось сгенерировать ссылку'
    toast.add({ severity: 'error', summary: 'Ошибка', detail: msg, life: 4000 })
  } finally {
    generating.value = false
  }
}

function cancelToken() {
  token.value = null
  qrDataUrl.value = ''
  stopPolling()
}

function confirmUnlink() {
  confirm.require({
    header: 'Отвязать Telegram?',
    message:
      'Бот перестанет присылать уведомления по заявкам. Привязать можно будет снова в любой момент.',
    acceptLabel: 'Отвязать',
    rejectLabel: 'Отмена',
    acceptClass: 'p-button-danger',
    icon: 'pi pi-exclamation-triangle',
    accept: async () => {
      unlinking.value = true
      try {
        await unlinkTelegram()
        await auth.fetchUser()
        toast.add({ severity: 'success', summary: 'Отвязано', life: 2500 })
      } catch (e: any) {
        toast.add({
          severity: 'error',
          summary: 'Ошибка',
          detail: e?.message || 'Не удалось отвязать',
          life: 4000,
        })
      } finally {
        unlinking.value = false
      }
    },
  })
}

const linkedDateLabel = computed(() => {
  const iso = auth.user?.telegram_linked_at
  if (!iso) return ''
  try {
    return new Intl.DateTimeFormat('ru-RU', { dateStyle: 'medium' }).format(new Date(iso))
  } catch {
    return ''
  }
})

watch(isLinked, (linked) => {
  if (linked) {
    cancelToken()
  }
})

onUnmounted(() => stopPolling())
</script>

<template>
  <Card class="tg-link-card">
    <template #title>
      <div class="title-row">
        <i class="pi pi-user" />
        <span>Мой Telegram</span>
      </div>
    </template>
    <template #content>
      <!-- State: linked -->
      <div v-if="isLinked" class="linked-state">
        <Tag severity="success" value="Подключён" />
        <div class="linked-hint" v-if="linkedDateLabel">
          Привязан с {{ linkedDateLabel }}
        </div>
        <div class="linked-actions">
          <a href="https://t.me/PASS24bot" target="_blank" rel="noopener">
            <Button label="Открыть бота" icon="pi pi-external-link" severity="secondary" />
          </a>
          <Button
            label="Отвязать"
            icon="pi pi-times"
            severity="danger"
            outlined
            :loading="unlinking"
            @click="confirmUnlink"
          />
        </div>
      </div>

      <!-- State: token active (generated but not yet linked) -->
      <div v-else-if="token" class="token-state">
        <p class="intro">
          Отсканируйте QR-код телефоном <strong>или</strong> нажмите кнопку ниже — в Telegram
          откроется бот, привязка произойдёт автоматически.
        </p>
        <div class="qr-row">
          <img :src="qrDataUrl" alt="QR-код привязки" class="qr-img" />
          <div class="token-info">
            <div class="timer">
              <i class="pi pi-clock" />
              <span>Действует ещё <b>{{ timerLabel }}</b></span>
            </div>
            <a :href="token.deeplink" target="_blank" rel="noopener">
              <Button label="Открыть в Telegram" icon="pi pi-send" />
            </a>
            <Button
              label="Отменить"
              icon="pi pi-times"
              severity="secondary"
              text
              @click="cancelToken"
            />
          </div>
        </div>
      </div>

      <!-- State: not linked, idle -->
      <div v-else class="idle-state">
        <p class="intro">
          Привяжите Telegram, чтобы получать уведомления по заявкам и создавать их прямо из
          мессенджера.
        </p>
        <Button
          label="Привязать Telegram"
          icon="pi pi-send"
          :loading="generating"
          @click="handleGenerate"
        />
      </div>
    </template>
  </Card>
</template>

<style scoped>
.tg-link-card { margin-bottom: 16px; }
.title-row { display: flex; align-items: center; gap: 10px; font-size: 16px; font-weight: 700; }
.title-row i { color: #0ea5e9; }

.linked-state, .token-state, .idle-state { display: flex; flex-direction: column; gap: 12px; }

.linked-hint { font-size: 13px; color: #64748b; }
.linked-actions { display: flex; gap: 10px; flex-wrap: wrap; }

.intro { font-size: 14px; color: #475569; margin: 0; line-height: 1.5; }

.qr-row { display: flex; gap: 24px; align-items: center; flex-wrap: wrap; }
.qr-img { width: 180px; height: 180px; border: 1px solid #e2e8f0; border-radius: 8px; background: white; }
.token-info { display: flex; flex-direction: column; gap: 10px; align-items: flex-start; }
.timer {
  display: flex; align-items: center; gap: 6px;
  font-size: 13px; color: #64748b;
}
.timer i { color: #f59e0b; }
.timer b { color: #0f172a; font-variant-numeric: tabular-nums; }

@media (max-width: 520px) {
  .qr-row { flex-direction: column; align-items: stretch; }
  .qr-img { width: 100%; max-width: 220px; margin: 0 auto; }
}
</style>

<script setup lang="ts">
import { ref, computed, onBeforeUnmount } from 'vue'
import Textarea from 'primevue/textarea'
import Button from 'primevue/button'
import Checkbox from 'primevue/checkbox'
import { useTicketsStore } from '../../stores/tickets'
import { useToast } from 'primevue/usetoast'

const props = defineProps<{
  ticketId: string
  isStaff: boolean
}>()

const emit = defineEmits<{
  submitted: []
  fileUploaded: []
}>()

const store = useTicketsStore()
const toast = useToast()

const commentText = ref('')
const isInternal = ref(false)
const submitting = ref(false)
const fileInput = ref<HTMLInputElement | null>(null)

interface PendingAttachment {
  id: string
  filename: string
  content_type: string
  size: number
  preview_url?: string
}
const pendingAttachments = ref<PendingAttachment[]>([])

const canSubmit = computed(
  () =>
    !submitting.value &&
    (commentText.value.trim().length > 0 || pendingAttachments.value.length > 0),
)

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} Б`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} КБ`
  return `${(bytes / 1024 / 1024).toFixed(1)} МБ`
}

function revokePreviews() {
  for (const att of pendingAttachments.value) {
    if (att.preview_url) URL.revokeObjectURL(att.preview_url)
  }
}

onBeforeUnmount(revokePreviews)

async function handleSubmit() {
  if (!canSubmit.value) return

  const text = commentText.value.trim()
  const attachmentIds = pendingAttachments.value.map((a) => a.id)

  submitting.value = true
  try {
    await store.addComment(
      props.ticketId,
      text,
      isInternal.value,
      attachmentIds.length ? attachmentIds : undefined,
    )
    revokePreviews()
    pendingAttachments.value = []
    commentText.value = ''
    isInternal.value = false
    emit('submitted')
  } catch (err: any) {
    toast.add({
      severity: 'error',
      summary: 'Ошибка',
      detail: err.message || 'Не удалось отправить комментарий',
      life: 4000,
    })
  } finally {
    submitting.value = false
  }
}

function openFilePicker() {
  fileInput.value?.click()
}

async function uploadFile(file: File): Promise<void> {
  const formData = new FormData()
  formData.append('file', file)

  const token = localStorage.getItem('access_token')
  const response = await fetch(`/tickets/${props.ticketId}/attachments`, {
    method: 'POST',
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    body: formData,
  })

  if (!response.ok) {
    const err = await response.json().catch(() => ({ detail: 'Ошибка загрузки' }))
    throw new Error(err.detail || `HTTP ${response.status}`)
  }

  const data = await response.json()
  pendingAttachments.value.push({
    id: data.id,
    filename: data.filename,
    content_type: data.content_type,
    size: data.size,
    preview_url: file.type.startsWith('image/') ? URL.createObjectURL(file) : undefined,
  })
}

async function handleFileSelect(event: Event) {
  const input = event.target as HTMLInputElement
  const files = Array.from(input.files || [])
  if (!files.length) return

  for (const file of files) {
    try {
      await uploadFile(file)
      emit('fileUploaded')
    } catch (err: any) {
      toast.add({
        severity: 'error',
        summary: `Не удалось загрузить ${file.name}`,
        detail: err.message || 'Ошибка',
        life: 4000,
      })
    }
  }

  // Сбрасываем, чтобы можно было выбрать тот же файл снова
  input.value = ''
}

async function removeAttachment(id: string) {
  const idx = pendingAttachments.value.findIndex((a) => a.id === id)
  if (idx === -1) return

  const att = pendingAttachments.value[idx]
  // Сначала локально, чтобы UI отреагировал мгновенно.
  if (att.preview_url) URL.revokeObjectURL(att.preview_url)
  pendingAttachments.value.splice(idx, 1)

  // Backend-удаление (best-effort): если не удалось — сообщаем, но к комментарию
  // attachment всё равно не привяжется, так как в submit отправляется только список текущих pending.
  try {
    const token = localStorage.getItem('access_token')
    const response = await fetch(`/tickets/${props.ticketId}/attachments/${id}`, {
      method: 'DELETE',
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
    if (!response.ok && response.status !== 404) {
      // 404 — уже удалён, не страшно
      throw new Error(`HTTP ${response.status}`)
    }
  } catch (err: any) {
    toast.add({
      severity: 'warn',
      summary: 'Файл убран из черновика',
      detail: 'Файл может остаться на сервере (orphan), будет очищен фоновой задачей.',
      life: 3500,
    })
  }
}

function handleKeydown(event: KeyboardEvent) {
  if ((event.ctrlKey || event.metaKey) && event.key === 'Enter') {
    event.preventDefault()
    handleSubmit()
  }
}
</script>

<template>
  <div class="compose-area">
    <Textarea
      v-model="commentText"
      auto-resize
      :rows="3"
      placeholder="Напишите ответ..."
      class="compose-textarea"
      @keydown="handleKeydown"
    />

    <div v-if="pendingAttachments.length" class="pending-attachments">
      <div
        v-for="att in pendingAttachments"
        :key="att.id"
        class="attachment-chip"
        :title="att.filename"
      >
        <img
          v-if="att.preview_url"
          :src="att.preview_url"
          class="att-thumb"
          :alt="att.filename"
        />
        <i v-else class="pi pi-file att-icon" />
        <div class="att-meta">
          <span class="att-name">{{ att.filename }}</span>
          <span class="att-size">{{ formatSize(att.size) }}</span>
        </div>
        <button
          class="att-remove"
          type="button"
          title="Убрать"
          @click="removeAttachment(att.id)"
        >
          <i class="pi pi-times" />
        </button>
      </div>
    </div>

    <div class="compose-actions">
      <div class="actions-left">
        <Button
          icon="pi pi-paperclip"
          severity="secondary"
          text
          size="small"
          @click="openFilePicker"
          title="Прикрепить файл (можно несколько)"
        />
        <label v-if="isStaff" class="internal-toggle">
          <Checkbox v-model="isInternal" :binary="true" />
          <i class="pi pi-lock internal-icon" />
          <span>Внутренний</span>
        </label>
      </div>

      <div class="actions-right">
        <Button
          label="Отправить"
          icon="pi pi-send"
          size="small"
          :disabled="!canSubmit"
          :loading="submitting"
          @click="handleSubmit"
        />
      </div>
    </div>

    <input
      ref="fileInput"
      type="file"
      class="hidden-file-input"
      accept="image/*,.pdf,.txt,.doc,.docx"
      multiple
      @change="handleFileSelect"
    />
  </div>
</template>

<style scoped>
.compose-area {
  position: sticky;
  bottom: 0;
  background: #ffffff;
  border-top: 1px solid #e2e8f0;
  padding: 16px;
  z-index: 10;
}

.compose-textarea {
  width: 100%;
}

.pending-attachments {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 10px;
}

.attachment-chip {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 8px 6px 6px;
  background: #f1f5f9;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  max-width: 260px;
  font-size: 12px;
  color: #334155;
}

.att-thumb {
  width: 40px;
  height: 40px;
  object-fit: cover;
  border-radius: 6px;
  background: #fff;
  flex: 0 0 auto;
}

.att-icon {
  width: 40px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #fff;
  border-radius: 6px;
  font-size: 18px;
  color: #64748b;
  flex: 0 0 auto;
}

.att-meta {
  display: flex;
  flex-direction: column;
  min-width: 0;
  flex: 1 1 auto;
}

.att-name {
  font-weight: 500;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.att-size {
  color: #64748b;
  font-size: 11px;
}

.att-remove {
  background: transparent;
  border: 0;
  cursor: pointer;
  color: #64748b;
  padding: 4px;
  border-radius: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 auto;
}

.att-remove:hover {
  background: #e2e8f0;
  color: #1e293b;
}

.compose-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 8px;
}

.actions-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.actions-right {
  display: flex;
  align-items: center;
}

.internal-toggle {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: #64748b;
  cursor: pointer;
  user-select: none;
}

.internal-icon {
  font-size: 12px;
  color: #f59e0b;
}

.hidden-file-input {
  display: none;
}
</style>

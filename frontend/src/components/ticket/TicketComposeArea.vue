<script setup lang="ts">
import { ref } from 'vue'
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

async function handleSubmit() {
  const text = commentText.value.trim()
  if (!text || submitting.value) return

  submitting.value = true
  try {
    await store.addComment(props.ticketId, text, isInternal.value)
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

async function handleFileSelect(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return

  const formData = new FormData()
  formData.append('file', file)

  try {
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

    toast.add({
      severity: 'success',
      summary: 'Файл загружен',
      detail: file.name,
      life: 3000,
    })
    emit('fileUploaded')
  } catch (err: any) {
    toast.add({
      severity: 'error',
      summary: 'Ошибка загрузки',
      detail: err.message || 'Не удалось загрузить файл',
      life: 4000,
    })
  }

  // Reset file input so the same file can be selected again
  input.value = ''
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

    <div class="compose-actions">
      <div class="actions-left">
        <Button
          icon="pi pi-paperclip"
          severity="secondary"
          text
          size="small"
          @click="openFilePicker"
          title="Прикрепить файл"
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
          :disabled="!commentText.trim() || submitting"
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

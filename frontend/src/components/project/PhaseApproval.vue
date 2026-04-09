<script setup lang="ts">
import { onMounted, ref, computed } from 'vue'
import Tag from 'primevue/tag'
import Button from 'primevue/button'
import Dialog from 'primevue/dialog'
import Textarea from 'primevue/textarea'
import { useToast } from 'primevue/usetoast'
import { api } from '../../api/client'
import type { ProjectApproval } from '../../types'

const props = defineProps<{
  projectId: string
  phaseId: string
  phaseStatus: string
  isPropertyManager: boolean
  isStaff: boolean
}>()

const toast = useToast()

const approvals = ref<ProjectApproval[]>([])
const loading = ref(false)
const submitting = ref(false)

// Reject dialog
const showRejectDialog = ref(false)
const rejectFeedback = ref('')
const rejectingApprovalId = ref<string | null>(null)

const phaseApproval = computed(() =>
  approvals.value.find(a => a.phase_id === props.phaseId) ?? null,
)

const isPending = computed(() => phaseApproval.value?.status === 'pending')
const isApproved = computed(() => phaseApproval.value?.status === 'approved')
const isRejected = computed(() => phaseApproval.value?.status === 'rejected')

async function fetchApprovals() {
  loading.value = true
  try {
    approvals.value = await api.get<ProjectApproval[]>(
      `/projects/${props.projectId}/approvals`,
    )
  } catch {
    // silent — component is non-critical
  } finally {
    loading.value = false
  }
}

async function requestApproval() {
  submitting.value = true
  try {
    await api.post(`/projects/${props.projectId}/phases/${props.phaseId}/request-approval`)
    await fetchApprovals()
    toast.add({ severity: 'success', summary: 'Запрос отправлен', life: 2000 })
  } catch (err: any) {
    toast.add({ severity: 'error', summary: 'Ошибка', detail: err.message, life: 4000 })
  } finally {
    submitting.value = false
  }
}

async function approve() {
  if (!phaseApproval.value) return
  submitting.value = true
  try {
    await api.post(`/projects/${props.projectId}/approvals/${phaseApproval.value.id}/approve`)
    await fetchApprovals()
    toast.add({ severity: 'success', summary: 'Фаза утверждена', life: 2000 })
  } catch (err: any) {
    toast.add({ severity: 'error', summary: 'Ошибка', detail: err.message, life: 4000 })
  } finally {
    submitting.value = false
  }
}

function openRejectDialog() {
  if (!phaseApproval.value) return
  rejectingApprovalId.value = phaseApproval.value.id
  rejectFeedback.value = ''
  showRejectDialog.value = true
}

async function submitReject() {
  if (!rejectingApprovalId.value) return
  submitting.value = true
  try {
    await api.post(
      `/projects/${props.projectId}/approvals/${rejectingApprovalId.value}/reject`,
      { feedback: rejectFeedback.value },
    )
    showRejectDialog.value = false
    rejectFeedback.value = ''
    rejectingApprovalId.value = null
    await fetchApprovals()
    toast.add({ severity: 'warn', summary: 'Фаза отклонена', life: 2000 })
  } catch (err: any) {
    toast.add({ severity: 'error', summary: 'Ошибка', detail: err.message, life: 4000 })
  } finally {
    submitting.value = false
  }
}

function formatDateTime(d: string): string {
  return new Date(d).toLocaleString('ru-RU', {
    day: 'numeric',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  })
}

onMounted(fetchApprovals)
</script>

<template>
  <div class="phase-approval">
    <!-- Phase completed, no approval yet — staff can request -->
    <div
      v-if="phaseStatus === 'completed' && !phaseApproval && isStaff"
      class="approval-action"
    >
      <Button
        label="Запросить утверждение"
        icon="pi pi-send"
        size="small"
        severity="info"
        :loading="submitting"
        @click="requestApproval"
      />
    </div>

    <!-- Pending approval -->
    <div v-if="isPending" class="approval-status">
      <Tag severity="warn" value="Ожидает подтверждения" icon="pi pi-clock" />
      <div v-if="isPropertyManager" class="approval-buttons">
        <Button
          label="Утвердить"
          icon="pi pi-check"
          size="small"
          severity="success"
          :loading="submitting"
          @click="approve"
        />
        <Button
          label="Отклонить"
          icon="pi pi-times"
          size="small"
          severity="danger"
          outlined
          :loading="submitting"
          @click="openRejectDialog"
        />
      </div>
      <span v-else-if="isStaff" class="approval-hint">
        Ожидает подтверждения клиента
      </span>
    </div>

    <!-- Approved -->
    <div v-if="isApproved && phaseApproval" class="approval-status">
      <Tag severity="success" value="Утверждено" icon="pi pi-check-circle" />
      <span v-if="phaseApproval.reviewed_at" class="approval-date">
        {{ formatDateTime(phaseApproval.reviewed_at) }}
      </span>
    </div>

    <!-- Rejected -->
    <div v-if="isRejected && phaseApproval" class="approval-status">
      <Tag severity="danger" value="Отклонено" icon="pi pi-times-circle" />
      <span v-if="phaseApproval.feedback" class="approval-feedback">
        {{ phaseApproval.feedback }}
      </span>
    </div>

    <!-- Reject dialog -->
    <Dialog
      v-model:visible="showRejectDialog"
      header="Отклонить фазу"
      :modal="true"
      :style="{ width: '480px' }"
    >
      <div class="reject-form">
        <label class="reject-label">Укажите причину отклонения</label>
        <Textarea
          v-model="rejectFeedback"
          placeholder="Опишите, что необходимо исправить..."
          rows="4"
          auto-resize
          class="reject-textarea"
        />
      </div>
      <template #footer>
        <Button
          label="Отмена"
          severity="secondary"
          text
          @click="showRejectDialog = false"
        />
        <Button
          label="Отклонить"
          icon="pi pi-times"
          severity="danger"
          :loading="submitting"
          :disabled="!rejectFeedback.trim()"
          @click="submitReject"
        />
      </template>
    </Dialog>
  </div>
</template>

<style scoped>
.phase-approval {
  margin-top: 8px;
}

.approval-action {
  margin-top: 4px;
}

.approval-status {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  margin-top: 4px;
}

.approval-buttons {
  display: flex;
  gap: 8px;
}

.approval-hint {
  font-size: 0.8rem;
  color: #94a3b8;
  font-style: italic;
}

.approval-date {
  font-size: 0.8rem;
  color: #64748b;
}

.approval-feedback {
  font-size: 0.85rem;
  color: #dc2626;
  background: #fef2f2;
  padding: 4px 10px;
  border-radius: 4px;
  border-left: 3px solid #ef4444;
}

.reject-form {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.reject-label {
  font-size: 0.875rem;
  color: #475569;
  font-weight: 500;
}

.reject-textarea {
  width: 100%;
}
</style>

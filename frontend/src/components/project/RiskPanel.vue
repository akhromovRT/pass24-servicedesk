<script setup lang="ts">
import { onMounted, ref } from 'vue'
import Button from 'primevue/button'
import Dialog from 'primevue/dialog'
import InputText from 'primevue/inputtext'
import Textarea from 'primevue/textarea'
import Select from 'primevue/select'
import Tag from 'primevue/tag'
import { useToast } from 'primevue/usetoast'
import { useConfirm } from 'primevue/useconfirm'
import { api } from '../../api/client'
import type { ProjectRisk, RiskSeverity, RiskProbability, RiskStatus } from '../../types'

const props = defineProps<{
  projectId: string
}>()

const toast = useToast()
const confirm = useConfirm()

const risks = ref<ProjectRisk[]>([])
const loading = ref(false)
const expandedRiskId = ref<string | null>(null)

// Dialog state
const showDialog = ref(false)
const dialogMode = ref<'create' | 'edit'>('create')
const saving = ref(false)
const editingRiskId = ref<string | null>(null)

const form = ref({
  title: '',
  description: '',
  severity: 'medium' as RiskSeverity,
  probability: 'medium' as RiskProbability,
  impact: '',
  mitigation_plan: '',
  status: 'open' as RiskStatus,
})

// Dropdown options
const severityOptions = [
  { label: 'Низкий', value: 'low' },
  { label: 'Средний', value: 'medium' },
  { label: 'Высокий', value: 'high' },
  { label: 'Критический', value: 'critical' },
]

const probabilityOptions = [
  { label: 'Низкая', value: 'low' },
  { label: 'Средняя', value: 'medium' },
  { label: 'Высокая', value: 'high' },
]

const statusOptions = [
  { label: 'Открыт', value: 'open' },
  { label: 'Снижен', value: 'mitigated' },
  { label: 'Произошёл', value: 'occurred' },
  { label: 'Закрыт', value: 'closed' },
]

const severityColors: Record<RiskSeverity, string> = {
  low: '#10b981',
  medium: '#eab308',
  high: '#f97316',
  critical: '#ef4444',
}

const severityLabels: Record<RiskSeverity, string> = {
  low: 'Низкий',
  medium: 'Средний',
  high: 'Высокий',
  critical: 'Критический',
}

const statusTagSeverity: Record<RiskStatus, 'info' | 'success' | 'danger' | 'secondary'> = {
  open: 'info',
  mitigated: 'success',
  occurred: 'danger',
  closed: 'secondary',
}

const statusLabels: Record<RiskStatus, string> = {
  open: 'Открыт',
  mitigated: 'Снижен',
  occurred: 'Произошёл',
  closed: 'Закрыт',
}

async function fetchRisks() {
  loading.value = true
  try {
    risks.value = await api.get<ProjectRisk[]>(`/projects/${props.projectId}/risks`)
  } catch (err: any) {
    toast.add({ severity: 'error', summary: 'Ошибка', detail: err.message, life: 4000 })
  } finally {
    loading.value = false
  }
}

function openCreateDialog() {
  dialogMode.value = 'create'
  editingRiskId.value = null
  form.value = {
    title: '',
    description: '',
    severity: 'medium',
    probability: 'medium',
    impact: '',
    mitigation_plan: '',
    status: 'open',
  }
  showDialog.value = true
}

function openEditDialog(risk: ProjectRisk) {
  dialogMode.value = 'edit'
  editingRiskId.value = risk.id
  form.value = {
    title: risk.title,
    description: risk.description || '',
    severity: risk.severity,
    probability: risk.probability,
    impact: risk.impact,
    mitigation_plan: risk.mitigation_plan || '',
    status: risk.status,
  }
  showDialog.value = true
}

async function saveRisk() {
  if (!form.value.title.trim() || !form.value.impact.trim()) {
    toast.add({ severity: 'warn', summary: 'Заполните обязательные поля', detail: 'Название и влияние обязательны', life: 3000 })
    return
  }

  saving.value = true
  const payload = {
    title: form.value.title,
    description: form.value.description || null,
    severity: form.value.severity,
    probability: form.value.probability,
    impact: form.value.impact,
    mitigation_plan: form.value.mitigation_plan || null,
    status: form.value.status,
  }

  try {
    if (dialogMode.value === 'create') {
      await api.post(`/projects/${props.projectId}/risks`, payload)
      toast.add({ severity: 'success', summary: 'Риск добавлен', life: 2000 })
    } else {
      await api.put(`/projects/${props.projectId}/risks/${editingRiskId.value}`, payload)
      toast.add({ severity: 'success', summary: 'Риск обновлён', life: 2000 })
    }
    showDialog.value = false
    await fetchRisks()
  } catch (err: any) {
    toast.add({ severity: 'error', summary: 'Ошибка', detail: err.message, life: 4000 })
  } finally {
    saving.value = false
  }
}

function confirmDelete(risk: ProjectRisk) {
  confirm.require({
    message: `Удалить риск "${risk.title}"?`,
    header: 'Подтверждение удаления',
    icon: 'pi pi-exclamation-triangle',
    rejectLabel: 'Отмена',
    acceptLabel: 'Удалить',
    acceptClass: 'p-button-danger',
    accept: () => deleteRisk(risk.id),
  })
}

async function deleteRisk(riskId: string) {
  try {
    await api.delete(`/projects/${props.projectId}/risks/${riskId}`)
    risks.value = risks.value.filter(r => r.id !== riskId)
    toast.add({ severity: 'success', summary: 'Риск удалён', life: 2000 })
  } catch (err: any) {
    toast.add({ severity: 'error', summary: 'Ошибка', detail: err.message, life: 4000 })
  }
}

function toggleExpand(riskId: string) {
  expandedRiskId.value = expandedRiskId.value === riskId ? null : riskId
}

function formatDateTime(d: string): string {
  return new Date(d).toLocaleString('ru-RU', {
    day: 'numeric',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  })
}

onMounted(fetchRisks)
</script>

<template>
  <div class="risk-panel">
    <div class="risk-header">
      <h3>Реестр рисков</h3>
      <Button
        label="Добавить риск"
        icon="pi pi-plus"
        size="small"
        @click="openCreateDialog"
      />
    </div>

    <div v-if="loading" class="loading">
      <i class="pi pi-spin pi-spinner" /> Загрузка...
    </div>

    <div v-else-if="risks.length === 0" class="empty-panel">
      Рисков пока нет
    </div>

    <div v-else class="risk-list">
      <div
        v-for="risk in risks"
        :key="risk.id"
        class="risk-card"
        :style="{ borderLeftColor: severityColors[risk.severity] }"
      >
        <div class="risk-card-header" @click="toggleExpand(risk.id)">
          <div class="risk-title-row">
            <strong class="risk-title">{{ risk.title }}</strong>
            <div class="risk-badges">
              <Tag
                :value="severityLabels[risk.severity]"
                :style="{
                  background: severityColors[risk.severity] + '20',
                  color: severityColors[risk.severity],
                  border: `1px solid ${severityColors[risk.severity]}40`,
                }"
              />
              <Tag
                :value="statusLabels[risk.status]"
                :severity="statusTagSeverity[risk.status]"
              />
            </div>
          </div>
          <div class="risk-meta">
            <span><i class="pi pi-calendar" /> {{ formatDateTime(risk.created_at) }}</span>
            <i
              :class="expandedRiskId === risk.id ? 'pi pi-chevron-up' : 'pi pi-chevron-down'"
              class="expand-icon"
            />
          </div>
        </div>

        <div v-if="expandedRiskId === risk.id" class="risk-card-body">
          <div v-if="risk.description" class="risk-field">
            <span class="risk-field-label">Описание</span>
            <p>{{ risk.description }}</p>
          </div>
          <div class="risk-field">
            <span class="risk-field-label">Влияние</span>
            <p>{{ risk.impact }}</p>
          </div>
          <div v-if="risk.mitigation_plan" class="risk-field">
            <span class="risk-field-label">План снижения</span>
            <p>{{ risk.mitigation_plan }}</p>
          </div>
          <div class="risk-card-actions">
            <Button
              label="Редактировать"
              icon="pi pi-pencil"
              size="small"
              severity="secondary"
              text
              @click.stop="openEditDialog(risk)"
            />
            <Button
              label="Удалить"
              icon="pi pi-trash"
              size="small"
              severity="danger"
              text
              @click.stop="confirmDelete(risk)"
            />
          </div>
        </div>
      </div>
    </div>

    <!-- Create / Edit dialog -->
    <Dialog
      v-model:visible="showDialog"
      :header="dialogMode === 'create' ? 'Новый риск' : 'Редактирование риска'"
      :modal="true"
      :style="{ width: '600px' }"
    >
      <div class="risk-form">
        <div class="field">
          <label>Название *</label>
          <InputText v-model="form.title" placeholder="Краткое название риска" />
        </div>

        <div class="field">
          <label>Описание</label>
          <Textarea
            v-model="form.description"
            placeholder="Подробное описание риска..."
            rows="3"
            auto-resize
          />
        </div>

        <div class="field-row">
          <div class="field">
            <label>Серьёзность *</label>
            <Select
              v-model="form.severity"
              :options="severityOptions"
              option-label="label"
              option-value="value"
              placeholder="Серьёзность"
            />
          </div>
          <div class="field">
            <label>Вероятность *</label>
            <Select
              v-model="form.probability"
              :options="probabilityOptions"
              option-label="label"
              option-value="value"
              placeholder="Вероятность"
            />
          </div>
        </div>

        <div class="field">
          <label>Влияние *</label>
          <InputText v-model="form.impact" placeholder="На что повлияет (сроки, бюджет, качество)" />
        </div>

        <div class="field">
          <label>План снижения</label>
          <Textarea
            v-model="form.mitigation_plan"
            placeholder="Действия для снижения вероятности или последствий..."
            rows="3"
            auto-resize
          />
        </div>

        <div v-if="dialogMode === 'edit'" class="field">
          <label>Статус</label>
          <Select
            v-model="form.status"
            :options="statusOptions"
            option-label="label"
            option-value="value"
            placeholder="Статус"
          />
        </div>
      </div>

      <template #footer>
        <Button
          label="Отмена"
          severity="secondary"
          text
          @click="showDialog = false"
        />
        <Button
          :label="dialogMode === 'create' ? 'Создать' : 'Сохранить'"
          icon="pi pi-check"
          :loading="saving"
          :disabled="!form.title.trim() || !form.impact.trim()"
          @click="saveRisk"
        />
      </template>
    </Dialog>
  </div>
</template>

<style scoped>
.risk-panel {
  padding: 16px 0;
}

.risk-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.risk-header h3 {
  margin: 0;
  font-size: 1.1rem;
  color: #1e293b;
}

.loading {
  padding: 32px;
  text-align: center;
  color: #64748b;
}

.empty-panel {
  padding: 32px;
  text-align: center;
  color: #94a3b8;
}

.risk-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.risk-card {
  background: white;
  border: 1px solid #e2e8f0;
  border-left: 4px solid #94a3b8;
  border-radius: 8px;
  overflow: hidden;
  transition: box-shadow 0.15s ease;
}

.risk-card:hover {
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
}

.risk-card-header {
  padding: 14px 16px;
  cursor: pointer;
  transition: background 0.15s ease;
}

.risk-card-header:hover {
  background: #f8fafc;
}

.risk-title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 6px;
}

.risk-title {
  font-size: 0.95rem;
  color: #1e293b;
  flex: 1;
  min-width: 0;
}

.risk-badges {
  display: flex;
  gap: 8px;
  flex-shrink: 0;
}

.risk-meta {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 0.8rem;
  color: #64748b;
}

.risk-meta i.pi-calendar {
  margin-right: 4px;
  color: #94a3b8;
}

.expand-icon {
  color: #94a3b8;
  font-size: 0.85rem;
}

.risk-card-body {
  border-top: 1px solid #e2e8f0;
  padding: 14px 16px;
}

.risk-field {
  margin-bottom: 12px;
}

.risk-field:last-of-type {
  margin-bottom: 16px;
}

.risk-field-label {
  display: block;
  font-size: 0.75rem;
  color: #94a3b8;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 4px;
}

.risk-field p {
  margin: 0;
  font-size: 0.875rem;
  color: #1e293b;
  white-space: pre-wrap;
}

.risk-card-actions {
  display: flex;
  gap: 8px;
  padding-top: 8px;
  border-top: 1px solid #f1f5f9;
}

/* Dialog form styles */
.risk-form {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.risk-form .field {
  display: flex;
  flex-direction: column;
  gap: 6px;
  flex: 1;
}

.risk-form .field label {
  font-size: 0.85rem;
  color: #475569;
  font-weight: 500;
}

.risk-form .field-row {
  display: flex;
  gap: 12px;
}

.risk-form :deep(.p-inputtext),
.risk-form :deep(.p-textarea),
.risk-form :deep(.p-select) {
  width: 100%;
}
</style>

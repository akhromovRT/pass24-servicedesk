<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import Button from 'primevue/button'
import Card from 'primevue/card'
import InputText from 'primevue/inputtext'
import Textarea from 'primevue/textarea'
import Select from 'primevue/select'
import DatePicker from 'primevue/datepicker'
import Divider from 'primevue/divider'
import { useToast } from 'primevue/usetoast'
import { useProjectsStore } from '../stores/projects'
import type { ProjectType } from '../types'

const router = useRouter()
const toast = useToast()
const store = useProjectsStore()

const typeOptions = [
  { label: 'Стандартный ЖК', value: 'residential', icon: 'pi pi-home' },
  { label: 'Стандартный БЦ', value: 'commercial', icon: 'pi pi-building' },
  { label: 'Только камеры', value: 'cameras_only', icon: 'pi pi-camera' },
  { label: 'Большая стройка', value: 'large_construction', icon: 'pi pi-wrench' },
]

// form state
const name = ref('')
const customerId = ref('')
const customerCompany = ref('')
const objectName = ref('')
const objectAddress = ref('')
const projectType = ref<ProjectType>('residential')
const contractNumber = ref('')
const contractSignedAt = ref<Date | null>(null)
const plannedStartDate = ref<Date | null>(null)
const managerId = ref('')
const notes = ref('')
const saving = ref(false)

const selectedTemplate = computed(() =>
  store.templates.find((t) => t.project_type === projectType.value),
)

const totalPhases = computed(() => selectedTemplate.value?.phases.length ?? 0)
const totalTasks = computed(() =>
  selectedTemplate.value?.phases.reduce((sum, p) => sum + p.tasks.length, 0) ?? 0,
)
const totalDuration = computed(() => selectedTemplate.value?.total_duration_days ?? 0)

const canSubmit = computed(() =>
  name.value.trim().length > 0
    && customerId.value.trim().length > 0
    && customerCompany.value.trim().length > 0
    && objectName.value.trim().length > 0,
)

async function submit() {
  if (!canSubmit.value) {
    toast.add({
      severity: 'warn',
      summary: 'Заполните обязательные поля',
      life: 3000,
    })
    return
  }
  saving.value = true
  try {
    const project = await store.createProject({
      name: name.value.trim(),
      customer_id: customerId.value.trim(),
      customer_company: customerCompany.value.trim(),
      object_name: objectName.value.trim(),
      object_address: objectAddress.value.trim() || undefined,
      project_type: projectType.value,
      contract_number: contractNumber.value.trim() || undefined,
      contract_signed_at: contractSignedAt.value?.toISOString().slice(0, 10),
      planned_start_date: plannedStartDate.value?.toISOString().slice(0, 10),
      manager_id: managerId.value.trim() || undefined,
      notes: notes.value.trim() || undefined,
    })
    toast.add({
      severity: 'success',
      summary: 'Проект создан',
      detail: `Код: ${project.code}`,
      life: 3000,
    })
    router.push(`/projects/${project.id}`)
  } catch (err: any) {
    toast.add({
      severity: 'error',
      summary: 'Ошибка создания',
      detail: err.message,
      life: 5000,
    })
  } finally {
    saving.value = false
  }
}

onMounted(async () => {
  try {
    await store.fetchTemplates()
  } catch (err: any) {
    toast.add({
      severity: 'error',
      summary: 'Не удалось загрузить шаблоны',
      detail: err.message,
      life: 4000,
    })
  }
})
</script>

<template>
  <div class="project-create-page">
    <Button icon="pi pi-arrow-left" label="К списку" text @click="router.push('/projects')" />
    <h1>Создание проекта внедрения</h1>

    <div class="create-grid">
      <!-- Форма -->
      <Card>
        <template #title>Основная информация</template>
        <template #content>
          <div class="form-fields">
            <div class="field">
              <label>Название проекта *</label>
              <InputText v-model="name" placeholder="Внедрение PASS24 в ЖК Ромашка" />
            </div>

            <div class="field-row">
              <div class="field">
                <label>ID клиента (User.id) *</label>
                <InputText v-model="customerId" placeholder="UUID пользователя PM" />
              </div>
              <div class="field">
                <label>Компания клиента *</label>
                <InputText v-model="customerCompany" placeholder="УК Ромашка" />
              </div>
            </div>

            <div class="field-row">
              <div class="field">
                <label>Название объекта *</label>
                <InputText v-model="objectName" placeholder="ЖК Ромашка" />
              </div>
              <div class="field">
                <label>Адрес объекта</label>
                <InputText v-model="objectAddress" placeholder="Москва, ул. ..." />
              </div>
            </div>

            <div class="field">
              <label>Тип проекта *</label>
              <Select
                v-model="projectType"
                :options="typeOptions"
                option-label="label"
                option-value="value"
                placeholder="Выберите тип"
              >
                <template #value="slotProps">
                  <div v-if="slotProps.value" class="select-value">
                    <i :class="typeOptions.find(t => t.value === slotProps.value)?.icon" />
                    {{ typeOptions.find(t => t.value === slotProps.value)?.label }}
                  </div>
                </template>
                <template #option="slotProps">
                  <div class="select-option">
                    <i :class="slotProps.option.icon" />
                    {{ slotProps.option.label }}
                  </div>
                </template>
              </Select>
            </div>

            <Divider />

            <div class="field-row">
              <div class="field">
                <label>Номер договора</label>
                <InputText v-model="contractNumber" placeholder="ДГ-2026-123" />
              </div>
              <div class="field">
                <label>Дата подписания</label>
                <DatePicker v-model="contractSignedAt" date-format="dd.mm.yy" show-icon />
              </div>
            </div>

            <div class="field-row">
              <div class="field">
                <label>Плановая дата старта</label>
                <DatePicker v-model="plannedStartDate" date-format="dd.mm.yy" show-icon />
              </div>
              <div class="field">
                <label>Менеджер (User.id)</label>
                <InputText v-model="managerId" placeholder="UUID support_agent" />
              </div>
            </div>

            <div class="field">
              <label>Примечания</label>
              <Textarea v-model="notes" rows="3" auto-resize />
            </div>

            <div class="form-actions">
              <Button
                label="Создать проект"
                icon="pi pi-check"
                :loading="saving"
                :disabled="!canSubmit"
                @click="submit"
              />
              <Button
                label="Отмена"
                severity="secondary"
                text
                @click="router.push('/projects')"
              />
            </div>
          </div>
        </template>
      </Card>

      <!-- Preview шаблона -->
      <Card class="preview-card">
        <template #title>
          <div class="preview-header">
            <i class="pi pi-file-o" />
            Предпросмотр шаблона
          </div>
        </template>
        <template #content>
          <div v-if="selectedTemplate">
            <h3>{{ selectedTemplate.title }}</h3>
            <p class="template-desc">{{ selectedTemplate.description }}</p>
            <div class="template-stats">
              <div class="stat"><strong>{{ totalPhases }}</strong><span>фаз</span></div>
              <div class="stat"><strong>{{ totalTasks }}</strong><span>задач</span></div>
              <div class="stat"><strong>{{ totalDuration }}</strong><span>дней</span></div>
            </div>
            <Divider />
            <div class="phases-preview">
              <div
                v-for="phase in selectedTemplate.phases"
                :key="phase.order"
                class="phase-preview-item"
              >
                <span class="phase-num">{{ phase.order }}</span>
                <div>
                  <strong>{{ phase.name }}</strong>
                  <span class="phase-days">{{ phase.duration_days }} дн · {{ phase.tasks.length }} задач</span>
                </div>
              </div>
            </div>
          </div>
          <div v-else class="loading-template">Загрузка шаблонов...</div>
        </template>
      </Card>
    </div>
  </div>
</template>

<style scoped>
.project-create-page {
  max-width: 1400px;
  margin: 0 auto;
  padding: 24px;
}
h1 { margin: 16px 0 24px; font-size: 1.75rem; }
.create-grid {
  display: grid;
  grid-template-columns: 1fr 400px;
  gap: 24px;
}
@media (max-width: 900px) {
  .create-grid { grid-template-columns: 1fr; }
}
.form-fields {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.field {
  display: flex;
  flex-direction: column;
  gap: 6px;
  flex: 1;
}
.field label {
  font-size: 0.85rem;
  color: #475569;
  font-weight: 500;
}
.field-row {
  display: flex;
  gap: 12px;
}
.form-actions {
  display: flex;
  gap: 12px;
  margin-top: 8px;
}
.preview-card {
  position: sticky;
  top: 24px;
  height: fit-content;
}
.preview-header {
  display: flex;
  align-items: center;
  gap: 8px;
}
.template-desc {
  color: #64748b;
  font-size: 0.875rem;
  margin: 4px 0 12px;
}
.template-stats {
  display: flex;
  gap: 16px;
  margin: 12px 0;
}
.stat {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 12px;
  background: #f8fafc;
  border-radius: 6px;
  flex: 1;
}
.stat strong {
  font-size: 1.5rem;
  color: #3b82f6;
}
.stat span {
  font-size: 0.75rem;
  color: #64748b;
  text-transform: uppercase;
}
.phases-preview {
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-height: 400px;
  overflow-y: auto;
}
.phase-preview-item {
  display: flex;
  gap: 8px;
  align-items: center;
}
.phase-num {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 24px;
  height: 24px;
  background: #dbeafe;
  color: #1e40af;
  border-radius: 12px;
  font-size: 0.75rem;
  font-weight: 600;
  flex-shrink: 0;
}
.phase-preview-item strong {
  font-size: 0.875rem;
  display: block;
}
.phase-days {
  font-size: 0.75rem;
  color: #64748b;
}
.loading-template { padding: 24px; text-align: center; color: #94a3b8; }
.select-value, .select-option {
  display: flex;
  align-items: center;
  gap: 8px;
}
</style>

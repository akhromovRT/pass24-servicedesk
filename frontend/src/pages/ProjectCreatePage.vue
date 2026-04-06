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
import Dialog from 'primevue/dialog'
import { useToast } from 'primevue/usetoast'
import { useProjectsStore } from '../stores/projects'
import type { ProjectType, User } from '../types'

const router = useRouter()
const toast = useToast()
const store = useProjectsStore()

const typeOptions = [
  { label: 'Стандартный ЖК', value: 'residential', icon: 'pi pi-home' },
  { label: 'Стандартный БЦ', value: 'commercial', icon: 'pi pi-building' },
  { label: 'Только камеры', value: 'cameras_only', icon: 'pi pi-camera' },
  { label: 'Большая стройка', value: 'large_construction', icon: 'pi pi-wrench' },
]

// Users for autocomplete
const customers = ref<User[]>([])
const managers = ref<User[]>([])

// Form state
const name = ref('')
const selectedCustomer = ref<User | null>(null)
const customerCompany = ref('')
const objectName = ref('')
const objectAddress = ref('')
const projectType = ref<ProjectType>('residential')
const contractNumber = ref('')
const contractSignedAt = ref<Date | null>(null)
const plannedStartDate = ref<Date | null>(null)
const selectedManager = ref<User | null>(null)
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
    && selectedCustomer.value !== null
    && customerCompany.value.trim().length > 0
    && objectName.value.trim().length > 0,
)

async function submit() {
  if (!canSubmit.value || !selectedCustomer.value) return
  saving.value = true
  try {
    const payload: Record<string, unknown> = {
      name: name.value.trim(),
      customer_id: String(selectedCustomer.value.id),
      customer_company: customerCompany.value.trim(),
      object_name: objectName.value.trim(),
      object_address: objectAddress.value.trim() || undefined,
      project_type: projectType.value,
      contract_number: contractNumber.value.trim() || undefined,
      contract_signed_at: contractSignedAt.value?.toISOString().slice(0, 10),
      planned_start_date: plannedStartDate.value?.toISOString().slice(0, 10),
      manager_id: selectedManager.value ? String(selectedManager.value.id) : undefined,
      notes: notes.value.trim() || undefined,
    }
    // Welcome-email для нового клиента
    if (createdPassword.value) {
      payload.send_welcome_email = true
      payload.customer_temp_password = createdPassword.value
    }
    const project = await store.createProject(payload as any)
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

// --- Create new customer dialog ---
const showCreateCustomer = ref(false)
const newCustName = ref('')
const newCustEmail = ref('')
const newCustPhone = ref('')
const newCustCompany = ref('')
const creatingCustomer = ref(false)
const createdPassword = ref('')

async function createNewCustomer() {
  if (!newCustName.value.trim() || !newCustEmail.value.trim() || !newCustCompany.value.trim()) {
    toast.add({ severity: 'warn', summary: 'Заполните Ф��О, email и компанию', life: 3000 })
    return
  }
  creatingCustomer.value = true
  try {
    const result = await store.createCustomer({
      email: newCustEmail.value.trim(),
      full_name: newCustName.value.trim(),
      phone: newCustPhone.value.trim() || undefined,
      company: newCustCompany.value.trim(),
    })
    // Auto-select and fill
    const newUser: User = {
      id: result.id,
      email: result.email,
      full_name: result.full_name,
      role: 'property_manager',
      is_active: true,
      created_at: new Date().toISOString(),
    }
    customers.value.push(newUser)
    selectedCustomer.value = newUser
    customerCompany.value = newCustCompany.value.trim()
    createdPassword.value = result.temp_password
    toast.add({
      severity: 'success',
      summary: 'Клиент со��дан',
      detail: `${result.full_name} (${result.email}). Пароль: ${result.temp_password}`,
      life: 10000,
    })
    // Reset form but keep dialog open to show password
  } catch (err: any) {
    toast.add({ severity: 'error', summary: 'Ошибка', detail: err.message, life: 5000 })
  } finally {
    creatingCustomer.value = false
  }
}

function closeCreateCustomer() {
  showCreateCustomer.value = false
  newCustName.value = ''
  newCustEmail.value = ''
  newCustPhone.value = ''
  newCustCompany.value = ''
  createdPassword.value = ''
}

onMounted(async () => {
  try {
    const [, customerList, managerList] = await Promise.all([
      store.fetchTemplates(),
      store.fetchUsers('property_manager'),
      store.fetchUsers('support_agent,admin'),
    ])
    customers.value = customerList
    managers.value = managerList
  } catch (err: any) {
    toast.add({
      severity: 'error',
      summary: 'Ошибка загрузки',
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
                <label>Клиент (администратор УК) *</label>
                <div class="field-with-action">
                  <Select
                    v-model="selectedCustomer"
                    :options="customers"
                    option-label="full_name"
                    placeholder="Выберите клиента"
                    filter
                    filter-placeholder="Поиск по имени..."
                    show-clear
                    class="flex-grow"
                  >
                    <template #option="{ option }">
                      <div class="user-option">
                        <strong>{{ option.full_name }}</strong>
                        <span class="user-email">{{ option.email }}</span>
                      </div>
                    </template>
                    <template #value="{ value }">
                      <span v-if="value">{{ value.full_name }} ({{ value.email }})</span>
                      <span v-else class="placeholder">Выберите клиента</span>
                    </template>
                  </Select>
                  <Button
                    icon="pi pi-user-plus"
                    severity="secondary"
                    outlined
                    title="Создать нового клиента"
                    @click="showCreateCustomer = true"
                  />
                </div>
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
                <label>Менеджер проекта (PASS24)</label>
                <Select
                  v-model="selectedManager"
                  :options="managers"
                  option-label="full_name"
                  placeholder="Выберите менеджера"
                  filter
                  filter-placeholder="Поиск..."
                  show-clear
                >
                  <template #option="{ option }">
                    <div class="user-option">
                      <strong>{{ option.full_name }}</strong>
                      <span class="user-email">{{ option.email }}</span>
                    </div>
                  </template>
                  <template #value="{ value }">
                    <span v-if="value">{{ value.full_name }}</span>
                    <span v-else class="placeholder">Не назначен</span>
                  </template>
                </Select>
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
              <Button label="Отмена" severity="secondary" text @click="router.push('/projects')" />
            </div>
          </div>
        </template>
      </Card>

      <!-- Preview шаблона -->
      <Card class="preview-card">
        <template #title>
          <div class="preview-header"><i class="pi pi-file-o" /> Предпросмотр шаблона</div>
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
              <div v-for="phase in selectedTemplate.phases" :key="phase.order" class="phase-preview-item">
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

    <!-- Create customer dialog -->
    <Dialog v-model:visible="showCreateCustomer" header="Создать клиента-администратора УК" :modal="true" :style="{ width: '500px' }" @hide="closeCreateCustomer">
      <div v-if="createdPassword" class="customer-created-success">
        <div class="success-banner">
          <i class="pi pi-check-circle" />
          <div>
            <strong>Клиент создан!</strong>
            <p>{{ newCustName }} ({{ newCustEmail }})</p>
          </div>
        </div>
        <div class="password-block">
          <label>Временный пароль (покажите клиенту):</label>
          <code class="temp-password">{{ createdPassword }}</code>
        </div>
        <p class="welcome-hint">
          <i class="pi pi-envelope" />
          Welcome-письмо с доступом к порталу будет отправлено автоматически при создании проекта.
        </p>
        <Button label="Готово" icon="pi pi-check" @click="closeCreateCustomer" class="close-btn" />
      </div>
      <div v-else class="create-customer-form">
        <div class="field">
          <label>ФИО *</label>
          <InputText v-model="newCustName" placeholder="Иванов Иван Иванович" />
        </div>
        <div class="field">
          <label>Email *</label>
          <InputText v-model="newCustEmail" placeholder="ivanov@uk-romashka.ru" />
        </div>
        <div class="field">
          <label>Телефон</label>
          <InputText v-model="newCustPhone" placeholder="+7 (999) 123-45-67" />
        </div>
        <div class="field">
          <label>Название УК / компании *</label>
          <InputText v-model="newCustCompany" placeholder="УК Ромашка" />
        </div>
      </div>
      <template v-if="!createdPassword" #footer>
        <Button label="Отмена" severity="secondary" text @click="closeCreateCustomer" />
        <Button
          label="Создать клиента"
          icon="pi pi-user-plus"
          :loading="creatingCustomer"
          :disabled="!newCustName.trim() || !newCustEmail.trim() || !newCustCompany.trim()"
          @click="createNewCustomer"
        />
      </template>
    </Dialog>
  </div>
</template>

<style scoped>
.project-create-page { max-width: 1400px; margin: 0 auto; padding: 24px; }
h1 { margin: 16px 0 24px; font-size: 1.75rem; }
.create-grid { display: grid; grid-template-columns: 1fr 400px; gap: 24px; }
@media (max-width: 900px) { .create-grid { grid-template-columns: 1fr; } }
.form-fields { display: flex; flex-direction: column; gap: 16px; }
.field { display: flex; flex-direction: column; gap: 6px; flex: 1; }
.field label { font-size: 0.85rem; color: #475569; font-weight: 500; }
.field-row { display: flex; gap: 12px; }
.form-actions { display: flex; gap: 12px; margin-top: 8px; }
.user-option { display: flex; flex-direction: column; }
.user-email { font-size: 0.8rem; color: #64748b; }
.placeholder { color: #94a3b8; }
.preview-card { position: sticky; top: 24px; height: fit-content; }
.preview-header { display: flex; align-items: center; gap: 8px; }
.template-desc { color: #64748b; font-size: 0.875rem; margin: 4px 0 12px; }
.template-stats { display: flex; gap: 16px; margin: 12px 0; }
.stat { display: flex; flex-direction: column; align-items: center; padding: 12px; background: #f8fafc; border-radius: 6px; flex: 1; }
.stat strong { font-size: 1.5rem; color: #3b82f6; }
.stat span { font-size: 0.75rem; color: #64748b; text-transform: uppercase; }
.phases-preview { display: flex; flex-direction: column; gap: 8px; max-height: 400px; overflow-y: auto; }
.phase-preview-item { display: flex; gap: 8px; align-items: center; }
.phase-num { display: inline-flex; align-items: center; justify-content: center; min-width: 24px; height: 24px; background: #dbeafe; color: #1e40af; border-radius: 12px; font-size: 0.75rem; font-weight: 600; flex-shrink: 0; }
.phase-preview-item strong { font-size: 0.875rem; display: block; }
.phase-days { font-size: 0.75rem; color: #64748b; }
.loading-template { padding: 24px; text-align: center; color: #94a3b8; }
.select-value, .select-option { display: flex; align-items: center; gap: 8px; }
.field-with-action { display: flex; gap: 8px; align-items: flex-start; }
.flex-grow { flex: 1; }
.create-customer-form { display: flex; flex-direction: column; gap: 16px; }
.create-customer-form .field { display: flex; flex-direction: column; gap: 6px; }
.create-customer-form .field label { font-size: 0.85rem; color: #475569; font-weight: 500; }
.customer-created-success { display: flex; flex-direction: column; gap: 16px; }
.success-banner { display: flex; align-items: center; gap: 12px; background: #f0fdf4; border-radius: 8px; padding: 12px 16px; }
.success-banner i { font-size: 1.5rem; color: #10b981; }
.success-banner p { margin: 4px 0 0; color: #64748b; font-size: 0.875rem; }
.password-block { background: #f8fafc; border-radius: 8px; padding: 12px 16px; }
.password-block label { font-size: 0.85rem; color: #475569; display: block; margin-bottom: 8px; }
.temp-password { font-size: 1.25rem; font-weight: 600; background: #e2e8f0; padding: 4px 12px; border-radius: 4px; user-select: all; }
.welcome-hint { display: flex; align-items: center; gap: 8px; color: #64748b; font-size: 0.875rem; }
.welcome-hint i { color: #3b82f6; }
.close-btn { align-self: flex-end; }
</style>

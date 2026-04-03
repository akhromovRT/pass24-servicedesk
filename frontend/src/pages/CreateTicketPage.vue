<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import Card from 'primevue/card'
import InputText from 'primevue/inputtext'
import Textarea from 'primevue/textarea'
import Select from 'primevue/select'
import Checkbox from 'primevue/checkbox'
import Button from 'primevue/button'
import Divider from 'primevue/divider'
import { useToast } from 'primevue/usetoast'
import { useTicketsStore } from '../stores/tickets'
import type {
  TicketCreate,
  TicketProduct,
  TicketCategory,
  TicketType,
} from '../types'

const router = useRouter()
const toast = useToast()
const store = useTicketsStore()

// --- Step management ---
const step = ref<1 | 2>(1)
const submitted = ref(false)

// --- Quick select card definitions ---
interface QuickCard {
  id: string
  icon: string
  label: string
  defaults: Partial<TicketCreate>
}

const quickCards: QuickCard[] = [
  {
    id: 'cant_enter',
    icon: 'pi pi-sign-in',
    label: 'Не могу попасть / проехать',
    defaults: {
      product: 'pass24_online',
      category: 'passes',
      urgent: true,
      ticket_type: 'incident',
    },
  },
  {
    id: 'app_problem',
    icon: 'pi pi-mobile',
    label: 'Проблема с приложением',
    defaults: {
      product: 'mobile_app',
      category: 'app_issues',
    },
  },
  {
    id: 'mobile_key',
    icon: 'pi pi-key',
    label: 'Проблема с мобильным ключом',
    defaults: {
      product: 'pass24_key',
    },
  },
  {
    id: 'auto_recognition',
    icon: 'pi pi-car',
    label: 'Шлагбаум / распознавание номеров',
    defaults: {
      product: 'pass24_auto',
      category: 'recognition',
    },
  },
  {
    id: 'pass_problem',
    icon: 'pi pi-id-card',
    label: 'Проблема с пропуском',
    defaults: {
      product: 'pass24_online',
      category: 'passes',
    },
  },
  {
    id: 'equipment',
    icon: 'pi pi-cog',
    label: 'Оборудование',
    defaults: {
      product: 'equipment',
      category: 'equipment_issues',
    },
  },
  {
    id: 'consultation',
    icon: 'pi pi-question-circle',
    label: 'Консультация / вопрос',
    defaults: {
      ticket_type: 'question',
      category: 'consultation',
    },
  },
  {
    id: 'feature',
    icon: 'pi pi-lightbulb',
    label: 'Предложение / идея',
    defaults: {
      ticket_type: 'feature_request',
      category: 'feature_request',
    },
  },
  {
    id: 'other',
    icon: 'pi pi-box',
    label: 'Другое',
    defaults: {
      product: 'other',
    },
  },
]

const selectedCardId = ref<string | null>(null)

// --- Form fields ---
const title = ref('')
const description = ref('')
const product = ref<TicketProduct | undefined>(undefined)
const category = ref<TicketCategory | undefined>(undefined)
const ticketType = ref<TicketType | undefined>(undefined)
const objectName = ref('')
const accessPoint = ref('')
const contactPhone = ref('')
const company = ref('')
const deviceType = ref<string | undefined>(undefined)
const urgent = ref(false)

// --- Dropdown options ---
const productOptions = [
  { label: 'PASS24.online', value: 'pass24_online' },
  { label: 'Мобильное приложение', value: 'mobile_app' },
  { label: 'PASS24.Key (мобильные ключи)', value: 'pass24_key' },
  { label: 'PASS24.control (СКУД)', value: 'pass24_control' },
  { label: 'PASS24.auto (распознавание номеров)', value: 'pass24_auto' },
  { label: 'Оборудование', value: 'equipment' },
  { label: 'Интеграция', value: 'integration' },
  { label: 'Другое', value: 'other' },
]

const categoryOptions = [
  { label: 'Регистрация и вход', value: 'registration' },
  { label: 'Пропуска и доступ', value: 'passes' },
  { label: 'Распознавание номеров', value: 'recognition' },
  { label: 'Работа приложения', value: 'app_issues' },
  { label: 'Объекты', value: 'objects' },
  { label: 'Доверенные лица', value: 'trusted_persons' },
  { label: 'Оборудование', value: 'equipment_issues' },
  { label: 'Консультация', value: 'consultation' },
  { label: 'Предложение', value: 'feature_request' },
  { label: 'Другое', value: 'other' },
]

const ticketTypeOptions = [
  { label: 'Инцидент (всё не работает)', value: 'incident' },
  { label: 'Проблема', value: 'problem' },
  { label: 'Вопрос', value: 'question' },
  { label: 'Запрос на настройку', value: 'request' },
  { label: 'Предложение / идея', value: 'feature_request' },
]

const deviceTypeOptions = [
  { label: 'iOS', value: 'ios' },
  { label: 'Android', value: 'android' },
  { label: 'Веб', value: 'web' },
  { label: 'Другое', value: 'other' },
]

// --- Computed ---
const showDeviceType = computed(() =>
  product.value === 'mobile_app' || product.value === 'pass24_key',
)

// --- Validation ---
const titleInvalid = computed(() => submitted.value && !title.value.trim())
const descriptionInvalid = computed(() => submitted.value && !description.value.trim())

// --- Actions ---
function selectCard(card: QuickCard) {
  selectedCardId.value = card.id

  // Apply defaults from the selected card
  product.value = card.defaults.product
  category.value = card.defaults.category
  ticketType.value = card.defaults.ticket_type
  urgent.value = card.defaults.urgent ?? false

  step.value = 2
}

function goBackToStep1() {
  step.value = 1
  submitted.value = false
}

async function onSubmit() {
  submitted.value = true

  if (titleInvalid.value || descriptionInvalid.value) return

  const data: TicketCreate = {
    title: title.value.trim(),
    description: description.value.trim(),
    product: product.value,
    category: category.value,
    ticket_type: ticketType.value,
    object_name: objectName.value.trim() || undefined,
    access_point: accessPoint.value.trim() || undefined,
    contact_phone: contactPhone.value.trim() || undefined,
    company: company.value.trim() || undefined,
    device_type: showDeviceType.value ? deviceType.value : undefined,
    urgent: urgent.value,
  }

  try {
    const ticket = await store.createTicket(data)
    toast.add({
      severity: 'success',
      summary: 'Заявка создана',
      detail: `Заявка "${ticket.title}" успешно создана`,
      life: 3000,
    })
    router.push(`/tickets/${ticket.id}`)
  } catch (e: any) {
    toast.add({
      severity: 'error',
      summary: 'Ошибка',
      detail: e.message || 'Не удалось создать заявку',
      life: 4000,
    })
  }
}

function goBack() {
  router.push('/')
}
</script>

<template>
  <div class="create-ticket-page">
    <Button
      label="Назад к заявкам"
      icon="pi pi-arrow-left"
      severity="secondary"
      text
      class="back-button"
      @click="goBack"
    />

    <!-- Step 1: Quick select cards -->
    <div v-if="step === 1" class="step-1">
      <h2 class="step-title">Что случилось?</h2>
      <p class="step-subtitle">Выберите тему, чтобы мы быстрее помогли</p>

      <div class="quick-cards-grid">
        <div
          v-for="card in quickCards"
          :key="card.id"
          class="quick-card"
          :class="{ selected: selectedCardId === card.id }"
          tabindex="0"
          role="button"
          @click="selectCard(card)"
          @keydown.enter="selectCard(card)"
          @keydown.space.prevent="selectCard(card)"
        >
          <i :class="card.icon" class="quick-card-icon" />
          <span class="quick-card-label">{{ card.label }}</span>
        </div>
      </div>
    </div>

    <!-- Step 2: Details form -->
    <div v-if="step === 2" class="step-2">
      <Button
        label="Назад к выбору темы"
        icon="pi pi-arrow-left"
        severity="secondary"
        text
        class="back-to-step1"
        @click="goBackToStep1"
      />

      <Card class="create-card">
        <template #title>Новая заявка</template>
        <template #content>
          <form class="ticket-form" @submit.prevent="onSubmit">
            <!-- Section: Main info -->
            <div class="form-section-title">Описание проблемы</div>

            <div class="field">
              <label for="title">Тема <span class="required">*</span></label>
              <InputText
                id="title"
                v-model="title"
                placeholder="Кратко опишите проблему"
                :invalid="titleInvalid"
                fluid
              />
              <small v-if="titleInvalid" class="field-error">Укажите тему заявки</small>
            </div>

            <div class="field">
              <label for="description">Описание <span class="required">*</span></label>
              <Textarea
                id="description"
                v-model="description"
                placeholder="Подробно опишите проблему: что произошло, когда, при каких условиях"
                :invalid="descriptionInvalid"
                rows="5"
                auto-resize
                fluid
              />
              <small v-if="descriptionInvalid" class="field-error">Укажите описание проблемы</small>
            </div>

            <Divider />

            <!-- Section: Classification -->
            <div class="form-section-title">Классификация</div>

            <div class="field">
              <label for="product">Продукт</label>
              <Select
                id="product"
                v-model="product"
                :options="productOptions"
                option-label="label"
                option-value="value"
                placeholder="Выберите продукт"
                fluid
              />
            </div>

            <div class="field">
              <label for="category">Категория</label>
              <Select
                id="category"
                v-model="category"
                :options="categoryOptions"
                option-label="label"
                option-value="value"
                placeholder="Выберите категорию"
                fluid
              />
            </div>

            <div class="field">
              <label for="ticketType">Тип обращения</label>
              <Select
                id="ticketType"
                v-model="ticketType"
                :options="ticketTypeOptions"
                option-label="label"
                option-value="value"
                placeholder="Выберите тип"
                fluid
              />
            </div>

            <Divider />

            <!-- Section: Object info -->
            <div class="form-section-title">Объект и точка доступа</div>

            <div class="field">
              <label for="objectName">Название объекта</label>
              <InputText
                id="objectName"
                v-model="objectName"
                placeholder="ЖК Солнечный, БЦ Меридиан"
                fluid
              />
            </div>

            <div class="field">
              <label for="accessPoint">Точка доступа</label>
              <InputText
                id="accessPoint"
                v-model="accessPoint"
                placeholder="КПП-1, подъезд 3"
                fluid
              />
            </div>

            <Divider />

            <!-- Section: Contact info -->
            <div class="form-section-title">Контактная информация</div>

            <div class="field">
              <label for="contactPhone">Телефон для связи</label>
              <InputText
                id="contactPhone"
                v-model="contactPhone"
                placeholder="+7 (999) 123-45-67"
                fluid
              />
            </div>

            <div class="field">
              <label for="company">Компания</label>
              <InputText
                id="company"
                v-model="company"
                placeholder="Название управляющей компании"
                fluid
              />
            </div>

            <!-- Section: Device (conditional) -->
            <template v-if="showDeviceType">
              <Divider />

              <div class="form-section-title">Устройство</div>

              <div class="field">
                <label for="deviceType">Тип устройства</label>
                <Select
                  id="deviceType"
                  v-model="deviceType"
                  :options="deviceTypeOptions"
                  option-label="label"
                  option-value="value"
                  placeholder="Выберите тип устройства"
                  fluid
                />
              </div>
            </template>

            <Divider />

            <!-- Urgent checkbox -->
            <div class="field-check">
              <Checkbox
                v-model="urgent"
                input-id="urgent"
                :binary="true"
              />
              <label for="urgent">Не могу попасть / проехать прямо сейчас</label>
            </div>

            <!-- Actions -->
            <div class="form-actions">
              <Button
                label="Отмена"
                severity="secondary"
                outlined
                @click="goBack"
              />
              <Button
                type="submit"
                label="Создать заявку"
                icon="pi pi-check"
                :loading="store.loading"
              />
            </div>
          </form>
        </template>
      </Card>
    </div>
  </div>
</template>

<style scoped>
.create-ticket-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
  max-width: 800px;
  margin: 0 auto;
}

.back-button {
  align-self: flex-start;
}

/* Step 1 */
.step-title {
  font-size: 1.5rem;
  font-weight: 600;
  margin: 0;
  color: var(--p-text-color);
}

.step-subtitle {
  font-size: 0.95rem;
  color: var(--p-text-muted-color);
  margin: 0.25rem 0 1rem;
}

.quick-cards-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
}

@media (max-width: 768px) {
  .quick-cards-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 480px) {
  .quick-cards-grid {
    grid-template-columns: 1fr;
  }
}

.quick-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 0.75rem;
  padding: 1.25rem 1rem;
  border: 1px solid var(--p-surface-200);
  border-radius: var(--p-border-radius);
  background: var(--p-surface-0);
  cursor: pointer;
  transition: all 0.2s ease;
  text-align: center;
  min-height: 100px;
  user-select: none;
}

.quick-card:hover {
  border-color: var(--p-primary-color);
  background: var(--p-primary-50);
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
}

.quick-card:focus-visible {
  outline: 2px solid var(--p-primary-color);
  outline-offset: 2px;
}

.quick-card.selected {
  border-color: var(--p-primary-color);
  background: var(--p-primary-50);
}

.quick-card-icon {
  font-size: 1.75rem;
  color: var(--p-primary-color);
}

.quick-card-label {
  font-size: 0.875rem;
  font-weight: 500;
  color: var(--p-text-color);
  line-height: 1.3;
}

/* Step 2 */
.back-to-step1 {
  align-self: flex-start;
  margin-bottom: -8px;
}

.create-card {
  width: 100%;
}

.ticket-form {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}

.form-section-title {
  font-size: 0.95rem;
  font-weight: 600;
  color: var(--p-text-color);
  margin-bottom: -0.5rem;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.field label {
  font-weight: 500;
  font-size: 0.875rem;
}

.required {
  color: var(--p-red-500);
}

.field-error {
  color: var(--p-red-500);
  font-size: 0.75rem;
}

.field-check {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.field-check label {
  font-weight: 500;
  font-size: 0.875rem;
  cursor: pointer;
}

.form-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  margin-top: 0.5rem;
}
</style>

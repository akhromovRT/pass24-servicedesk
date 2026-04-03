<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import Card from 'primevue/card'
import InputText from 'primevue/inputtext'
import Textarea from 'primevue/textarea'
import Select from 'primevue/select'
import Checkbox from 'primevue/checkbox'
import Button from 'primevue/button'
import { useToast } from 'primevue/usetoast'
import { useTicketsStore } from '../stores/tickets'

const router = useRouter()
const toast = useToast()
const store = useTicketsStore()

const title = ref('')
const description = ref('')
const category = ref('')
const contact = ref('')
const urgent = ref(false)
const submitted = ref(false)

const categoryOptions = [
  { label: 'Доступ', value: 'access' },
  { label: 'Пропуска', value: 'pass' },
  { label: 'Шлагбаум', value: 'gate' },
  { label: 'Уведомления', value: 'notifications' },
  { label: 'Общее', value: 'general' },
  { label: 'Другое', value: 'other' },
]

const titleInvalid = () => submitted.value && !title.value.trim()
const descriptionInvalid = () => submitted.value && !description.value.trim()

async function onSubmit() {
  submitted.value = true

  if (titleInvalid() || descriptionInvalid()) return

  try {
    const ticket = await store.createTicket({
      title: title.value.trim(),
      description: description.value.trim(),
      category: category.value || undefined,
      contact: contact.value.trim() || undefined,
      urgent: urgent.value,
    })
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

    <Card class="create-card">
      <template #title>Новая заявка</template>
      <template #content>
        <form class="ticket-form" @submit.prevent="onSubmit">
          <div class="field">
            <label for="title">Тема <span class="required">*</span></label>
            <InputText
              id="title"
              v-model="title"
              placeholder="Кратко опишите проблему"
              :invalid="titleInvalid()"
              fluid
            />
            <small v-if="titleInvalid()" class="field-error">Укажите тему заявки</small>
          </div>

          <div class="field">
            <label for="description">Описание <span class="required">*</span></label>
            <Textarea
              id="description"
              v-model="description"
              placeholder="Подробно опишите проблему: что произошло, когда, при каких условиях"
              :invalid="descriptionInvalid()"
              rows="5"
              auto-resize
              fluid
            />
            <small v-if="descriptionInvalid()" class="field-error">Укажите описание проблемы</small>
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
            <label for="contact">Контактные данные</label>
            <InputText
              id="contact"
              v-model="contact"
              placeholder="Телефон или email для обратной связи"
              fluid
            />
          </div>

          <div class="field-check">
            <Checkbox
              v-model="urgent"
              input-id="urgent"
              :binary="true"
            />
            <label for="urgent">Срочная заявка</label>
          </div>

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
</template>

<style scoped>
.create-ticket-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
  max-width: 700px;
  margin: 0 auto;
}

.back-button {
  align-self: flex-start;
}

.create-card {
  width: 100%;
}

.ticket-form {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
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

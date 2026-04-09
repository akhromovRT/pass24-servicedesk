<script setup lang="ts">
import { ref } from 'vue'
import AutoComplete from 'primevue/autocomplete'
import InputText from 'primevue/inputtext'
import Button from 'primevue/button'
import { api } from '../../api/client'

interface CustomerSuggestion {
  id: string
  name: string
  address: string
  phone: string
}

const props = defineProps<{
  objectName: string | null
  objectAddress: string | null
  accessPoint: string | null
  customerId: string | null
  ticketId: string
  isStaff: boolean
}>()

const emit = defineEmits<{
  updated: []
}>()

const editing = ref(false)
const saving = ref(false)
const selectedCustomer = ref<CustomerSuggestion | null>(null)
const searchText = ref('')
const editAddress = ref('')
const editAccessPoint = ref('')
const suggestions = ref<CustomerSuggestion[]>([])

function startEdit() {
  if (props.customerId && props.objectName) {
    selectedCustomer.value = { id: props.customerId, name: props.objectName, address: props.objectAddress || '', phone: '' }
    searchText.value = props.objectName
  } else {
    selectedCustomer.value = null
    searchText.value = props.objectName || ''
  }
  editAddress.value = props.objectAddress || ''
  editAccessPoint.value = props.accessPoint || ''
  editing.value = true
}

function cancelEdit() {
  editing.value = false
}

async function searchCustomers(event: { query: string }) {
  try {
    suggestions.value = await api.get<CustomerSuggestion[]>(`/tickets/objects/suggest?q=${encodeURIComponent(event.query)}`)
  } catch {
    suggestions.value = []
  }
}

function onSelectCustomer(event: { value: CustomerSuggestion }) {
  const item = event.value
  selectedCustomer.value = item
  searchText.value = item.name
  if (item.address) {
    editAddress.value = item.address
  }
}

function onClearCustomer() {
  selectedCustomer.value = null
}

async function save() {
  saving.value = true
  try {
    const name = typeof searchText.value === 'string'
      ? searchText.value.trim()
      : (selectedCustomer.value?.name || '')
    await api.put(`/tickets/${props.ticketId}/object`, {
      customer_id: selectedCustomer.value?.id || null,
      object_name: name || null,
      object_address: editAddress.value.trim() || null,
      access_point: editAccessPoint.value.trim() || null,
    })
    editing.value = false
    emit('updated')
  } catch {
    // error handling in caller
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div class="ticket-object-info">
    <template v-if="!editing">
      <div v-if="objectName" class="info-row">
        <span class="info-label">Клиент / Объект</span>
        <span class="info-value">
          {{ objectName }}
          <span v-if="customerId" class="linked-badge" title="Привязан к постоянному клиенту">
            <i class="pi pi-link" />
          </span>
        </span>
      </div>
      <div v-if="objectAddress" class="info-row">
        <span class="info-label">Адрес</span>
        <span class="info-value">{{ objectAddress }}</span>
      </div>
      <div v-if="accessPoint" class="info-row">
        <span class="info-label">Точка доступа</span>
        <span class="info-value">{{ accessPoint }}</span>
      </div>
      <div v-if="!objectName && !objectAddress && !accessPoint" class="info-empty">
        Клиент / объект не указан
      </div>
      <Button
        v-if="isStaff"
        :label="objectName ? 'Изменить' : 'Указать клиента'"
        icon="pi pi-pencil"
        text
        size="small"
        severity="secondary"
        class="edit-btn"
        @click="startEdit"
      />
    </template>

    <template v-else>
      <div class="edit-form">
        <div class="edit-field">
          <label>Клиент (постоянный)</label>
          <AutoComplete
            v-model="searchText"
            :suggestions="suggestions"
            optionLabel="name"
            :delay="300"
            :minLength="1"
            placeholder="Начните вводить название клиента..."
            fluid
            @complete="searchCustomers"
            @item-select="onSelectCustomer"
            @clear="onClearCustomer"
          >
            <template #option="{ option }">
              <div class="suggest-item">
                <div class="suggest-name">{{ option.name }}</div>
                <div v-if="option.address" class="suggest-address">{{ option.address }}</div>
              </div>
            </template>
          </AutoComplete>
          <small v-if="selectedCustomer" class="field-linked">
            <i class="pi pi-check-circle" /> Привязан: {{ selectedCustomer.name }}
          </small>
          <small v-else class="field-hint">Выберите из списка или введите вручную</small>
        </div>
        <div class="edit-field">
          <label>Адрес</label>
          <InputText v-model="editAddress" placeholder="Адрес объекта" fluid />
        </div>
        <div class="edit-field">
          <label>Точка доступа</label>
          <InputText v-model="editAccessPoint" placeholder="КПП, подъезд..." fluid />
        </div>
        <div class="edit-actions">
          <Button label="Сохранить" icon="pi pi-check" size="small" :loading="saving" @click="save" />
          <Button label="Отмена" icon="pi pi-times" text size="small" severity="secondary" @click="cancelEdit" />
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.ticket-object-info {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.info-row {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.info-label {
  font-size: 0.75rem;
  color: #64748b;
  font-weight: 500;
  text-transform: uppercase;
  letter-spacing: 0.025em;
}

.info-value {
  font-size: 0.875rem;
  color: #1e293b;
  display: flex;
  align-items: center;
  gap: 6px;
}

.linked-badge {
  color: #10b981;
  font-size: 0.75rem;
}

.info-empty {
  font-size: 0.8125rem;
  color: #94a3b8;
  font-style: italic;
}

.edit-btn {
  align-self: flex-start;
  margin-top: 4px;
}

.edit-form {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.edit-field {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.edit-field label {
  font-size: 0.75rem;
  color: #64748b;
  font-weight: 500;
  text-transform: uppercase;
  letter-spacing: 0.025em;
}

.field-linked {
  color: #10b981;
  font-size: 0.75rem;
  display: flex;
  align-items: center;
  gap: 4px;
}

.field-hint {
  color: #94a3b8;
  font-size: 0.75rem;
}

.suggest-item {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 2px 0;
}

.suggest-name {
  font-weight: 500;
  font-size: 0.875rem;
}

.suggest-address {
  font-size: 0.75rem;
  color: #64748b;
}

.edit-actions {
  display: flex;
  gap: 8px;
  margin-top: 4px;
}
</style>

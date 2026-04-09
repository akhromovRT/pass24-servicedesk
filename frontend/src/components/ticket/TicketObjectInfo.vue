<script setup lang="ts">
import { ref } from 'vue'
import AutoComplete from 'primevue/autocomplete'
import InputText from 'primevue/inputtext'
import Button from 'primevue/button'
import { api } from '../../api/client'

interface ObjectSuggestion {
  object_name: string
  object_address: string | null
}

const props = defineProps<{
  objectName: string | null
  objectAddress: string | null
  accessPoint: string | null
  ticketId: string
  isStaff: boolean
}>()

const emit = defineEmits<{
  updated: []
}>()

const editing = ref(false)
const saving = ref(false)
const editName = ref('')
const editAddress = ref('')
const editAccessPoint = ref('')
const suggestions = ref<ObjectSuggestion[]>([])

function startEdit() {
  editName.value = props.objectName || ''
  editAddress.value = props.objectAddress || ''
  editAccessPoint.value = props.accessPoint || ''
  editing.value = true
}

function cancelEdit() {
  editing.value = false
}

async function searchObjects(event: { query: string }) {
  try {
    suggestions.value = await api.get<ObjectSuggestion[]>(`/tickets/objects/suggest?q=${encodeURIComponent(event.query)}`)
  } catch {
    suggestions.value = []
  }
}

function onSelectSuggestion(event: { value: ObjectSuggestion }) {
  const item = event.value
  editName.value = item.object_name
  if (item.object_address) {
    editAddress.value = item.object_address
  }
}

async function save() {
  saving.value = true
  try {
    await api.put(`/tickets/${props.ticketId}/object`, {
      object_name: editName.value.trim() || null,
      object_address: editAddress.value.trim() || null,
      access_point: editAccessPoint.value.trim() || null,
    })
    editing.value = false
    emit('updated')
  } catch {
    // toast handled by caller
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div class="ticket-object-info">
    <template v-if="!editing">
      <div v-if="objectName" class="info-row">
        <span class="info-label">Объект</span>
        <span class="info-value">{{ objectName }}</span>
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
        Информация об объекте не указана
      </div>
      <Button
        v-if="isStaff"
        :label="objectName ? 'Изменить' : 'Указать объект'"
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
          <label>Объект</label>
          <AutoComplete
            v-model="editName"
            :suggestions="suggestions"
            optionLabel="object_name"
            :delay="300"
            :minLength="1"
            placeholder="Начните вводить название..."
            fluid
            @complete="searchObjects"
            @item-select="onSelectSuggestion"
          />
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

.edit-actions {
  display: flex;
  gap: 8px;
  margin-top: 4px;
}
</style>

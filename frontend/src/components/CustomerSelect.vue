<script setup lang="ts">
/**
 * CustomerSelect — autocomplete выбора компании-клиента.
 *
 * Функции:
 * - Поиск по синхронизированным компаниям (GET /customers/search?q=...)
 * - Кнопка «Добавить по ИНН» → lookup через DaData → создание в БД
 * - При выборе emit('update:modelValue', customer_id)
 */
import { ref, watch, computed } from 'vue'
import AutoComplete from 'primevue/autocomplete'
import Button from 'primevue/button'
import Dialog from 'primevue/dialog'
import InputText from 'primevue/inputtext'
import { useToast } from 'primevue/usetoast'
import { api } from '../api/client'

interface CustomerOption {
  id: string
  inn: string
  name: string
  address: string
  phone: string
}

interface DaDataResult {
  name: string
  inn: string
  kpp: string
  ogrn: string
  address: string
  director: string
  type: string
  opf: string
  status: string
}

const props = defineProps<{
  modelValue: string | null
}>()

const emit = defineEmits<{
  'update:modelValue': [value: string | null]
  'customer-selected': [customer: CustomerOption | null]
}>()

const toast = useToast()
const suggestions = ref<CustomerOption[]>([])
const selectedCustomer = ref<CustomerOption | null>(null)
const loading = ref(false)

// Dialog: создание по ИНН
const showInnDialog = ref(false)
const innInput = ref('')
const innLoading = ref(false)
const innResult = ref<DaDataResult | null>(null)
const innCreating = ref(false)

async function search(event: { query: string }) {
  if (event.query.length < 1) return
  loading.value = true
  try {
    suggestions.value = await api.get<CustomerOption[]>(
      `/customers/search?q=${encodeURIComponent(event.query)}`
    )
  } catch {
    suggestions.value = []
  } finally {
    loading.value = false
  }
}

function onSelect(event: { value: CustomerOption }) {
  selectedCustomer.value = event.value
  emit('update:modelValue', event.value.id)
  emit('customer-selected', event.value)
}

function onClear() {
  selectedCustomer.value = null
  emit('update:modelValue', null)
  emit('customer-selected', null)
}

// Загрузить выбранную компанию при инициализации
watch(() => props.modelValue, async (id) => {
  if (id && !selectedCustomer.value) {
    try {
      const c = await api.get<CustomerOption>(`/customers/${id}`)
      selectedCustomer.value = c
    } catch {}
  }
}, { immediate: true })

// --- INN lookup ---

function openInnDialog() {
  innInput.value = ''
  innResult.value = null
  showInnDialog.value = true
}

async function lookupInn() {
  const inn = innInput.value.replace(/\D/g, '')
  if (inn.length < 10) {
    toast.add({ severity: 'warn', summary: 'ИНН должен содержать 10-12 цифр', life: 3000 })
    return
  }
  innLoading.value = true
  try {
    innResult.value = await api.get<DaDataResult>(`/customers/lookup-inn/${inn}`)
  } catch {
    toast.add({ severity: 'error', summary: 'Компания не найдена', detail: `ИНН ${inn} не найден в реестре`, life: 4000 })
    innResult.value = null
  } finally {
    innLoading.value = false
  }
}

async function createFromInn() {
  if (!innResult.value) return
  innCreating.value = true
  try {
    const customer = await api.post<CustomerOption>(
      `/customers/create-by-inn?inn=${innResult.value.inn}`
    )
    selectedCustomer.value = customer
    emit('update:modelValue', customer.id)
    emit('customer-selected', customer)
    showInnDialog.value = false
    toast.add({ severity: 'success', summary: 'Компания создана', detail: customer.name, life: 3000 })
  } catch (e: any) {
    toast.add({ severity: 'error', summary: 'Ошибка', detail: e.message, life: 4000 })
  } finally {
    innCreating.value = false
  }
}

const displayName = computed(() =>
  selectedCustomer.value ? `${selectedCustomer.value.name} (ИНН: ${selectedCustomer.value.inn})` : ''
)
</script>

<template>
  <div class="customer-select">
    <div class="select-row">
      <AutoComplete
        :model-value="displayName"
        :suggestions="suggestions"
        option-label="name"
        :loading="loading"
        placeholder="Начните вводить название или ИНН..."
        class="customer-autocomplete"
        @complete="search"
        @item-select="onSelect"
        @clear="onClear"
      >
        <template #option="{ option }">
          <div class="option-item">
            <div class="option-name">{{ option.name }}</div>
            <div class="option-meta">ИНН {{ option.inn }}<span v-if="option.address"> · {{ option.address.slice(0, 60) }}</span></div>
          </div>
        </template>
        <template #empty>
          <div class="option-empty">Компания не найдена. Попробуйте создать по ИНН →</div>
        </template>
      </AutoComplete>
      <Button
        icon="pi pi-plus"
        severity="secondary"
        outlined
        size="small"
        title="Добавить компанию по ИНН"
        @click="openInnDialog"
      />
    </div>

    <!-- Dialog: создание по ИНН -->
    <Dialog
      v-model:visible="showInnDialog"
      modal
      header="Добавить компанию по ИНН"
      :style="{ width: '500px' }"
    >
      <div class="inn-dialog">
        <div class="inn-input-row">
          <InputText
            v-model="innInput"
            placeholder="Введите ИНН (10 или 12 цифр)"
            inputmode="numeric"
            class="inn-field"
            @keydown.enter="lookupInn"
          />
          <Button
            label="Найти"
            icon="pi pi-search"
            size="small"
            :loading="innLoading"
            @click="lookupInn"
          />
        </div>

        <div v-if="innResult" class="inn-result">
          <div class="result-row"><span class="label">Название:</span> <b>{{ innResult.name }}</b></div>
          <div class="result-row"><span class="label">ИНН:</span> {{ innResult.inn }}</div>
          <div class="result-row" v-if="innResult.kpp"><span class="label">КПП:</span> {{ innResult.kpp }}</div>
          <div class="result-row" v-if="innResult.ogrn"><span class="label">ОГРН:</span> {{ innResult.ogrn }}</div>
          <div class="result-row" v-if="innResult.address"><span class="label">Адрес:</span> {{ innResult.address }}</div>
          <div class="result-row" v-if="innResult.director"><span class="label">Директор:</span> {{ innResult.director }}</div>
          <div class="result-row" v-if="innResult.opf"><span class="label">Форма:</span> {{ innResult.opf }}</div>
          <div class="result-row" v-if="innResult.status">
            <span class="label">Статус:</span>
            <span :class="innResult.status === 'ACTIVE' ? 'status-active' : 'status-inactive'">
              {{ innResult.status === 'ACTIVE' ? 'Действующая' : innResult.status }}
            </span>
          </div>
        </div>
      </div>

      <template #footer>
        <Button label="Отмена" severity="secondary" text @click="showInnDialog = false" />
        <Button
          v-if="innResult"
          label="Создать компанию"
          icon="pi pi-check"
          :loading="innCreating"
          @click="createFromInn"
        />
      </template>
    </Dialog>
  </div>
</template>

<style scoped>
.customer-select { width: 100%; }
.select-row { display: flex; gap: 6px; align-items: flex-start; }
.customer-autocomplete { flex: 1; }

.option-item { padding: 4px 0; }
.option-name { font-weight: 500; color: #1e293b; font-size: 14px; }
.option-meta { font-size: 12px; color: #64748b; margin-top: 2px; }
.option-empty { font-size: 13px; color: #94a3b8; padding: 8px; }

.inn-dialog { display: flex; flex-direction: column; gap: 16px; }
.inn-input-row { display: flex; gap: 8px; }
.inn-field { flex: 1; }

.inn-result {
  background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px;
  padding: 14px; display: flex; flex-direction: column; gap: 6px;
}
.result-row { font-size: 14px; color: #334155; }
.result-row .label { color: #94a3b8; min-width: 90px; display: inline-block; }
.status-active { color: #059669; font-weight: 600; }
.status-inactive { color: #dc2626; font-weight: 600; }
</style>

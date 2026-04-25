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
  is_permanent_client?: boolean
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

// DaData suggestions (если не найдено среди своих)
interface DaDataSuggestion {
  name: string; inn: string; address: string; ogrn: string; status: string
}
const dadataSuggestions = ref<DaDataSuggestion[]>([])
const showDadataResults = ref(false)
const dadataLoading = ref(false)

async function search(event: { query: string }) {
  if (event.query.length < 1) return
  loading.value = true
  showDadataResults.value = false
  dadataSuggestions.value = []
  try {
    const results = await api.get<CustomerOption[]>(
      `/customers/search?q=${encodeURIComponent(event.query)}`
    )
    // Постоянные клиенты — наверх (бэкенд уже сортирует так же,
    // дублируем на фронте на случай если порядок изменится).
    suggestions.value = [...results].sort((a, b) =>
      Number(b.is_permanent_client ?? false) - Number(a.is_permanent_client ?? false)
    )

    // Если среди постоянных клиентов мало/нет результатов и запрос >= 3 символов
    // показываем кнопку «Искать в DaData»
    if (results.length < 3 && event.query.length >= 3) {
      showDadataResults.value = true
      // Подгружаем из DaData параллельно
      dadataLoading.value = true
      try {
        dadataSuggestions.value = await api.get<DaDataSuggestion[]>(
          `/customers/dadata-search?q=${encodeURIComponent(event.query)}`
        )
      } catch { dadataSuggestions.value = [] }
      finally { dadataLoading.value = false }
    }
  } catch {
    suggestions.value = []
  } finally {
    loading.value = false
  }
}

async function addFromDadata(dadata: DaDataSuggestion) {
  innCreating.value = true
  try {
    const customer = await api.post<CustomerOption>(
      `/customers/create-by-inn?inn=${dadata.inn}`
    )
    selectedCustomer.value = customer
    emit('update:modelValue', customer.id)
    emit('customer-selected', customer)
    showDadataResults.value = false
    toast.add({ severity: 'success', summary: 'Компания добавлена', detail: customer.name, life: 3000 })
  } catch (e: any) {
    toast.add({ severity: 'error', summary: 'Ошибка', detail: e.message, life: 4000 })
  } finally {
    innCreating.value = false
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
            <div class="option-name">
              {{ option.name }}
              <span
                v-if="option.is_permanent_client"
                class="option-permanent-badge"
                title="Постоянный клиент (синхронизирован из Bitrix24)"
              >
                <i class="pi pi-star-fill" /> Постоянный
              </span>
            </div>
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

    <!-- DaData результаты (если мало среди своих) -->
    <div v-if="showDadataResults && dadataSuggestions.length" class="dadata-results">
      <div class="dadata-header">
        <i class="pi pi-search" />
        Найдено в реестре (ФНС):
      </div>
      <button
        v-for="d in dadataSuggestions"
        :key="d.inn"
        type="button"
        class="dadata-item"
        :disabled="innCreating"
        @click="addFromDadata(d)"
      >
        <div class="dadata-name">{{ d.name }}</div>
        <div class="dadata-meta">ИНН {{ d.inn }}<span v-if="d.address"> · {{ d.address.slice(0, 50) }}</span></div>
        <i class="pi pi-plus-circle dadata-add" />
      </button>
    </div>
    <div v-else-if="showDadataResults && dadataLoading" class="dadata-loading">
      <i class="pi pi-spin pi-spinner" /> Поиск в реестре ФНС...
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
.option-name {
  font-weight: 500; color: #1e293b; font-size: 14px;
  display: flex; align-items: center; gap: 8px; flex-wrap: wrap;
}
.option-permanent-badge {
  display: inline-flex; align-items: center; gap: 4px;
  font-size: 11px; font-weight: 500; color: #b45309;
  background: #fef3c7; border: 1px solid #fde68a;
  border-radius: 999px; padding: 2px 8px; line-height: 1.2;
}
.option-permanent-badge .pi { font-size: 10px; color: #d97706; }
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

/* DaData results */
.dadata-results {
  margin-top: 8px; border: 1px solid #e0f2fe; border-radius: 8px;
  background: #f0f9ff; overflow: hidden;
}
.dadata-header {
  padding: 8px 12px; font-size: 12px; font-weight: 600; color: #0369a1;
  display: flex; align-items: center; gap: 6px;
  border-bottom: 1px solid #bae6fd;
}
.dadata-item {
  display: flex; align-items: center; gap: 8px; width: 100%;
  padding: 8px 12px; border: none; background: white; cursor: pointer;
  text-align: left; font-family: inherit; border-bottom: 1px solid #f0f9ff;
  transition: background 0.15s;
}
.dadata-item:hover { background: #e0f2fe; }
.dadata-item:last-child { border-bottom: none; }
.dadata-name { font-size: 13px; font-weight: 500; color: #1e293b; flex: 1; }
.dadata-meta { font-size: 11px; color: #64748b; flex: 1; }
.dadata-add { color: #0ea5e9; font-size: 16px; flex-shrink: 0; }
.dadata-loading {
  margin-top: 6px; font-size: 12px; color: #64748b;
  display: flex; align-items: center; gap: 6px;
}
</style>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import Card from 'primevue/card'
import InputText from 'primevue/inputtext'
import Textarea from 'primevue/textarea'
import Select from 'primevue/select'
import Checkbox from 'primevue/checkbox'
import Button from 'primevue/button'
import Divider from 'primevue/divider'
import { useToast } from 'primevue/usetoast'
import { useTicketsStore } from '../stores/tickets'
import { api, isAuthenticated } from '../api/client'
import { useAuthStore } from '../stores/auth'
import type { TicketCreate, TicketProduct, TicketCategory, TicketType } from '../types'

const router = useRouter()
const route = useRoute()
const toast = useToast()
const store = useTicketsStore()
const auth = useAuthStore()

const step = ref<1 | 2>(1)
const submitted = ref(false)
const ticketCreated = ref(false)
const createdTicketId = ref('')

// Агент/админ может создать заявку от имени клиента
const isStaff = computed(() =>
  auth.user?.role === 'support_agent' || auth.user?.role === 'admin'
)
// Для агентов/админов по умолчанию включаем режим "от имени клиента"
const onBehalfOfMode = ref(
  auth.user?.role === 'support_agent' || auth.user?.role === 'admin'
)

// Если включён режим "от имени клиента" — поля пустые
const email = ref(onBehalfOfMode.value ? '' : (auth.user?.email || ''))
const contactName = ref(onBehalfOfMode.value ? '' : (auth.user?.full_name || ''))

// ------------------------------------------------------------------
// Телефон: отдельный код страны + цифры. Хранение: +<code><digits>
// ------------------------------------------------------------------
interface CountryCode {
  code: string         // "+7"
  flag: string         // "🇷🇺"
  name: string         // "Россия"
  length: number       // макс. цифр после кода
}

const countryCodes: CountryCode[] = [
  { code: '+7',   flag: '🇷🇺', name: 'Россия / Казахстан',  length: 10 },
  { code: '+375', flag: '🇧🇾', name: 'Беларусь',            length: 9  },
  { code: '+380', flag: '🇺🇦', name: 'Украина',             length: 9  },
  { code: '+374', flag: '🇦🇲', name: 'Армения',             length: 8  },
  { code: '+994', flag: '🇦🇿', name: 'Азербайджан',         length: 9  },
  { code: '+995', flag: '🇬🇪', name: 'Грузия',              length: 9  },
  { code: '+996', flag: '🇰🇬', name: 'Киргизия',            length: 9  },
  { code: '+992', flag: '🇹🇯', name: 'Таджикистан',         length: 9  },
  { code: '+993', flag: '🇹🇲', name: 'Туркменистан',        length: 8  },
  { code: '+998', flag: '🇺🇿', name: 'Узбекистан',          length: 9  },
  { code: '+373', flag: '🇲🇩', name: 'Молдова',             length: 8  },
  { code: '+371', flag: '🇱🇻', name: 'Латвия',              length: 8  },
  { code: '+370', flag: '🇱🇹', name: 'Литва',               length: 8  },
  { code: '+372', flag: '🇪🇪', name: 'Эстония',             length: 8  },
  { code: '+1',   flag: '🇺🇸', name: 'США / Канада',        length: 10 },
  { code: '+44',  flag: '🇬🇧', name: 'Великобритания',      length: 10 },
  { code: '+49',  flag: '🇩🇪', name: 'Германия',            length: 11 },
  { code: '+33',  flag: '🇫🇷', name: 'Франция',             length: 9  },
  { code: '+39',  flag: '🇮🇹', name: 'Италия',              length: 10 },
  { code: '+34',  flag: '🇪🇸', name: 'Испания',             length: 9  },
  { code: '+48',  flag: '🇵🇱', name: 'Польша',              length: 9  },
  { code: '+420', flag: '🇨🇿', name: 'Чехия',               length: 9  },
  { code: '+86',  flag: '🇨🇳', name: 'Китай',               length: 11 },
  { code: '+90',  flag: '🇹🇷', name: 'Турция',              length: 10 },
  { code: '+972', flag: '🇮🇱', name: 'Израиль',             length: 9  },
  { code: '+971', flag: '🇦🇪', name: 'ОАЭ',                 length: 9  },
]

const countryCode = ref<CountryCode>(countryCodes[0])  // default: +7 Россия
const phoneDigits = ref('')  // только цифры, без формата

function onPhoneDigitsInput(e: Event) {
  const input = e.target as HTMLInputElement
  // Оставляем только цифры + ограничиваем длину для страны
  const clean = input.value.replace(/\D/g, '').slice(0, countryCode.value.length)
  phoneDigits.value = clean
  // Не трогаем курсор — браузер сам обработает, т.к. мы просто отфильтровали
  if (input.value !== clean) {
    input.value = clean
  }
}

function normalizePhone(): string {
  // Возвращает +<code><digits> или пустую строку
  if (!phoneDigits.value) return ''
  if (phoneDigits.value.length < countryCode.value.length) return ''
  return countryCode.value.code + phoneDigits.value
}

function toggleBehalfMode() {
  onBehalfOfMode.value = !onBehalfOfMode.value
  phoneDigits.value = ''
  if (onBehalfOfMode.value) {
    // Переключились в режим "от имени клиента" — очищаем поля
    email.value = ''
    contactName.value = ''
  } else {
    // От своего имени — подставляем данные агента
    email.value = auth.user?.email || ''
    contactName.value = auth.user?.full_name || ''
  }
}

interface QuickCard {
  id: string
  icon: string
  label: string
  hint: string
  defaults: Partial<TicketCreate>
}

const quickCards: QuickCard[] = [
  { id: 'cant_enter', icon: 'pi pi-sign-in', label: 'Не могу попасть / проехать', hint: 'Дверь или шлагбаум не открывается', defaults: { product: 'pass24_online', category: 'passes', urgent: true, ticket_type: 'incident' } },
  { id: 'app_problem', icon: 'pi pi-mobile', label: 'Проблема с приложением', hint: 'Вылетает, не загружается, ошибка', defaults: { product: 'mobile_app', category: 'app_issues' } },
  { id: 'mobile_key', icon: 'pi pi-key', label: 'Мобильный ключ', hint: 'BLE-ключ не работает, не активируется', defaults: { product: 'pass24_key' } },
  { id: 'auto_recognition', icon: 'pi pi-car', label: 'Шлагбаум / номера', hint: 'Камера не распознаёт, шлагбаум не поднимается', defaults: { product: 'pass24_auto', category: 'recognition' } },
  { id: 'pass_problem', icon: 'pi pi-id-card', label: 'Проблема с пропуском', hint: 'Не создаётся, не работает, отклонён', defaults: { product: 'pass24_online', category: 'passes' } },
  { id: 'equipment', icon: 'pi pi-cog', label: 'Оборудование', hint: 'Считыватель, контроллер, камера', defaults: { product: 'equipment', category: 'equipment_issues' } },
  { id: 'consultation', icon: 'pi pi-question-circle', label: 'Вопрос / консультация', hint: 'Как настроить, как работает', defaults: { ticket_type: 'question', category: 'consultation' } },
  { id: 'feature', icon: 'pi pi-lightbulb', label: 'Предложение', hint: 'Идея по улучшению системы', defaults: { ticket_type: 'feature_request', category: 'feature_request' } },
  { id: 'other', icon: 'pi pi-box', label: 'Другое', hint: 'Не нашли нужную тему', defaults: { product: 'other' } },
]

const selectedCardId = ref<string | null>(null)

// Form fields
const title = ref('')
const description = ref('')

// KB suggestions — статьи базы знаний, релевантные теме заявки
interface KbSuggestion { title: string; slug: string; category: string }
const kbSuggestions = ref<KbSuggestion[]>([])
let kbDebounceTimer: ReturnType<typeof setTimeout> | null = null

async function searchKb(query: string) {
  if (query.trim().length < 4) { kbSuggestions.value = []; return }
  try {
    const data = await api.get<{ items: KbSuggestion[] }>(
      `/knowledge/search?query=${encodeURIComponent(query)}&per_page=3`
    )
    kbSuggestions.value = data.items || []
  } catch { kbSuggestions.value = [] }
}

import { watch as watchRef } from 'vue'
watchRef(title, (q) => {
  if (kbDebounceTimer) clearTimeout(kbDebounceTimer)
  kbDebounceTimer = setTimeout(() => searchKb(q), 400)
})

function openArticle(slug: string) {
  window.open(`/knowledge/${slug}`, '_blank')
}
const product = ref<TicketProduct | undefined>(undefined)
const category = ref<TicketCategory | undefined>(undefined)
const ticketType = ref<TicketType | undefined>(undefined)
const objectName = ref('')
const accessPoint = ref('')
const company = ref('')
const deviceType = ref<string | undefined>(undefined)
const urgent = ref(false)

const productOptions = [
  { label: 'PASS24.online (веб-портал)', value: 'pass24_online' },
  { label: 'Мобильное приложение', value: 'mobile_app' },
  { label: 'PASS24.Key (BLE-ключи)', value: 'pass24_key' },
  { label: 'PASS24.control (СКУД)', value: 'pass24_control' },
  { label: 'PASS24.auto (номера авто)', value: 'pass24_auto' },
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
  { label: 'Инцидент — нарушение работы сервиса', value: 'incident' },
  { label: 'Проблема — корневая причина', value: 'problem' },
  { label: 'Service Request — стандартный запрос', value: 'service_request' },
  { label: 'Change Request — изменение системы', value: 'change_request' },
  { label: 'Вопрос — нужна консультация', value: 'question' },
  { label: 'Предложение — идея по улучшению', value: 'feature_request' },
]

const deviceTypeOptions = [
  { label: 'iPhone (iOS)', value: 'ios' },
  { label: 'Android', value: 'android' },
  { label: 'Веб-браузер', value: 'web' },
  { label: 'Другое', value: 'other' },
]

const showDeviceType = computed(() =>
  product.value === 'mobile_app' || product.value === 'pass24_key',
)

// Validation
const emailInvalid = computed(() => submitted.value && (!email.value.trim() || !email.value.match(/^[^\s@]+@[^\s@]+\.[^\s@]+$/)))
const titleInvalid = computed(() => submitted.value && !title.value.trim())
const descriptionInvalid = computed(() => submitted.value && !description.value.trim())

function selectCard(card: QuickCard) {
  selectedCardId.value = card.id
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

// Если пришёл из статьи БЗ — фиксируем это
const fromArticleSlug = ref<string | null>(null)
const fromArticleTitle = ref<string | null>(null)

onMounted(() => {
  const q = route.query
  if (q.from_article) {
    fromArticleSlug.value = q.from_article as string
    // title может содержать "По статье: XXX" — достанем из него название
    const articleTitle = (q.title as string) || ''
    const match = articleTitle.match(/^По статье:\s*(.+)$/)
    fromArticleTitle.value = match ? match[1] : articleTitle
    // Скипаем Step 1 — мы знаем контекст
    step.value = 2
  }
  if (q.title || q.description) {
    title.value = (q.title as string) || ''
    description.value = (q.description as string) || ''
    if (q.product) product.value = q.product as any
    if (q.category) category.value = q.category as any
    if (q.ticket_type) ticketType.value = q.ticket_type as any
    step.value = 2
  }
  // Pre-fill email from auth (только если НЕ режим "от имени клиента")
  if (auth.user && !onBehalfOfMode.value) {
    email.value = auth.user.email
    contactName.value = auth.user.full_name
  }
})

async function onSubmit() {
  submitted.value = true
  if (emailInvalid.value || titleInvalid.value || descriptionInvalid.value) return

  // Всегда через guest endpoint если не авторизован
  if (!isAuthenticated()) {
    try {
      const resp = await api.post<{ ticket_id: string }>('/tickets/guest', {
        email: email.value.trim(),
        name: contactName.value.trim() || undefined,
        title: title.value.trim(),
        description: description.value.trim(),
        product: product.value,
        category: category.value,
        ticket_type: ticketType.value,
        object_name: objectName.value.trim() || undefined,
        contact_phone: normalizePhone() || undefined,
        urgent: urgent.value,
        source_article_slug: fromArticleSlug.value || undefined,
      } as any)
      ticketCreated.value = true
      createdTicketId.value = resp.ticket_id.slice(0, 8)
      toast.add({ severity: 'success', summary: 'Заявка создана', detail: `Обновления на ${email.value}`, life: 5000 })
    } catch (e: any) {
      toast.add({ severity: 'error', summary: 'Ошибка', detail: e.message || 'Не удалось создать', life: 4000 })
    }
    return
  }

  // Авторизован
  try {
    // Агент/админ создаёт от имени клиента — если email или имя отличаются
    const creatingOnBehalf = isStaff.value && onBehalfOfMode.value &&
      email.value.trim() && email.value.trim().toLowerCase() !== auth.user?.email.toLowerCase()

    const ticket = await store.createTicket({
      title: title.value.trim(),
      description: description.value.trim(),
      product: product.value,
      category: category.value,
      ticket_type: ticketType.value,
      object_name: objectName.value.trim() || undefined,
      access_point: accessPoint.value.trim() || undefined,
      contact_phone: normalizePhone() || undefined,
      contact_name: creatingOnBehalf ? contactName.value.trim() || undefined : undefined,
      company: company.value.trim() || undefined,
      device_type: showDeviceType.value ? deviceType.value : undefined,
      urgent: urgent.value,
      on_behalf_of_email: creatingOnBehalf ? email.value.trim() : undefined,
      on_behalf_of_name: creatingOnBehalf ? contactName.value.trim() || undefined : undefined,
      source_article_slug: fromArticleSlug.value || undefined,
    })
    toast.add({ severity: 'success', summary: 'Заявка создана', life: 3000 })
    router.push(`/tickets/${ticket.id}`)
  } catch (e: any) {
    toast.add({ severity: 'error', summary: 'Ошибка', detail: e.message, life: 4000 })
  }
}
</script>

<template>
  <div class="create-ticket-page">
    <Button label="На главную" icon="pi pi-arrow-left" severity="secondary" text class="back-button" @click="router.push('/')" />

    <!-- Step 1: Quick cards -->
    <div v-if="step === 1" class="step-1">
      <h2 class="step-title">Что случилось?</h2>
      <p class="step-subtitle">Выберите тему — мы подберём нужную категорию автоматически</p>

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
          <span class="quick-card-hint">{{ card.hint }}</span>
        </div>
      </div>
    </div>

    <!-- Step 2: Form -->
    <div v-if="step === 2" class="step-2">
      <Button
        v-if="!fromArticleSlug"
        label="Назад к выбору темы" icon="pi pi-arrow-left"
        severity="secondary" text class="back-to-step1"
        @click="goBackToStep1"
      />

      <!-- Баннер: пришёл из статьи БЗ -->
      <div v-if="fromArticleSlug" class="from-article-banner">
        <i class="pi pi-book banner-icon" />
        <div class="banner-content">
          <div class="banner-title">Вы пишете по статье базы знаний</div>
          <div class="banner-subtitle">
            «{{ fromArticleTitle }}» — если статья не помогла,
            опишите подробнее вопрос и мы улучшим материал
          </div>
        </div>
        <a
          :href="`/knowledge/${fromArticleSlug}`"
          target="_blank"
          class="banner-link"
        >Открыть статью</a>
      </div>

      <Card class="create-card">
        <template #title>Новая заявка</template>
        <template #content>
          <!-- Success -->
          <div v-if="ticketCreated" class="ticket-success">
            <div class="success-icon"><i class="pi pi-check-circle" /></div>
            <h3>Заявка создана!</h3>
            <p>Номер: <strong>{{ createdTicketId }}</strong></p>
            <p>Обновления придут на <strong>{{ email }}</strong></p>
            <p class="success-hint">Вы можете отвечать на письма — ответы станут комментариями к заявке.</p>
            <Divider />
            <p class="success-register">Хотите отслеживать все заявки на портале в реальном времени?</p>
            <Button label="Зарегистрироваться" icon="pi pi-user-plus" severity="secondary" outlined @click="router.push('/register')" />
            <Button label="На главную" text severity="secondary" @click="router.push('/')" class="ml-2" />
          </div>

          <form v-else class="ticket-form" @submit.prevent="onSubmit">
            <!-- Email — обязательно для всех -->
            <div class="form-section-title">
              <i class="pi pi-envelope section-icon" /> Контактные данные
              <Button
                v-if="isStaff"
                :label="onBehalfOfMode ? 'От своего имени' : 'От имени клиента'"
                :icon="onBehalfOfMode ? 'pi pi-user' : 'pi pi-users'"
                size="small"
                severity="secondary"
                :outlined="!onBehalfOfMode"
                class="behalf-toggle"
                type="button"
                @click="toggleBehalfMode"
              />
            </div>

            <div v-if="onBehalfOfMode && isStaff" class="behalf-hint">
              Укажите контактные данные клиента — на этот email придут уведомления о заявке.
            </div>

            <div class="field">
              <label for="email">Электронная почта клиента <span class="required">*</span></label>
              <InputText
                id="email"
                v-model="email"
                type="email"
                :invalid="emailInvalid"
                :disabled="!!auth.user && !onBehalfOfMode"
                fluid
              />
              <small class="field-help">На этот адрес придёт подтверждение и все обновления по заявке. Можно отвечать прямо на письма.</small>
              <small v-if="emailInvalid" class="field-error">Укажите корректный email — это обязательное поле</small>
            </div>

            <div class="form-row">
              <div class="field">
                <label for="contactName">Имя клиента</label>
                <InputText
                  id="contactName"
                  v-model="contactName"
                  :disabled="!!auth.user && !onBehalfOfMode"
                  fluid
                />
                <small class="field-help">Как обращаться в переписке</small>
              </div>
              <div class="field">
                <label for="contactPhone">Телефон</label>
                <div class="phone-input-group">
                  <Select
                    v-model="countryCode"
                    :options="countryCodes"
                    option-label="code"
                    class="country-code-select"
                  >
                    <template #value="{ value }">
                      <span v-if="value" class="country-value">
                        <span class="flag">{{ value.flag }}</span>
                        <span>{{ value.code }}</span>
                      </span>
                    </template>
                    <template #option="{ option }">
                      <span class="country-option">
                        <span class="flag">{{ option.flag }}</span>
                        <span class="code">{{ option.code }}</span>
                        <span class="name">{{ option.name }}</span>
                      </span>
                    </template>
                  </Select>
                  <InputText
                    id="contactPhone"
                    :model-value="phoneDigits"
                    @input="onPhoneDigitsInput"
                    inputmode="tel"
                    class="phone-digits-input"
                  />
                </div>
                <small class="field-help">Для срочной связи — выберите страну и введите номер ({{ countryCode.length }} цифр)</small>
              </div>
            </div>

            <Divider />

            <!-- Описание -->
            <div class="form-section-title"><i class="pi pi-file-edit section-icon" /> Описание проблемы</div>

            <div class="field">
              <label for="title">Тема заявки <span class="required">*</span></label>
              <InputText
                id="title"
                v-model="title"
                :invalid="titleInvalid"
                fluid
              />
              <div v-if="kbSuggestions.length" class="kb-suggestions">
                <div class="kb-hint">💡 Возможно, эти статьи помогут решить проблему:</div>
                <button
                  v-for="s in kbSuggestions" :key="s.slug"
                  type="button"
                  class="kb-suggestion-item"
                  @click="openArticle(s.slug)"
                >
                  <i class="pi pi-book" />
                  <span>{{ s.title }}</span>
                  <i class="pi pi-external-link" />
                </button>
              </div>
              <small class="field-help">Кратко опишите суть проблемы — например: «Не открывается дверь в подъезд 3»</small>
              <small v-if="titleInvalid" class="field-error">Укажите тему — без неё не получится создать заявку</small>
            </div>

            <div class="field">
              <label for="description">Подробное описание <span class="required">*</span></label>
              <Textarea
                id="description"
                v-model="description"
                :invalid="descriptionInvalid"
                rows="4"
                auto-resize
                fluid
              />
              <small class="field-help">Что произошло? Когда? Что уже пробовали? Какую ошибку видите?</small>
              <small v-if="descriptionInvalid" class="field-error">Опишите проблему подробнее</small>
            </div>

            <Divider />

            <!-- Объект -->
            <div class="form-section-title"><i class="pi pi-building section-icon" /> Где проблема</div>

            <div class="form-row">
              <div class="field">
                <label for="objectName">Название объекта</label>
                <InputText id="objectName" v-model="objectName" fluid />
                <small class="field-help">Жилой комплекс, бизнес-центр или коттеджный посёлок — например: ЖК Солнечный</small>
              </div>
              <div class="field">
                <label for="accessPoint">Точка доступа</label>
                <InputText id="accessPoint" v-model="accessPoint" fluid />
                <small class="field-help">Конкретная дверь, шлагбаум или КПП — например: КПП-1, подъезд 3</small>
              </div>
            </div>

            <Divider />

            <!-- Классификация (складываемая) -->
            <div class="form-section-title"><i class="pi pi-tag section-icon" /> Классификация</div>

            <div class="form-row">
              <div class="field">
                <label for="product">Продукт</label>
                <Select id="product" v-model="product" :options="productOptions" option-label="label" option-value="value" fluid />
                <small class="field-help">Какой продукт затронут. Если не уверены — оставьте пустым, определим сами</small>
              </div>
              <div class="field">
                <label for="category">Категория</label>
                <Select id="category" v-model="category" :options="categoryOptions" option-label="label" option-value="value" fluid />
                <small class="field-help">Тип проблемы — помогает направить заявку нужному специалисту</small>
              </div>
            </div>

            <div class="form-row">
              <div class="field">
                <label for="ticketType">Тип обращения</label>
                <Select id="ticketType" v-model="ticketType" :options="ticketTypeOptions" option-label="label" option-value="value" fluid />
                <small class="field-help">Инцидент — срочно, всё сломалось. Вопрос — нужна консультация</small>
              </div>
              <div class="field" v-if="showDeviceType">
                <label for="deviceType">Устройство</label>
                <Select id="deviceType" v-model="deviceType" :options="deviceTypeOptions" option-label="label" option-value="value" fluid />
                <small class="field-help">На каком устройстве проблема — поможет воспроизвести</small>
              </div>
              <div class="field" v-if="!showDeviceType">
                <label for="company">Компания / УК</label>
                <InputText id="company" v-model="company" fluid />
                <small class="field-help">Название управляющей компании — например: ООО «Управляющая компания»</small>
              </div>
            </div>

            <Divider />

            <!-- Срочность -->
            <div class="field-check urgent-check">
              <Checkbox v-model="urgent" input-id="urgent" :binary="true" />
              <div>
                <label for="urgent">Не могу попасть / проехать прямо сейчас</label>
                <small class="field-help-inline">Отметьте, если вы заблокированы — мы отреагируем в первую очередь</small>
              </div>
            </div>

            <!-- Submit -->
            <div class="form-actions">
              <Button label="Отмена" severity="secondary" outlined @click="router.push('/')" />
              <Button type="submit" label="Создать заявку" icon="pi pi-check" :loading="store.loading" />
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

.back-button { align-self: flex-start; }

.step-title { font-size: 1.5rem; font-weight: 600; margin: 0; }
.step-subtitle { font-size: 0.95rem; color: #64748b; margin: 4px 0 16px; }

/* Quick cards */
.quick-cards-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; }
@media (max-width: 768px) { .quick-cards-grid { grid-template-columns: repeat(2, 1fr); } }
@media (max-width: 480px) { .quick-cards-grid { grid-template-columns: 1fr; } }

.quick-card {
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  gap: 6px; padding: 18px 14px; border: 1px solid #e2e8f0; border-radius: 12px;
  background: white; cursor: pointer; transition: all 0.2s; text-align: center; min-height: 110px;
}
.quick-card:hover { border-color: #3b82f6; background: #eff6ff; transform: translateY(-2px); box-shadow: 0 4px 12px rgba(0,0,0,0.06); }
.quick-card.selected { border-color: #3b82f6; background: #eff6ff; }
.quick-card-icon { font-size: 24px; color: #3b82f6; }
.quick-card-label { font-size: 14px; font-weight: 600; color: #1e293b; }
.quick-card-hint { font-size: 12px; color: #94a3b8; line-height: 1.3; }

/* Step 2 */
.back-to-step1 { align-self: flex-start; margin-bottom: -8px; }

/* Баннер "из статьи БЗ" */
.from-article-banner {
  display: flex; align-items: center; gap: 12px;
  background: linear-gradient(135deg, #eff6ff 0%, #dbeafe 100%);
  border: 1px solid #93c5fd; border-radius: 10px;
  padding: 12px 16px; margin-bottom: 4px;
}
.banner-icon { font-size: 22px; color: #2563eb; flex-shrink: 0; }
.banner-content { flex: 1; min-width: 0; }
.banner-title { font-weight: 600; font-size: 14px; color: #1e293b; }
.banner-subtitle { font-size: 12px; color: #475569; margin-top: 2px; line-height: 1.4; }
.banner-link {
  font-size: 12px; font-weight: 500; color: #2563eb;
  text-decoration: none; padding: 6px 10px;
  border: 1px solid #93c5fd; border-radius: 6px; background: white;
  white-space: nowrap; transition: background 0.15s;
}
.banner-link:hover { background: #dbeafe; }

/* Success */
.ticket-success { text-align: center; padding: 24px 0; }
.success-icon { font-size: 48px; color: #22c55e; margin-bottom: 12px; }
.ticket-success h3 { margin: 0 0 8px; color: #1e293b; }
.ticket-success p { color: #475569; margin: 4px 0; }
.success-hint { font-size: 13px; color: #64748b !important; margin-top: 8px !important; }
.success-register { font-weight: 600; color: #1e293b !important; margin-bottom: 12px !important; }
.ml-2 { margin-left: 8px; }

/* Form */
.ticket-form { display: flex; flex-direction: column; gap: 16px; }

.form-section-title {
  font-size: 15px; font-weight: 600; color: #1e293b;
  display: flex; align-items: center; gap: 8px; margin-bottom: -4px;
}
.section-icon { font-size: 16px; color: #3b82f6; }
.behalf-toggle { margin-left: auto; }
.behalf-hint {
  font-size: 13px; color: #0369a1; background: #f0f9ff;
  border: 1px solid #bae6fd; border-radius: 8px; padding: 10px 12px;
}

/* Phone input: country code + digits */
.phone-input-group {
  display: flex;
  gap: 6px;
  align-items: stretch;
}
.country-code-select { flex: 0 0 auto; min-width: 100px; }
.phone-digits-input { flex: 1; }
.country-value {
  display: inline-flex; align-items: center; gap: 6px;
  font-variant-numeric: tabular-nums;
}
.country-option {
  display: inline-flex; align-items: center; gap: 8px;
  white-space: nowrap;
}
.country-option .flag { font-size: 18px; }
.country-option .code { font-weight: 600; color: #1e293b; min-width: 48px; }
.country-option .name { font-size: 13px; color: #64748b; }
.country-value .flag { font-size: 16px; }

.field { display: flex; flex-direction: column; gap: 4px; }
.field label { font-weight: 500; font-size: 14px; color: #334155; }
.required { color: #ef4444; }

.field-help { font-size: 12px; color: #94a3b8; line-height: 1.4; }

/* KB suggestions */
.kb-suggestions {
  margin-top: 8px; display: flex; flex-direction: column; gap: 4px;
  padding: 10px 12px; background: #f0f9ff;
  border: 1px solid #bae6fd; border-radius: 8px;
}
.kb-hint { font-size: 12px; color: #0369a1; font-weight: 600; margin-bottom: 4px; }
.kb-suggestion-item {
  display: flex; align-items: center; gap: 8px;
  background: white; border: 1px solid #e0f2fe; border-radius: 6px;
  padding: 6px 10px; font-size: 13px; color: #075985;
  cursor: pointer; font-family: inherit; text-align: left;
  transition: background 0.15s, border-color 0.15s;
}
.kb-suggestion-item:hover { background: #e0f2fe; border-color: #7dd3fc; }
.kb-suggestion-item .pi-external-link { margin-left: auto; font-size: 11px; }
.field-error { font-size: 12px; color: #ef4444; }

.form-row { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
@media (max-width: 600px) { .form-row { grid-template-columns: 1fr; } }

.field-check { display: flex; align-items: flex-start; gap: 10px; }
.field-check label { font-weight: 500; font-size: 14px; cursor: pointer; color: #1e293b; }
.field-help-inline { display: block; font-size: 12px; color: #94a3b8; margin-top: 2px; }
.urgent-check { background: #fef2f2; border: 1px solid #fecaca; border-radius: 10px; padding: 12px 14px; }

.form-actions { display: flex; justify-content: flex-end; gap: 12px; margin-top: 8px; }
</style>

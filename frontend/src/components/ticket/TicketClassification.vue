<script setup lang="ts">
defineProps<{
  product: string | null
  ticketType: string | null
  source: string | null
}>()

const productLabels: Record<string, string> = {
  pass24_online: 'PASS24',
  mobile_app: 'Мобильное приложение',
  pass24_key: 'PASS24.Key',
  pass24_control: 'PASS24.control',
  pass24_auto: 'PASS24.auto',
  equipment: 'Оборудование',
  integration: 'Интеграция',
  other: 'Другое',
}

const typeLabels: Record<string, string> = {
  incident: 'Инцидент',
  problem: 'Проблема',
  question: 'Вопрос',
  service_request: 'Запрос',
  feature_request: 'Предложение',
}

const sourceLabels: Record<string, string> = {
  web: 'Веб-портал',
  email: 'Email',
  telegram: 'Telegram',
  api: 'API',
  phone: 'Телефон',
}
</script>

<template>
  <div class="ticket-classification">
    <div v-if="product" class="info-row">
      <span class="info-label">Продукт</span>
      <span class="info-value">{{ productLabels[product] || product }}</span>
    </div>
    <div v-if="ticketType" class="info-row">
      <span class="info-label">Тип заявки</span>
      <span class="info-value">{{ typeLabels[ticketType] || ticketType }}</span>
    </div>
    <div v-if="source" class="info-row">
      <span class="info-label">Источник</span>
      <span class="info-value">{{ sourceLabels[source] || source }}</span>
    </div>
    <div v-if="!product && !ticketType && !source" class="info-empty">
      Классификация не указана
    </div>
  </div>
</template>

<style scoped>
.ticket-classification {
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
</style>

<script setup lang="ts">
defineProps<{
  contactName: string | null
  contactEmail: string | null
  contactPhone: string | null
  company: string | null
}>()
</script>

<template>
  <div class="ticket-contact-info">
    <div v-if="contactName" class="info-row">
      <span class="info-label">Контакт</span>
      <span class="info-value">{{ contactName }}</span>
    </div>
    <div v-if="contactEmail" class="info-row">
      <span class="info-label">Email</span>
      <a :href="`mailto:${contactEmail}`" class="info-link">{{ contactEmail }}</a>
    </div>
    <div v-if="contactPhone" class="info-row">
      <span class="info-label">Телефон</span>
      <a :href="`tel:${contactPhone}`" class="info-link">{{ contactPhone }}</a>
    </div>
    <div v-if="company" class="info-row">
      <span class="info-label">Компания</span>
      <span class="info-value">{{ company }}</span>
    </div>
    <div v-if="!contactName && !contactEmail && !contactPhone && !company" class="info-empty">
      Контактная информация не указана
    </div>
  </div>
</template>

<style scoped>
.ticket-contact-info {
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

.info-link {
  font-size: 0.875rem;
  color: #3b82f6;
  text-decoration: none;
}

.info-link:hover {
  text-decoration: underline;
}

.info-empty {
  font-size: 0.8125rem;
  color: #94a3b8;
  font-style: italic;
}
</style>

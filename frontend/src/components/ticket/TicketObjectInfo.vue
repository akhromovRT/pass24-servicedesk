<script setup lang="ts">
defineProps<{
  objectName: string | null
  objectAddress: string | null
  accessPoint: string | null
}>()
</script>

<template>
  <div class="ticket-object-info">
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
</style>

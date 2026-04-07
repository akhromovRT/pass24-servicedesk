<script setup lang="ts">
defineProps<{
  deviceType: string | null
  appVersion: string | null
  errorMessage: string | null
}>()
</script>

<template>
  <div class="ticket-technical-info">
    <div v-if="deviceType" class="info-row">
      <span class="info-label">Устройство</span>
      <span class="info-value">{{ deviceType }}</span>
    </div>
    <div v-if="appVersion" class="info-row">
      <span class="info-label">Версия приложения</span>
      <span class="info-value">{{ appVersion }}</span>
    </div>
    <div v-if="errorMessage" class="info-row">
      <span class="info-label">Сообщение об ошибке</span>
      <code class="info-code">{{ errorMessage }}</code>
    </div>
  </div>
</template>

<style scoped>
.ticket-technical-info {
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

.info-code {
  font-family: 'SF Mono', 'Fira Code', 'Fira Mono', Menlo, Consolas, monospace;
  font-size: 0.8125rem;
  color: #dc2626;
  background: #fef2f2;
  border: 1px solid #fecaca;
  border-radius: 4px;
  padding: 6px 8px;
  white-space: pre-wrap;
  word-break: break-word;
}
</style>

<script setup lang="ts">
import { toRef } from 'vue'
import ProgressBar from 'primevue/progressbar'
import type { Ticket } from '../../types'
import { useSlaProgress } from '../../composables/useSlaProgress'

const props = defineProps<{
  ticket: Ticket
}>()

const { responseProgress, resolveProgress, isPaused, pauseLabel } =
  useSlaProgress(toRef(props, 'ticket'))
</script>

<template>
  <div class="sla-progress">
    <div v-if="responseProgress" class="sla-item">
      <div class="sla-header">
        <span class="sla-label">Первый ответ</span>
        <span
          class="sla-remaining"
          :style="{ color: responseProgress.color }"
        >
          {{ responseProgress.label }}
        </span>
      </div>
      <ProgressBar
        :value="responseProgress.pct"
        :showValue="false"
        :style="{ height: '6px' }"
        :pt="{ value: { style: { backgroundColor: responseProgress.color } } }"
      />
    </div>
    <div v-if="resolveProgress" class="sla-item">
      <div class="sla-header">
        <span class="sla-label">Решение</span>
        <span
          class="sla-remaining"
          :style="{ color: resolveProgress.color }"
        >
          {{ resolveProgress.label }}
        </span>
      </div>
      <ProgressBar
        :value="resolveProgress.pct"
        :showValue="false"
        :style="{ height: '6px' }"
        :pt="{ value: { style: { backgroundColor: resolveProgress.color } } }"
      />
      <div v-if="isPaused && pauseLabel" class="sla-pause-badge">{{ pauseLabel }}</div>
    </div>
    <div v-if="!responseProgress && !resolveProgress" class="sla-empty">
      SLA не настроен
    </div>
  </div>
</template>

<style scoped>
.sla-progress {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.sla-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.sla-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.sla-label {
  font-size: 0.75rem;
  color: #64748b;
  font-weight: 500;
}

.sla-remaining {
  font-size: 0.75rem;
  font-weight: 600;
}

.sla-empty {
  font-size: 0.8125rem;
  color: #94a3b8;
  font-style: italic;
}

.sla-pause-badge {
  margin-top: 4px;
  font-size: 0.75rem;
  color: #64748b;
  background: #f1f5f9;
  padding: 4px 8px;
  border-radius: 4px;
  font-weight: 500;
}
</style>

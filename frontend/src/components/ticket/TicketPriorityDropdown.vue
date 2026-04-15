<script setup lang="ts">
import { ref, watch } from 'vue'
import Select from 'primevue/select'
import { useToast } from 'primevue/usetoast'
import { api } from '../../api/client'
import type { TicketPriority } from '../../types'

const props = defineProps<{
  ticketId: string
  currentPriority: TicketPriority
}>()

const emit = defineEmits<{
  changed: []
}>()

const toast = useToast()
const selected = ref(props.currentPriority)

watch(() => props.currentPriority, (v) => { selected.value = v })

const priorityOptions = [
  { label: 'Критический', value: 'critical', color: '#dc2626' },
  { label: 'Высокий', value: 'high', color: '#ea580c' },
  { label: 'Обычный', value: 'normal', color: '#2563eb' },
  { label: 'Низкий', value: 'low', color: '#64748b' },
]

// Маппинг priority → impact/urgency для API
const priorityToParams: Record<string, { impact: string; urgency: string }> = {
  critical: { impact: 'high', urgency: 'high' },
  high: { impact: 'medium', urgency: 'high' },
  normal: { impact: 'medium', urgency: 'medium' },
  low: { impact: 'low', urgency: 'low' },
}

async function onChange(newPriority: string) {
  if (newPriority === props.currentPriority) return
  const params = priorityToParams[newPriority]
  if (!params) return
  try {
    await api.put(`/tickets/${props.ticketId}/priority`, params)
    toast.add({ severity: 'success', summary: 'Приоритет изменён', life: 2000 })
    emit('changed')
  } catch (e: any) {
    toast.add({ severity: 'error', summary: 'Ошибка', detail: e.message, life: 4000 })
    selected.value = props.currentPriority
  }
}
</script>

<template>
  <div class="priority-dropdown">
    <Select
      v-model="selected"
      :options="priorityOptions"
      optionLabel="label"
      optionValue="value"
      class="w-full"
      @update:model-value="onChange"
    >
      <template #value="{ value }">
        <div class="priority-option">
          <span class="priority-dot" :style="{ background: priorityOptions.find(o => o.value === value)?.color }" />
          <span>{{ priorityOptions.find(o => o.value === value)?.label }}</span>
        </div>
      </template>
      <template #option="{ option }">
        <div class="priority-option">
          <span class="priority-dot" :style="{ background: option.color }" />
          <span>{{ option.label }}</span>
        </div>
      </template>
    </Select>
  </div>
</template>

<style scoped>
.priority-option {
  display: flex;
  align-items: center;
  gap: 8px;
}
.priority-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  flex-shrink: 0;
}
</style>

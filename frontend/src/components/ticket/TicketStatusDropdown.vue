<script setup lang="ts">
import { computed, toRef } from 'vue'
import Select from 'primevue/select'
import type { TicketStatus } from '../../types'
import { useTicketTransitions } from '../../composables/useTicketTransitions'

const props = defineProps<{
  currentStatus: TicketStatus
}>()

const emit = defineEmits<{
  changeStatus: [newStatus: TicketStatus]
}>()

const statusRef = toRef(props, 'currentStatus')
const { statusOptions, STATUS_COLORS } = useTicketTransitions(statusRef)

const selectedStatus = computed({
  get: () => props.currentStatus,
  set: (val: TicketStatus) => {
    if (val !== props.currentStatus) {
      emit('changeStatus', val)
    }
  },
})
</script>

<template>
  <Select
    v-model="selectedStatus"
    :options="statusOptions"
    optionLabel="label"
    optionValue="value"
    class="status-dropdown"
  >
    <template #value="{ value }">
      <div v-if="value" class="status-option">
        <span class="status-dot" :style="{ backgroundColor: STATUS_COLORS[value as TicketStatus] || '#94a3b8' }" />
        <span>{{ statusOptions.find(o => o.value === value)?.label || value }}</span>
      </div>
    </template>
    <template #option="{ option }">
      <div class="status-option">
        <span class="status-dot" :style="{ backgroundColor: option.color }" />
        <span>{{ option.label }}</span>
      </div>
    </template>
  </Select>
</template>

<style scoped>
.status-dropdown {
  width: 100%;
}

.status-option {
  display: flex;
  align-items: center;
  gap: 8px;
}

.status-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  flex-shrink: 0;
}
</style>

<script setup lang="ts">
import { computed, onMounted } from 'vue'
import Select from 'primevue/select'
import Button from 'primevue/button'
import { useAgentTools } from '../../composables/useAgentTools'
import { useAuthStore } from '../../stores/auth'

const props = defineProps<{
  assigneeId: string | null
  ticketId: string
}>()

const emit = defineEmits<{
  assigned: [agentId: string | null]
}>()

const authStore = useAuthStore()
const { agents, loadAll } = useAgentTools()

onMounted(() => {
  loadAll()
})

const currentAssigneeName = computed(() => {
  if (!props.assigneeId) return 'Не назначен'
  const agent = agents.value.find(a => a.id === props.assigneeId)
  return agent?.full_name || 'Загрузка...'
})

const agentOptions = computed(() => [
  { label: 'Не назначен', value: null },
  ...agents.value.map(a => ({ label: a.full_name, value: a.id })),
])

const isAssignedToMe = computed(() => props.assigneeId === authStore.user?.id)

function assignToMe() {
  if (authStore.user) {
    emit('assigned', authStore.user.id)
  }
}

function onAgentSelect(agentId: string | null) {
  emit('assigned', agentId)
}
</script>

<template>
  <div class="ticket-assignment">
    <div class="assignment-current">
      <span class="info-label">Исполнитель</span>
      <span class="info-value">{{ currentAssigneeName }}</span>
    </div>
    <Button
      v-if="!isAssignedToMe"
      label="Взять себе"
      icon="pi pi-user"
      severity="secondary"
      size="small"
      outlined
      class="assign-self-btn"
      @click="assignToMe"
    />
    <Select
      :modelValue="assigneeId"
      :options="agentOptions"
      optionLabel="label"
      optionValue="value"
      placeholder="Назначить агента..."
      class="agent-select"
      @update:modelValue="onAgentSelect"
    />
  </div>
</template>

<style scoped>
.ticket-assignment {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.assignment-current {
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

.assign-self-btn {
  width: 100%;
}

.agent-select {
  width: 100%;
}
</style>

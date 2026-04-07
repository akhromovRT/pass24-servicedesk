<script setup lang="ts">
import { onMounted } from 'vue'
import Button from 'primevue/button'
import { useAgentTools } from '../../composables/useAgentTools'

defineProps<{
  ticketId: string
}>()

const emit = defineEmits<{
  macroApplied: [macroId: string]
}>()

const { macros, loadAll } = useAgentTools()

onMounted(() => {
  loadAll()
})

function applyMacro(macroId: string) {
  emit('macroApplied', macroId)
}
</script>

<template>
  <div class="ticket-macros">
    <div v-if="macros.length === 0" class="macros-empty">
      Макросы не настроены
    </div>
    <div v-else class="macros-grid">
      <Button
        v-for="macro in macros"
        :key="macro.id"
        :label="macro.name"
        :icon="macro.icon || 'pi pi-bolt'"
        severity="secondary"
        size="small"
        outlined
        @click="applyMacro(macro.id)"
      />
    </div>
  </div>
</template>

<style scoped>
.ticket-macros {
  display: flex;
  flex-direction: column;
}

.macros-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.macros-empty {
  font-size: 0.8125rem;
  color: #94a3b8;
  font-style: italic;
}
</style>

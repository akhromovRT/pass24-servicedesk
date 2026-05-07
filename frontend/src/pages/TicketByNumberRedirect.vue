<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '../api/client'

const route = useRoute()
const router = useRouter()
const error = ref('')

onMounted(async () => {
  const number = String(route.params.number)
  try {
    const data = await api.get<{ id: string }>(`/tickets/by-number/${number}`)
    if (data?.id) {
      await router.replace({ name: 'ticket-detail', params: { id: data.id } })
      return
    }
    error.value = 'Тикет не найден'
  } catch {
    error.value = 'Тикет не найден'
  }
})
</script>

<template>
  <div class="redirect-page">
    <p v-if="error" class="error-msg">{{ error }}</p>
    <p v-else class="loading-msg">
      <i class="pi pi-spin pi-spinner" /> Открываем заявку…
    </p>
  </div>
</template>

<style scoped>
.redirect-page {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 50vh;
  padding: 20px;
}

.loading-msg,
.error-msg {
  color: #64748b;
  font-size: 14px;
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.error-msg {
  color: #dc2626;
}
</style>

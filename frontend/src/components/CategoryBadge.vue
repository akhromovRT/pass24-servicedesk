<script setup lang="ts">
import Tag from 'primevue/tag'
import type { ArticleCategory } from '../types'

defineProps<{
  category: ArticleCategory
}>()

const categoryLabels: Record<ArticleCategory, string> = {
  access: 'Доступ',
  pass: 'Пропуска',
  gate: 'Шлагбаумы',
  app: 'Приложение',
  notifications: 'Уведомления',
  general: 'Общее',
}

const categorySeverities: Record<ArticleCategory, string> = {
  access: 'danger',
  pass: 'success',
  gate: 'warn',
  app: 'info',
  notifications: 'secondary',
  general: 'contrast',
}
</script>

<template>
  <Tag
    :value="categoryLabels[category]"
    :severity="categorySeverities[category] as any"
  />
</template>

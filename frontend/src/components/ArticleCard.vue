<script setup lang="ts">
import Card from 'primevue/card'
import type { Article } from '../types'
import CategoryBadge from './CategoryBadge.vue'

defineProps<{
  article: Article
}>()

defineEmits<{
  click: []
}>()

function formatDate(dateStr: string): string {
  return new Intl.DateTimeFormat('ru-RU', {
    day: 'numeric',
    month: 'long',
    year: 'numeric',
  }).format(new Date(dateStr))
}

function excerpt(content: string): string {
  const plain = content.replace(/[#*`_\-\[\]]/g, '').trim()
  return plain.length > 150 ? plain.slice(0, 150) + '...' : plain
}
</script>

<template>
  <Card class="article-card" @click="$emit('click')">
    <template #title>
      <div class="article-card-title">{{ article.title }}</div>
    </template>
    <template #subtitle>
      <CategoryBadge :category="article.category" />
    </template>
    <template #content>
      <p class="article-card-excerpt">{{ excerpt(article.content) }}</p>
      <div class="article-card-meta">
        <span class="meta-item">
          <i class="pi pi-eye" />
          {{ article.views_count }}
        </span>
        <span class="meta-item">
          {{ formatDate(article.created_at) }}
        </span>
      </div>
    </template>
  </Card>
</template>

<style scoped>
.article-card {
  cursor: pointer;
  transition: box-shadow 0.2s, transform 0.2s;
}

.article-card:hover {
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.1);
  transform: translateY(-2px);
}

.article-card-title {
  font-size: 1rem;
  font-weight: 600;
  line-height: 1.4;
}

.article-card-excerpt {
  color: #64748b;
  font-size: 0.875rem;
  line-height: 1.5;
  margin: 0;
}

.article-card-meta {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-top: 12px;
  font-size: 0.8rem;
  color: #94a3b8;
}

.meta-item {
  display: flex;
  align-items: center;
  gap: 4px;
}
</style>

<script setup lang="ts">
import { onMounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import Card from 'primevue/card'
import Button from 'primevue/button'
import Divider from 'primevue/divider'
import Breadcrumb from 'primevue/breadcrumb'
import { useToast } from 'primevue/usetoast'
import { useKnowledgeStore } from '../stores/knowledge'
import CategoryBadge from '../components/CategoryBadge.vue'

const route = useRoute()
const router = useRouter()
const toast = useToast()
const knowledge = useKnowledgeStore()

const article = computed(() => knowledge.currentArticle)

const breadcrumbItems = computed(() => [
  { label: 'База знаний', command: () => router.push('/knowledge') },
  { label: article.value?.title || '...' },
])

const breadcrumbHome = { icon: 'pi pi-book', command: () => router.push('/knowledge') }

function formatDate(dateStr: string): string {
  return new Intl.DateTimeFormat('ru-RU', {
    day: 'numeric',
    month: 'long',
    year: 'numeric',
  }).format(new Date(dateStr))
}

function renderMarkdown(content: string): string {
  let html = content
    // Escape HTML
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')

  // Code blocks (``` ... ```)
  html = html.replace(/```(\w*)\n([\s\S]*?)```/g, (_m, _lang, code) =>
    `<pre><code>${code.trim()}</code></pre>`,
  )

  // Inline code
  html = html.replace(/`([^`]+)`/g, '<code>$1</code>')

  // Headings
  html = html.replace(/^### (.+)$/gm, '<h3>$1</h3>')
  html = html.replace(/^## (.+)$/gm, '<h2>$1</h2>')
  html = html.replace(/^# (.+)$/gm, '<h1>$1</h1>')

  // Bold
  html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')

  // Italic
  html = html.replace(/\*(.+?)\*/g, '<em>$1</em>')

  // Unordered lists
  html = html.replace(/^- (.+)$/gm, '<li>$1</li>')
  html = html.replace(/((?:<li>.*<\/li>\n?)+)/g, '<ul>$1</ul>')

  // Ordered lists
  html = html.replace(/^\d+\. (.+)$/gm, '<li>$1</li>')

  // Paragraphs: double newlines
  html = html.replace(/\n\n+/g, '</p><p>')
  html = `<p>${html}</p>`

  // Single newlines to <br>
  html = html.replace(/\n/g, '<br>')

  // Clean up empty paragraphs
  html = html.replace(/<p>\s*<\/p>/g, '')
  html = html.replace(/<p>\s*(<h[1-3]>)/g, '$1')
  html = html.replace(/(<\/h[1-3]>)\s*<\/p>/g, '$1')
  html = html.replace(/<p>\s*(<pre>)/g, '$1')
  html = html.replace(/(<\/pre>)\s*<\/p>/g, '$1')
  html = html.replace(/<p>\s*(<ul>)/g, '$1')
  html = html.replace(/(<\/ul>)\s*<\/p>/g, '$1')

  return html
}

onMounted(async () => {
  const slug = route.params.slug as string
  try {
    await knowledge.fetchArticle(slug)
  } catch (e: any) {
    toast.add({
      severity: 'error',
      summary: 'Ошибка',
      detail: e.message || 'Статья не найдена',
      life: 4000,
    })
    router.push('/knowledge')
  }
})
</script>

<template>
  <div class="article-page">
    <Breadcrumb :model="breadcrumbItems" :home="breadcrumbHome" class="article-breadcrumb" />

    <div v-if="knowledge.loading" class="article-loading">
      <i class="pi pi-spin pi-spinner" style="font-size: 2rem" />
    </div>

    <Card v-else-if="article" class="article-card">
      <template #title>
        <h1 class="article-title">{{ article.title }}</h1>
      </template>
      <template #subtitle>
        <div class="article-meta">
          <CategoryBadge :category="article.category" />
          <span class="meta-item">
            <i class="pi pi-user" />
            {{ article.author_name }}
          </span>
          <span class="meta-item">
            <i class="pi pi-calendar" />
            {{ formatDate(article.created_at) }}
          </span>
          <span class="meta-item">
            <i class="pi pi-eye" />
            {{ article.views_count }}
          </span>
        </div>
      </template>
      <template #content>
        <Divider />
        <div class="article-content" v-html="renderMarkdown(article.content)" />
      </template>
    </Card>

    <Button
      label="Назад к базе знаний"
      icon="pi pi-arrow-left"
      severity="secondary"
      outlined
      @click="router.push('/knowledge')"
    />
  </div>
</template>

<style scoped>
.article-page {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.article-breadcrumb {
  background: transparent;
  padding: 0;
}

.article-loading {
  display: flex;
  justify-content: center;
  padding: 60px 0;
}

.article-title {
  font-size: 1.5rem;
  font-weight: 700;
  line-height: 1.4;
  margin: 0;
}

.article-meta {
  display: flex;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
  margin-top: 8px;
}

.meta-item {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 0.85rem;
  color: #64748b;
}

.article-content {
  line-height: 1.7;
  font-size: 0.95rem;
}

.article-content :deep(h1) {
  font-size: 1.4rem;
  font-weight: 700;
  margin: 24px 0 12px;
}

.article-content :deep(h2) {
  font-size: 1.2rem;
  font-weight: 600;
  margin: 20px 0 10px;
}

.article-content :deep(h3) {
  font-size: 1.05rem;
  font-weight: 600;
  margin: 16px 0 8px;
}

.article-content :deep(p) {
  margin: 8px 0;
}

.article-content :deep(ul) {
  padding-left: 24px;
  margin: 8px 0;
}

.article-content :deep(li) {
  margin: 4px 0;
}

.article-content :deep(pre) {
  background: #f1f5f9;
  padding: 16px;
  border-radius: 8px;
  overflow-x: auto;
  margin: 12px 0;
}

.article-content :deep(code) {
  font-family: 'SF Mono', 'Fira Code', monospace;
  font-size: 0.875em;
}

.article-content :deep(p code),
.article-content :deep(li code) {
  background: #f1f5f9;
  padding: 2px 6px;
  border-radius: 4px;
}

.article-content :deep(strong) {
  font-weight: 600;
}
</style>

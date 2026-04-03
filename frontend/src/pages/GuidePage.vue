<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import Button from 'primevue/button'
import Tag from 'primevue/tag'
import Divider from 'primevue/divider'
import { useToast } from 'primevue/usetoast'
import { useKnowledgeStore } from '../stores/knowledge'

const route = useRoute()
const router = useRouter()
const toast = useToast()
const store = useKnowledgeStore()

const loading = ref(true)

const categoryLabels: Record<string, string> = {
  access: 'Доступ',
  pass: 'Пропуска',
  gate: 'Шлагбаумы',
  app: 'Приложение',
  notifications: 'Уведомления',
  general: 'Общее',
}

const categoryColors: Record<string, string> = {
  access: '#ef4444',
  pass: '#22c55e',
  gate: '#f59e0b',
  app: '#3b82f6',
  notifications: '#8b5cf6',
  general: '#64748b',
}

const formattedDate = computed(() => {
  if (!store.currentArticle) return ''
  return new Intl.DateTimeFormat('ru-RU', {
    day: 'numeric',
    month: 'long',
    year: 'numeric',
  }).format(new Date(store.currentArticle.created_at))
})

function renderMarkdown(md: string): string {
  let html = md
  // Code blocks
  html = html.replace(/```(\w*)\n([\s\S]*?)```/g, '<pre><code>$2</code></pre>')
  // Inline code
  html = html.replace(/`([^`]+)`/g, '<code class="inline">$1</code>')
  // H1
  html = html.replace(/^# (.+)$/gm, '<h1>$1</h1>')
  // H2
  html = html.replace(/^## (.+)$/gm, '<h2>$1</h2>')
  // H3
  html = html.replace(/^### (.+)$/gm, '<h3>$1</h3>')
  // Bold
  html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
  // Italic
  html = html.replace(/\*(.+?)\*/g, '<em>$1</em>')
  // Tables
  html = html.replace(/^\|(.+)\|$/gm, (match) => {
    const cells = match.split('|').filter(c => c.trim())
    if (cells.every(c => /^[\s-:]+$/.test(c))) return '<tr class="sep"></tr>'
    const tag = match.includes('---') ? 'th' : 'td'
    return '<tr>' + cells.map(c => `<${tag}>${c.trim()}</${tag}>`).join('') + '</tr>'
  })
  html = html.replace(/(<tr.*?<\/tr>\n?)+/g, '<table>$&</table>')
  html = html.replace(/<tr class="sep"><\/tr>/g, '')
  // Blockquotes
  html = html.replace(/^> (.+)$/gm, '<blockquote>$1</blockquote>')
  // Ordered lists
  html = html.replace(/^\d+\. (.+)$/gm, '<li class="ol">$1</li>')
  html = html.replace(/(<li class="ol">.*<\/li>\n?)+/g, '<ol>$&</ol>')
  // Unordered lists
  html = html.replace(/^- (.+)$/gm, '<li>$1</li>')
  html = html.replace(/(<li>.*<\/li>\n?)+/g, (match) => {
    if (match.includes('class="ol"')) return match
    return '<ul>' + match + '</ul>'
  })
  // Paragraphs
  html = html.replace(/^(?!<[a-z])((?!<\/)[^\n]+)$/gm, '<p>$1</p>')
  // Clean empty paragraphs
  html = html.replace(/<p>\s*<\/p>/g, '')
  return html
}

onMounted(async () => {
  try {
    await store.fetchArticle(route.params.slug as string)
  } catch {
    toast.add({ severity: 'error', summary: 'Инструкция не найдена', life: 3000 })
    router.push('/instructions')
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div v-if="loading" class="guide-loading">
    <i class="pi pi-spin pi-spinner" style="font-size: 2rem; color: #94a3b8;" />
  </div>

  <div v-else-if="store.currentArticle" class="guide">
    <!-- Breadcrumb -->
    <nav class="guide-breadcrumb">
      <router-link to="/instructions" class="breadcrumb-link">
        <i class="pi pi-arrow-left" />
        Инструкции
      </router-link>
      <span class="breadcrumb-sep">/</span>
      <span class="breadcrumb-current">{{ store.currentArticle.title }}</span>
    </nav>

    <!-- Header card -->
    <div class="guide-header">
      <div class="guide-meta">
        <Tag
          :value="categoryLabels[store.currentArticle.category] || store.currentArticle.category"
          :style="{ background: categoryColors[store.currentArticle.category] || '#64748b', color: 'white', border: 'none' }"
        />
        <Tag value="Инструкция" severity="info" />
      </div>
      <h1 class="guide-title">{{ store.currentArticle.title }}</h1>
      <div class="guide-info">
        <span><i class="pi pi-user" /> {{ store.currentArticle.author_name }}</span>
        <span><i class="pi pi-calendar" /> {{ formattedDate }}</span>
        <span><i class="pi pi-eye" /> {{ store.currentArticle.views_count }}</span>
      </div>
    </div>

    <Divider />

    <!-- Content -->
    <article class="guide-content" v-html="renderMarkdown(store.currentArticle.content)" />

    <!-- Footer -->
    <div class="guide-footer">
      <Divider />
      <div class="guide-footer-inner">
        <p class="guide-footer-text">Не нашли ответ? Создайте заявку в техподдержку.</p>
        <div class="guide-footer-actions">
          <Button
            label="Назад к инструкциям"
            icon="pi pi-arrow-left"
            severity="secondary"
            outlined
            @click="router.push('/instructions')"
          />
          <Button
            label="Создать заявку"
            icon="pi pi-plus"
            @click="router.push('/tickets/create')"
          />
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.guide {
  max-width: 780px;
  margin: 0 auto;
}

.guide-loading {
  display: flex;
  justify-content: center;
  padding: 80px;
}

/* Breadcrumb */
.guide-breadcrumb {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  margin-bottom: 20px;
  color: #94a3b8;
}

.breadcrumb-link {
  color: #3b82f6;
  text-decoration: none;
  display: flex;
  align-items: center;
  gap: 6px;
  transition: color 0.15s;
}

.breadcrumb-link:hover { color: #1d4ed8; }

.breadcrumb-sep { color: #cbd5e1; }

.breadcrumb-current {
  color: #64748b;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* Header */
.guide-header {
  margin-bottom: 8px;
}

.guide-meta {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
}

.guide-title {
  font-size: 28px;
  font-weight: 800;
  color: #0f172a;
  line-height: 1.25;
  margin: 0 0 12px;
  letter-spacing: -0.02em;
}

.guide-info {
  display: flex;
  gap: 20px;
  font-size: 14px;
  color: #94a3b8;
}

.guide-info span {
  display: flex;
  align-items: center;
  gap: 6px;
}

.guide-info i { font-size: 13px; }

/* Content — beautiful article rendering */
.guide-content {
  line-height: 1.75;
  color: #334155;
}

.guide-content :deep(h1) {
  font-size: 24px;
  font-weight: 700;
  color: #0f172a;
  margin: 32px 0 12px;
  padding-bottom: 8px;
  border-bottom: 2px solid #f1f5f9;
}

.guide-content :deep(h2) {
  font-size: 20px;
  font-weight: 700;
  color: #1e293b;
  margin: 28px 0 10px;
}

.guide-content :deep(h3) {
  font-size: 16px;
  font-weight: 600;
  color: #334155;
  margin: 20px 0 8px;
}

.guide-content :deep(p) {
  margin: 8px 0;
  font-size: 15px;
}

.guide-content :deep(strong) {
  color: #0f172a;
  font-weight: 600;
}

.guide-content :deep(ol),
.guide-content :deep(ul) {
  margin: 8px 0 8px 20px;
  padding: 0;
}

.guide-content :deep(li) {
  margin: 6px 0;
  font-size: 15px;
  padding-left: 4px;
}

.guide-content :deep(ol) {
  list-style: decimal;
}

.guide-content :deep(ul) {
  list-style: disc;
}

.guide-content :deep(blockquote) {
  margin: 16px 0;
  padding: 12px 16px;
  background: #f0f9ff;
  border-left: 4px solid #3b82f6;
  border-radius: 0 8px 8px 0;
  color: #1e40af;
  font-size: 14px;
}

.guide-content :deep(pre) {
  background: #1e293b;
  color: #e2e8f0;
  padding: 16px 20px;
  border-radius: 10px;
  overflow-x: auto;
  margin: 16px 0;
  font-size: 14px;
  line-height: 1.6;
}

.guide-content :deep(code.inline) {
  background: #f1f5f9;
  color: #e11d48;
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 14px;
  font-family: 'SF Mono', Monaco, monospace;
}

.guide-content :deep(table) {
  width: 100%;
  border-collapse: collapse;
  margin: 16px 0;
  font-size: 14px;
}

.guide-content :deep(th) {
  background: #f8fafc;
  font-weight: 600;
  color: #1e293b;
  text-align: left;
  padding: 10px 14px;
  border-bottom: 2px solid #e2e8f0;
}

.guide-content :deep(td) {
  padding: 10px 14px;
  border-bottom: 1px solid #f1f5f9;
  color: #475569;
}

.guide-content :deep(tr:hover td) {
  background: #fafbfc;
}

/* Footer */
.guide-footer {
  margin-top: 32px;
}

.guide-footer-inner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 16px;
}

.guide-footer-text {
  color: #64748b;
  font-size: 14px;
  margin: 0;
}

.guide-footer-actions {
  display: flex;
  gap: 8px;
}

@media (max-width: 640px) {
  .guide-title { font-size: 22px; }
  .guide-info { flex-wrap: wrap; gap: 12px; }
  .guide-footer-inner { flex-direction: column; align-items: flex-start; }
}
</style>

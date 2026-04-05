<script setup lang="ts">
import { ref, onMounted, computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import Button from 'primevue/button'
import Tag from 'primevue/tag'
import Textarea from 'primevue/textarea'
import Divider from 'primevue/divider'
import { useToast } from 'primevue/usetoast'
import { useKnowledgeStore } from '../stores/knowledge'
import { getSessionId } from '../utils/session'
import type { Article } from '../types'

const route = useRoute()
const router = useRouter()
const toast = useToast()
const store = useKnowledgeStore()

const loading = ref(true)
const relatedArticles = ref<Article[]>([])

// Feedback widget state
const feedbackChoice = ref<'helpful' | 'not_helpful' | null>(null)
const feedbackComment = ref('')
const feedbackSubmitting = ref(false)
const feedbackDone = ref(false)
const feedbackAlreadyGiven = ref<'helpful' | 'not_helpful' | null>(null)

const categoryLabels: Record<string, string> = {
  access: 'Доступ и вход',
  pass: 'Пропуска и QR',
  gate: 'Шлагбаумы и камеры',
  app: 'Мобильное приложение',
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

const typeMeta = computed(() => {
  const t = store.currentArticle?.article_type
  return t === 'guide'
    ? { label: 'Инструкция', severity: 'info' as const }
    : { label: 'FAQ', severity: 'warn' as const }
})

const formattedDate = computed(() => {
  if (!store.currentArticle) return ''
  return new Intl.DateTimeFormat('ru-RU', {
    day: 'numeric',
    month: 'long',
    year: 'numeric',
  }).format(new Date(store.currentArticle.updated_at || store.currentArticle.created_at))
})

// TOC: извлечём заголовки H2/H3 из содержимого
const tocItems = computed(() => {
  if (!store.currentArticle) return []
  const content = store.currentArticle.content
  const items: { level: number; text: string; id: string }[] = []
  const lines = content.split('\n')
  for (const line of lines) {
    const h2 = line.match(/^## (.+)$/)
    const h3 = line.match(/^### (.+)$/)
    if (h2) {
      items.push({ level: 2, text: h2[1].trim(), id: slugifyHeading(h2[1].trim()) })
    } else if (h3) {
      items.push({ level: 3, text: h3[1].trim(), id: slugifyHeading(h3[1].trim()) })
    }
  }
  return items
})

const hasToc = computed(() => tocItems.value.length >= 3)

function slugifyHeading(s: string): string {
  return 'h-' + s.toLowerCase().replace(/[^a-zа-я0-9]+/gi, '-').replace(/^-|-$/g, '').slice(0, 60)
}

function renderMarkdown(md: string): string {
  let html = md
  // Code blocks ``` ... ```
  html = html.replace(/```(\w*)\n([\s\S]*?)```/g, '<pre><code>$2</code></pre>')
  // Inline code
  html = html.replace(/`([^`]+)`/g, '<code class="inline">$1</code>')
  // Headings с якорями для TOC
  html = html.replace(/^### (.+)$/gm, (_m, t) => `<h3 id="${slugifyHeading(t.trim())}">${t}</h3>`)
  html = html.replace(/^## (.+)$/gm, (_m, t) => `<h2 id="${slugifyHeading(t.trim())}">${t}</h2>`)
  html = html.replace(/^# (.+)$/gm, '<h1>$1</h1>')
  // Bold / italic
  html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
  html = html.replace(/(^|[^*])\*([^*\n]+)\*/g, '$1<em>$2</em>')
  // Tables
  html = html.replace(/^\|(.+)\|$/gm, (match) => {
    const cells = match.split('|').filter((c) => c.trim())
    if (cells.every((c) => /^[\s-:]+$/.test(c))) return '<tr class="sep"></tr>'
    const tag = match.includes('---') ? 'th' : 'td'
    return '<tr>' + cells.map((c) => `<${tag}>${c.trim()}</${tag}>`).join('') + '</tr>'
  })
  html = html.replace(/(<tr.*?<\/tr>\n?)+/g, '<table>$&</table>')
  html = html.replace(/<tr class="sep"><\/tr>/g, '')
  // Blockquotes (поддержка info/warning callout-ов)
  html = html.replace(/^> \*\*(Важно|Внимание|Предупреждение)[:：]?\*\*\s*(.+)$/gim, '<blockquote class="warning"><strong>$1:</strong> $2</blockquote>')
  html = html.replace(/^> \*\*(Совет|Подсказка|Примечание|Заметка)[:：]?\*\*\s*(.+)$/gim, '<blockquote class="tip"><strong>$1:</strong> $2</blockquote>')
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
  html = html.replace(/<p>\s*<\/p>/g, '')
  return html
}

async function loadArticle(slug: string) {
  loading.value = true
  // Сбрасываем feedback state при переходе между статьями
  feedbackChoice.value = null
  feedbackComment.value = ''
  feedbackDone.value = false
  feedbackAlreadyGiven.value = null
  try {
    await store.fetchArticle(slug)
    await loadRelated()
    // Проверяем, оставлял ли пользователь feedback по этой статье
    if (store.currentArticle) {
      const key = `pass24_feedback_${store.currentArticle.id}`
      try {
        const prev = localStorage.getItem(key)
        if (prev === 'helpful' || prev === 'not_helpful') {
          feedbackAlreadyGiven.value = prev
        }
      } catch {
        // ignore storage errors
      }
    }
  } catch {
    toast.add({ severity: 'error', summary: 'Статья не найдена', life: 3000 })
    router.push('/knowledge')
  } finally {
    loading.value = false
  }
}

async function submitFeedback(helpful: boolean) {
  if (!store.currentArticle) return
  // Если это 👎 и комментарий ещё не раскрыт — раскрываем форму
  if (!helpful && feedbackChoice.value !== 'not_helpful') {
    feedbackChoice.value = 'not_helpful'
    return
  }
  // Если это 👍 — сразу отправляем
  feedbackSubmitting.value = true
  try {
    const resp = await store.submitFeedback(store.currentArticle.id, {
      helpful,
      comment: feedbackComment.value.trim() || undefined,
      session_id: getSessionId(),
      source: 'web',
    })
    feedbackDone.value = true
    // Сохраняем выбор в localStorage
    try {
      const key = `pass24_feedback_${store.currentArticle.id}`
      localStorage.setItem(key, helpful ? 'helpful' : 'not_helpful')
    } catch {
      // ignore
    }
    if (!resp.recorded) {
      toast.add({ severity: 'info', summary: 'Вы уже оценивали эту статью', life: 3000 })
    } else {
      toast.add({ severity: 'success', summary: 'Спасибо за отзыв!', life: 2500 })
    }
  } catch (e: any) {
    toast.add({ severity: 'error', summary: 'Не удалось отправить', detail: e.message, life: 3000 })
  } finally {
    feedbackSubmitting.value = false
  }
}

async function loadRelated() {
  if (!store.currentArticle) return
  try {
    // Загружаем статьи той же категории
    await store.fetchArticles(1, store.currentArticle.category)
    relatedArticles.value = store.articles
      .filter((a) => a.id !== store.currentArticle!.id)
      .slice(0, 4)
  } catch {
    relatedArticles.value = []
  }
}

function scrollToHeading(id: string) {
  const el = document.getElementById(id)
  if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

onMounted(() => {
  loadArticle(route.params.slug as string)
})

// Reload on slug change (если переходим между связанными статьями)
watch(
  () => route.params.slug,
  (newSlug) => {
    if (newSlug && typeof newSlug === 'string') {
      loadArticle(newSlug)
      window.scrollTo({ top: 0, behavior: 'smooth' })
    }
  },
)
</script>

<template>
  <div v-if="loading" class="article-loading">
    <i class="pi pi-spin pi-spinner" style="font-size: 2rem; color: #94a3b8" />
  </div>

  <div v-else-if="store.currentArticle" class="article-page">
    <!-- Breadcrumb -->
    <nav class="breadcrumb">
      <router-link to="/knowledge" class="breadcrumb-link">
        <i class="pi pi-arrow-left" />
        База знаний
      </router-link>
      <span class="breadcrumb-sep">/</span>
      <span class="breadcrumb-category">{{ categoryLabels[store.currentArticle.category] || store.currentArticle.category }}</span>
      <span class="breadcrumb-sep">/</span>
      <span class="breadcrumb-current">{{ store.currentArticle.title }}</span>
    </nav>

    <!-- Header -->
    <div class="article-header">
      <div class="article-meta-top">
        <Tag
          :value="categoryLabels[store.currentArticle.category] || store.currentArticle.category"
          :style="{
            background: categoryColors[store.currentArticle.category] || '#64748b',
            color: 'white',
            border: 'none',
          }"
        />
        <Tag :value="typeMeta.label" :severity="typeMeta.severity" />
      </div>
      <h1 class="article-title">{{ store.currentArticle.title }}</h1>
      <div class="article-info">
        <span><i class="pi pi-calendar" /> Обновлено {{ formattedDate }}</span>
        <span><i class="pi pi-eye" /> {{ store.currentArticle.views_count }} просмотров</span>
        <span v-if="store.currentArticle.author_name"><i class="pi pi-user" /> {{ store.currentArticle.author_name }}</span>
      </div>
    </div>

    <Divider />

    <!-- TOC (если есть 3+ заголовков) -->
    <div v-if="hasToc" class="toc">
      <div class="toc-title">Содержание</div>
      <ol class="toc-list">
        <li
          v-for="item in tocItems"
          :key="item.id"
          :class="['toc-item', `toc-level-${item.level}`]"
          @click="scrollToHeading(item.id)"
        >
          {{ item.text }}
        </li>
      </ol>
    </div>

    <!-- Content -->
    <article class="article-content" v-html="renderMarkdown(store.currentArticle.content)" />

    <!-- Feedback widget: «Помогла ли статья?» -->
    <div class="feedback">
      <Divider />
      <!-- Уже оставлял отзыв -->
      <div v-if="feedbackAlreadyGiven && !feedbackDone" class="feedback-done">
        <i :class="feedbackAlreadyGiven === 'helpful' ? 'pi pi-thumbs-up-fill helpful' : 'pi pi-thumbs-down-fill not-helpful'" />
        <span>Вы уже оценили эту статью как «{{ feedbackAlreadyGiven === 'helpful' ? 'помогла' : 'не помогла' }}»</span>
      </div>
      <!-- Только что отправил -->
      <div v-else-if="feedbackDone" class="feedback-done success">
        <i class="pi pi-check-circle" />
        <span>Спасибо! Ваш отзыв поможет улучшить статью.</span>
      </div>
      <!-- Открытый виджет -->
      <div v-else class="feedback-widget">
        <div class="feedback-question">Помогла ли статья решить ваш вопрос?</div>
        <div class="feedback-buttons">
          <button
            type="button"
            class="feedback-btn helpful"
            :disabled="feedbackSubmitting"
            @click="submitFeedback(true)"
          >
            <i class="pi pi-thumbs-up" />
            Да, помогла
          </button>
          <button
            type="button"
            class="feedback-btn not-helpful"
            :class="{ active: feedbackChoice === 'not_helpful' }"
            :disabled="feedbackSubmitting"
            @click="submitFeedback(false)"
          >
            <i class="pi pi-thumbs-down" />
            Нет, не помогла
          </button>
        </div>
        <!-- Форма комментария при 👎 -->
        <div v-if="feedbackChoice === 'not_helpful'" class="feedback-comment">
          <Textarea
            v-model="feedbackComment"
            rows="2"
            placeholder="Что именно не помогло? (необязательно, но поможет нам улучшить статью)"
            :maxlength="500"
            class="feedback-textarea"
          />
          <div class="feedback-comment-actions">
            <Button
              label="Отправить отзыв"
              size="small"
              :loading="feedbackSubmitting"
              @click="submitFeedback(false)"
            />
          </div>
        </div>
      </div>
    </div>

    <!-- Related articles -->
    <div v-if="relatedArticles.length > 0" class="related">
      <Divider />
      <h2 class="related-title">Связанные статьи</h2>
      <div class="related-grid">
        <div
          v-for="related in relatedArticles"
          :key="related.id"
          class="related-card"
          @click="router.push(`/knowledge/${related.slug}`)"
        >
          <i
            :class="related.article_type === 'guide' ? 'pi pi-book' : 'pi pi-question-circle'"
            :style="{ color: categoryColors[related.category] || '#64748b' }"
          />
          <div class="related-body">
            <div class="related-card-title">{{ related.title }}</div>
            <div class="related-card-type">{{ related.article_type === 'guide' ? 'Инструкция' : 'FAQ' }}</div>
          </div>
          <i class="pi pi-chevron-right related-arrow" />
        </div>
      </div>
    </div>

    <!-- Footer CTA -->
    <div class="article-footer">
      <Divider />
      <div class="footer-inner">
        <p class="footer-text">Не нашли ответ в базе знаний?</p>
        <div class="footer-actions">
          <Button
            label="Назад к базе знаний"
            icon="pi pi-arrow-left"
            severity="secondary"
            outlined
            @click="router.push('/knowledge')"
          />
          <Button
            label="Не помогло — создать заявку"
            icon="pi pi-plus"
            @click="router.push({
              path: '/tickets/create',
              query: {
                from_article: store.currentArticle?.slug,
                title: `По статье: ${store.currentArticle?.title}`,
                description: `Клиент пришёл из статьи «${store.currentArticle?.title}» (${store.currentArticle?.category}) и не нашёл там ответа на свой вопрос.\n\nСуть вопроса: `,
                category: store.currentArticle?.category,
              }
            })"
          />
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.article-page {
  max-width: 780px;
  margin: 0 auto;
}

.article-loading {
  display: flex;
  justify-content: center;
  padding: 80px;
}

/* Breadcrumb */
.breadcrumb {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  margin-bottom: 20px;
  color: #94a3b8;
  flex-wrap: wrap;
}

.breadcrumb-link {
  color: #3b82f6;
  text-decoration: none;
  display: flex;
  align-items: center;
  gap: 6px;
  transition: color 0.15s;
}

.breadcrumb-link:hover {
  color: #1d4ed8;
}

.breadcrumb-sep {
  color: #cbd5e1;
}

.breadcrumb-category {
  color: #64748b;
}

.breadcrumb-current {
  color: #1e293b;
  font-weight: 500;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 300px;
}

/* Header */
.article-header {
  margin-bottom: 8px;
}

.article-meta-top {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
  flex-wrap: wrap;
}

.article-title {
  font-size: 28px;
  font-weight: 800;
  color: #0f172a;
  line-height: 1.25;
  margin: 0 0 12px;
  letter-spacing: -0.02em;
}

.article-info {
  display: flex;
  gap: 20px;
  font-size: 14px;
  color: #94a3b8;
  flex-wrap: wrap;
}

.article-info span {
  display: flex;
  align-items: center;
  gap: 6px;
}

.article-info i {
  font-size: 13px;
}

/* TOC */
.toc {
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  padding: 16px 20px;
  margin: 16px 0 24px;
}

.toc-title {
  font-size: 13px;
  font-weight: 700;
  color: #64748b;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin-bottom: 10px;
}

.toc-list {
  list-style: none;
  padding: 0;
  margin: 0;
}

.toc-item {
  padding: 4px 0;
  font-size: 14px;
  color: #3b82f6;
  cursor: pointer;
  transition: color 0.15s;
}

.toc-item:hover {
  color: #1d4ed8;
  text-decoration: underline;
}

.toc-level-3 {
  padding-left: 16px;
  font-size: 13px;
  color: #64748b;
}

.toc-level-3:hover {
  color: #3b82f6;
}

/* Content */
.article-content {
  line-height: 1.75;
  color: #334155;
}

.article-content :deep(h1) {
  font-size: 24px;
  font-weight: 700;
  color: #0f172a;
  margin: 32px 0 12px;
  padding-bottom: 8px;
  border-bottom: 2px solid #f1f5f9;
}

.article-content :deep(h2) {
  font-size: 20px;
  font-weight: 700;
  color: #1e293b;
  margin: 28px 0 10px;
  scroll-margin-top: 20px;
}

.article-content :deep(h3) {
  font-size: 16px;
  font-weight: 600;
  color: #334155;
  margin: 20px 0 8px;
  scroll-margin-top: 20px;
}

.article-content :deep(p) {
  margin: 8px 0;
  font-size: 15px;
}

.article-content :deep(strong) {
  color: #0f172a;
  font-weight: 600;
}

.article-content :deep(ol),
.article-content :deep(ul) {
  margin: 8px 0 8px 20px;
  padding: 0;
}

.article-content :deep(li) {
  margin: 6px 0;
  font-size: 15px;
  padding-left: 4px;
}

.article-content :deep(ol) {
  list-style: decimal;
}

.article-content :deep(ul) {
  list-style: disc;
}

.article-content :deep(blockquote) {
  margin: 16px 0;
  padding: 12px 16px;
  background: #f0f9ff;
  border-left: 4px solid #3b82f6;
  border-radius: 0 8px 8px 0;
  color: #1e40af;
  font-size: 14px;
}

.article-content :deep(blockquote.tip) {
  background: #f0fdf4;
  border-left-color: #22c55e;
  color: #14532d;
}

.article-content :deep(blockquote.warning) {
  background: #fef3c7;
  border-left-color: #f59e0b;
  color: #78350f;
}

.article-content :deep(pre) {
  background: #1e293b;
  color: #e2e8f0;
  padding: 16px 20px;
  border-radius: 10px;
  overflow-x: auto;
  margin: 16px 0;
  font-size: 14px;
  line-height: 1.6;
}

.article-content :deep(code.inline) {
  background: #f1f5f9;
  color: #e11d48;
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 14px;
  font-family: 'SF Mono', Monaco, monospace;
}

.article-content :deep(table) {
  width: 100%;
  border-collapse: collapse;
  margin: 16px 0;
  font-size: 14px;
}

.article-content :deep(th) {
  background: #f8fafc;
  font-weight: 600;
  color: #1e293b;
  text-align: left;
  padding: 10px 14px;
  border-bottom: 2px solid #e2e8f0;
}

.article-content :deep(td) {
  padding: 10px 14px;
  border-bottom: 1px solid #f1f5f9;
  color: #475569;
}

.article-content :deep(tr:hover td) {
  background: #fafbfc;
}

/* Feedback widget */
.feedback {
  margin-top: 24px;
}

.feedback-widget {
  padding: 16px 20px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
}

.feedback-question {
  font-size: 15px;
  font-weight: 600;
  color: #1e293b;
  margin-bottom: 12px;
}

.feedback-buttons {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.feedback-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 18px;
  background: white;
  border: 1.5px solid #e2e8f0;
  border-radius: 10px;
  font-size: 14px;
  font-weight: 500;
  color: #334155;
  cursor: pointer;
  transition: all 0.15s;
}

.feedback-btn i {
  font-size: 15px;
}

.feedback-btn:hover:not(:disabled) {
  border-color: #cbd5e1;
  background: #fafbfc;
}

.feedback-btn.helpful:hover:not(:disabled) {
  border-color: #22c55e;
  color: #16a34a;
}

.feedback-btn.not-helpful:hover:not(:disabled),
.feedback-btn.not-helpful.active {
  border-color: #ef4444;
  color: #dc2626;
  background: #fef2f2;
}

.feedback-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.feedback-comment {
  margin-top: 12px;
}

.feedback-textarea {
  width: 100%;
  font-size: 14px;
  resize: vertical;
}

.feedback-textarea :deep(textarea) {
  border-radius: 8px;
  padding: 10px 12px;
}

.feedback-comment-actions {
  display: flex;
  justify-content: flex-end;
  margin-top: 10px;
}

.feedback-done {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 18px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  font-size: 14px;
  color: #64748b;
}

.feedback-done i {
  font-size: 16px;
}

.feedback-done i.helpful {
  color: #22c55e;
}

.feedback-done i.not-helpful {
  color: #ef4444;
}

.feedback-done.success {
  background: #f0fdf4;
  border-color: #bbf7d0;
  color: #166534;
}

.feedback-done.success i {
  color: #22c55e;
}

/* Related */
.related {
  margin-top: 32px;
}

.related-title {
  font-size: 18px;
  font-weight: 700;
  color: #0f172a;
  margin: 16px 0 12px;
}

.related-grid {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.related-card {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 14px;
  background: white;
  border: 1px solid #f1f5f9;
  border-radius: 10px;
  cursor: pointer;
  transition: all 0.15s;
}

.related-card:hover {
  border-color: #e2e8f0;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
  transform: translateX(4px);
}

.related-card > i:first-child {
  font-size: 18px;
  flex-shrink: 0;
}

.related-body {
  flex: 1;
  min-width: 0;
}

.related-card-title {
  font-size: 14px;
  font-weight: 600;
  color: #1e293b;
}

.related-card-type {
  font-size: 12px;
  color: #94a3b8;
  margin-top: 2px;
}

.related-arrow {
  color: #cbd5e1;
  font-size: 12px;
  flex-shrink: 0;
}

.related-card:hover .related-arrow {
  color: #3b82f6;
}

/* Footer */
.article-footer {
  margin-top: 32px;
}

.footer-inner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 16px;
}

.footer-text {
  color: #64748b;
  font-size: 14px;
  margin: 0;
}

.footer-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

@media (max-width: 640px) {
  .article-title {
    font-size: 22px;
  }
  .article-info {
    gap: 12px;
  }
  .breadcrumb-current {
    display: none;
  }
  .footer-inner {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>

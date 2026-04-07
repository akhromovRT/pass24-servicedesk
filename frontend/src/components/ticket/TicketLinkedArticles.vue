<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import Button from 'primevue/button'
import Tag from 'primevue/tag'
import Dialog from 'primevue/dialog'
import InputText from 'primevue/inputtext'
import Panel from 'primevue/panel'
import Textarea from 'primevue/textarea'
import Select from 'primevue/select'
import { useToast } from 'primevue/usetoast'
import { api } from '../../api/client'

type RelationType = 'helped' | 'related' | 'created_from'

interface ArticleLink {
  id: string
  ticket_id: string
  article_id: string
  article_title: string
  article_slug: string
  relation_type: RelationType
  linked_by: string
  created_at: string
}

interface ArticleSearchResult {
  id: string
  title: string
  slug: string
  category: string
}

const props = defineProps<{
  ticketId: string
}>()

const emit = defineEmits<{
  updated: []
}>()

const router = useRouter()
const toast = useToast()

const articleLinks = ref<ArticleLink[]>([])
const dialogVisible = ref(false)
const searchQuery = ref('')
const searchResults = ref<ArticleSearchResult[]>([])
const searchLoading = ref(false)
const selectedRelationType = ref<RelationType>('helped')

const createdFromArticle = computed(() =>
  articleLinks.value.find(l => l.relation_type === 'created_from')
)
const improvementText = ref('')
const submittingImprovement = ref(false)
const improvementSubmitted = ref(false)

const relationLabels: Record<RelationType, string> = {
  helped: 'Помогла решить',
  related: 'Связана',
  created_from: 'Создана из тикета',
}

const relationSeverities: Record<RelationType, string> = {
  helped: 'success',
  related: 'info',
  created_from: 'warn',
}

const relationOptions = [
  { label: 'Помогла решить', value: 'helped' },
  { label: 'Связана', value: 'related' },
]

let searchDebounce: ReturnType<typeof setTimeout> | null = null

async function load() {
  try {
    articleLinks.value = await api.get<ArticleLink[]>(`/tickets/${props.ticketId}/articles`)
  } catch {}
}

function openDialog() {
  searchQuery.value = ''
  searchResults.value = []
  selectedRelationType.value = 'helped'
  dialogVisible.value = true
}

function onSearchInput() {
  if (searchDebounce) clearTimeout(searchDebounce)
  const q = searchQuery.value.trim()
  if (!q) { searchResults.value = []; return }
  searchDebounce = setTimeout(async () => {
    searchLoading.value = true
    try {
      const data = await api.get<{ items: ArticleSearchResult[] }>(
        `/knowledge/search?query=${encodeURIComponent(q)}&per_page=5`,
      )
      searchResults.value = data.items || []
    } catch { searchResults.value = [] }
    finally { searchLoading.value = false }
  }, 300)
}

async function linkArticle(articleId: string) {
  try {
    await api.post(`/tickets/${props.ticketId}/articles`, {
      article_id: articleId,
      relation_type: selectedRelationType.value,
    })
    dialogVisible.value = false
    await load()
    toast.add({ severity: 'success', summary: 'Статья привязана', life: 2000 })
  } catch (e: any) {
    toast.add({ severity: 'error', summary: 'Ошибка', detail: e.message, life: 4000 })
  }
}

async function unlinkArticle(linkId: string) {
  try {
    await api.delete(`/tickets/${props.ticketId}/articles/${linkId}`)
    await load()
    toast.add({ severity: 'success', summary: 'Статья отвязана', life: 2000 })
  } catch (e: any) {
    toast.add({ severity: 'error', summary: 'Ошибка', detail: e.message, life: 4000 })
  }
}

async function submitImprovement() {
  if (!createdFromArticle.value) return
  submittingImprovement.value = true
  try {
    await api.post(`/tickets/${props.ticketId}/kb-improvement`, {
      article_id: createdFromArticle.value.article_id,
      suggestion: improvementText.value.trim(),
    })
    improvementSubmitted.value = true
    improvementText.value = ''
    toast.add({ severity: 'success', summary: 'Предложение отправлено', life: 3000 })
  } catch (e: any) {
    toast.add({ severity: 'error', summary: 'Ошибка', detail: e.message, life: 4000 })
  } finally {
    submittingImprovement.value = false
  }
}

load()

defineExpose({ load })
</script>

<template>
  <Panel header="Статьи базы знаний" toggleable collapsed class="sidebar-panel">
    <div v-if="createdFromArticle && !improvementSubmitted" class="improvement-block">
      <p class="improvement-hint">Клиент пришёл из статьи «{{ createdFromArticle.article_title }}» и не нашёл ответа</p>
      <Textarea v-model="improvementText" rows="2" placeholder="Как улучшить статью?" class="w-full" />
      <Button
        label="Отправить"
        size="small"
        :loading="submittingImprovement"
        :disabled="!improvementText.trim()"
        @click="submitImprovement"
        class="mt-2"
      />
    </div>

    <div v-for="link in articleLinks" :key="link.id" class="article-link-item">
      <div class="article-link-info">
        <a class="article-link-title" @click="router.push(`/knowledge/${link.article_slug}`)">
          {{ link.article_title }}
        </a>
        <Tag :value="relationLabels[link.relation_type]" :severity="relationSeverities[link.relation_type] as any" />
      </div>
      <Button icon="pi pi-times" text severity="danger" size="small" @click="unlinkArticle(link.id)" />
    </div>

    <Button label="Привязать статью" icon="pi pi-link" text size="small" @click="openDialog" class="mt-2" />

    <Dialog v-model:visible="dialogVisible" header="Привязать статью БЗ" modal :style="{ width: '500px' }">
      <div class="mb-3">
        <Select v-model="selectedRelationType" :options="relationOptions" optionLabel="label" optionValue="value" class="w-full mb-2" />
        <InputText v-model="searchQuery" placeholder="Поиск статей..." class="w-full" @input="onSearchInput" />
      </div>
      <div v-if="searchLoading" class="text-center p-3"><i class="pi pi-spin pi-spinner"></i></div>
      <div v-for="a in searchResults" :key="a.id" class="search-result-item" @click="linkArticle(a.id)">
        <span>{{ a.title }}</span>
      </div>
    </Dialog>
  </Panel>
</template>

<style scoped>
.article-link-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 0;
  border-bottom: 1px solid #f1f5f9;
}
.article-link-info { display: flex; align-items: center; gap: 8px; flex: 1; min-width: 0; }
.article-link-title { color: #2563eb; cursor: pointer; font-size: 13px; text-decoration: none; }
.article-link-title:hover { text-decoration: underline; }
.improvement-block { background: #fef9c3; border-radius: 8px; padding: 12px; margin-bottom: 12px; }
.improvement-hint { font-size: 13px; color: #92400e; margin: 0 0 8px; }
.search-result-item {
  padding: 10px 12px;
  cursor: pointer;
  border-radius: 6px;
  font-size: 14px;
}
.search-result-item:hover { background: #f1f5f9; }
</style>

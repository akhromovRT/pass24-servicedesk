<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import InputText from 'primevue/inputtext'
import Select from 'primevue/select'
import Button from 'primevue/button'
import Paginator from 'primevue/paginator'
import { useToast } from 'primevue/usetoast'
import { useKnowledgeStore } from '../stores/knowledge'
import { useAuthStore } from '../stores/auth'
import IconField from 'primevue/iconfield'
import InputIcon from 'primevue/inputicon'
import ArticleCard from '../components/ArticleCard.vue'

const router = useRouter()
const toast = useToast()
const knowledge = useKnowledgeStore()
const auth = useAuthStore()

const searchInput = ref('')
const selectedCategory = ref<string | null>(null)
let debounceTimer: ReturnType<typeof setTimeout> | null = null

interface CategoryOption {
  label: string
  value: string | null
}

const categoryOptions: CategoryOption[] = [
  { label: 'Все категории', value: null },
  { label: 'Доступ', value: 'access' },
  { label: 'Пропуска', value: 'pass' },
  { label: 'Шлагбаумы', value: 'gate' },
  { label: 'Приложение', value: 'app' },
  { label: 'Уведомления', value: 'notifications' },
  { label: 'Общее', value: 'general' },
]

const canCreate = () =>
  auth.user?.role === 'support_agent' || auth.user?.role === 'admin'

async function loadArticles(page = 1) {
  try {
    if (searchInput.value.trim()) {
      await knowledge.searchArticles(searchInput.value.trim(), page, 'faq')
    } else {
      await knowledge.fetchArticles(page, selectedCategory.value || undefined, 'faq')
    }
  } catch (e: any) {
    toast.add({
      severity: 'error',
      summary: 'Ошибка',
      detail: e.message || 'Не удалось загрузить статьи',
      life: 4000,
    })
  }
}

function onSearchInput() {
  if (debounceTimer) clearTimeout(debounceTimer)
  debounceTimer = setTimeout(() => {
    loadArticles(1)
  }, 300)
}

function onCategoryChange() {
  searchInput.value = ''
  knowledge.searchQuery = ''
  loadArticles(1)
}

function onPageChange(event: { page: number }) {
  loadArticles(event.page + 1)
}

function openArticle(slug: string) {
  router.push(`/knowledge/${slug}`)
}

onMounted(() => {
  loadArticles()
})

watch(searchInput, onSearchInput)
</script>

<template>
  <div class="knowledge-page">
    <div class="knowledge-header">
      <h1>База знаний</h1>
      <Button
        v-if="canCreate()"
        label="Создать статью"
        icon="pi pi-plus"
        @click="router.push('/knowledge/create')"
      />
    </div>

    <div class="knowledge-filters">
      <IconField class="search-input">
        <InputIcon class="pi pi-search" />
        <InputText
          v-model="searchInput"
          placeholder="Поиск по статьям..."
          fluid
        />
      </IconField>
      <Select
        v-model="selectedCategory"
        :options="categoryOptions"
        option-label="label"
        option-value="value"
        placeholder="Все категории"
        class="category-select"
        @change="onCategoryChange"
      />
    </div>

    <div v-if="knowledge.loading" class="knowledge-loading">
      <i class="pi pi-spin pi-spinner" style="font-size: 2rem" />
    </div>

    <div v-else-if="knowledge.articles.length === 0" class="knowledge-empty">
      <i class="pi pi-inbox" style="font-size: 3rem; color: #cbd5e1" />
      <p>Статьи не найдены</p>
    </div>

    <div v-else class="knowledge-grid">
      <ArticleCard
        v-for="article in knowledge.articles"
        :key="article.id"
        :article="article"
        @click="openArticle(article.slug)"
      />
    </div>

    <Paginator
      v-if="knowledge.total > 20"
      :rows="20"
      :total-records="knowledge.total"
      :first="(knowledge.page - 1) * 20"
      @page="onPageChange"
    />
  </div>
</template>

<style scoped>
.knowledge-page {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.knowledge-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.knowledge-header h1 {
  font-size: 1.5rem;
  font-weight: 700;
}

.knowledge-filters {
  display: flex;
  gap: 12px;
  align-items: center;
}

.search-input {
  flex: 1;
}

.category-select {
  min-width: 200px;
}

.knowledge-loading {
  display: flex;
  justify-content: center;
  padding: 60px 0;
}

.knowledge-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  padding: 60px 0;
  color: #94a3b8;
}

.knowledge-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 16px;
}

@media (max-width: 640px) {
  .knowledge-filters {
    flex-direction: column;
  }

  .category-select {
    min-width: unset;
    width: 100%;
  }
}
</style>

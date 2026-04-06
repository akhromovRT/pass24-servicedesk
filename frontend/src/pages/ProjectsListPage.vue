<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import Button from 'primevue/button'
import InputText from 'primevue/inputtext'
import MultiSelect from 'primevue/multiselect'
import Paginator from 'primevue/paginator'
import { useToast } from 'primevue/usetoast'
import ProjectCard from '../components/ProjectCard.vue'
import { useProjectsStore } from '../stores/projects'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const toast = useToast()
const store = useProjectsStore()
const auth = useAuthStore()

const statusFilter = ref<string[]>([])
const typeFilter = ref<string[]>([])
const searchQuery = ref('')
let searchDebounce: ReturnType<typeof setTimeout> | null = null

const isAdmin = computed(() => auth.user?.role === 'admin')

const statusOptions = [
  { label: 'Черновик', value: 'draft' },
  { label: 'Планирование', value: 'planning' },
  { label: 'В работе', value: 'in_progress' },
  { label: 'На паузе', value: 'on_hold' },
  { label: 'Завершён', value: 'completed' },
  { label: 'Отменён', value: 'cancelled' },
]

const typeOptions = [
  { label: 'ЖК (residential)', value: 'residential' },
  { label: 'БЦ (commercial)', value: 'commercial' },
  { label: 'Только камеры', value: 'cameras_only' },
  { label: 'Большая стройка', value: 'large_construction' },
]

async function loadProjects(p?: number) {
  try {
    await store.fetchProjects(p, {
      status: statusFilter.value.length ? statusFilter.value : undefined,
      project_type: typeFilter.value.length ? typeFilter.value : undefined,
      q: searchQuery.value.trim() || undefined,
    })
  } catch (err: any) {
    toast.add({
      severity: 'error',
      summary: 'Ошибка загрузки',
      detail: err.message || 'Не удалось загрузить проекты',
      life: 4000,
    })
  }
}

function openProject(id: string) {
  router.push(`/projects/${id}`)
}

function onPage(event: { page: number }) {
  loadProjects(event.page + 1)
}

watch(searchQuery, () => {
  if (searchDebounce) clearTimeout(searchDebounce)
  searchDebounce = setTimeout(() => loadProjects(1), 300)
})

watch([statusFilter, typeFilter], () => loadProjects(1))

onMounted(() => loadProjects(1))
</script>

<template>
  <div class="projects-page">
    <div class="page-header">
      <div>
        <h1 class="page-title">Проекты внедрения</h1>
        <p class="page-subtitle">Всего проектов: {{ store.total }}</p>
      </div>
      <Button
        v-if="isAdmin"
        label="Создать проект"
        icon="pi pi-plus"
        @click="router.push('/projects/create')"
      />
    </div>

    <div class="toolbar">
      <span class="search-wrap">
        <i class="pi pi-search" />
        <InputText
          v-model="searchQuery"
          placeholder="Поиск: код, название, клиент, объект..."
          class="search-input"
        />
      </span>
      <MultiSelect
        v-model="statusFilter"
        :options="statusOptions"
        option-label="label"
        option-value="value"
        placeholder="Статус"
        :max-selected-labels="2"
        class="filter-select"
      />
      <MultiSelect
        v-model="typeFilter"
        :options="typeOptions"
        option-label="label"
        option-value="value"
        placeholder="Тип проекта"
        :max-selected-labels="2"
        class="filter-select"
      />
    </div>

    <div v-if="store.loading" class="loading">
      <i class="pi pi-spin pi-spinner" />
      <span>Загрузка...</span>
    </div>

    <div v-else-if="store.projects.length === 0" class="empty-state">
      <i class="pi pi-folder-open" />
      <p>Проекты не найдены</p>
      <Button
        v-if="isAdmin"
        label="Создать первый проект"
        icon="pi pi-plus"
        severity="secondary"
        @click="router.push('/projects/create')"
      />
    </div>

    <div v-else class="projects-grid">
      <ProjectCard
        v-for="project in store.projects"
        :key="project.id"
        :project="project"
        @click="openProject(project.id)"
      />
    </div>

    <Paginator
      v-if="store.total > 0"
      :first="(store.page - 1) * 20"
      :rows="20"
      :total-records="store.total"
      @page="onPage"
    />
  </div>
</template>

<style scoped>
.projects-page {
  max-width: 1400px;
  margin: 0 auto;
  padding: 24px;
}
.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 24px;
}
.page-title {
  margin: 0;
  font-size: 1.75rem;
  font-weight: 600;
}
.page-subtitle {
  margin: 4px 0 0;
  color: #64748b;
  font-size: 0.9rem;
}
.toolbar {
  display: flex;
  gap: 12px;
  margin-bottom: 24px;
  flex-wrap: wrap;
}
.search-wrap {
  position: relative;
  flex: 1;
  min-width: 260px;
}
.search-wrap i {
  position: absolute;
  left: 12px;
  top: 50%;
  transform: translateY(-50%);
  color: #94a3b8;
}
.search-input {
  width: 100%;
  padding-left: 36px;
}
.filter-select {
  min-width: 180px;
}
.loading,
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 48px 24px;
  color: #64748b;
  gap: 12px;
}
.loading i,
.empty-state i {
  font-size: 2rem;
  color: #cbd5e1;
}
.projects-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 20px;
  margin-bottom: 24px;
}
</style>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import Button from 'primevue/button'
import Tag from 'primevue/tag'
import Select from 'primevue/select'
import Checkbox from 'primevue/checkbox'
import Panel from 'primevue/panel'
import { useToast } from 'primevue/usetoast'
import { useTicketsStore } from '../../stores/tickets'
import { useProjectsStore } from '../../stores/projects'
import type { Ticket, ProjectListItem } from '../../types'

const props = defineProps<{
  ticket: Ticket
}>()

const emit = defineEmits<{
  updated: []
}>()

const router = useRouter()
const toast = useToast()
const store = useTicketsStore()
const projectsStore = useProjectsStore()

const projectsList = ref<ProjectListItem[]>([])
const linkProjectId = ref('')
const linkAsBlocker = ref(false)
const linking = ref(false)

const linkedProjectName = computed(() => {
  if (!props.ticket.implementation_project_id) return null
  const p = projectsList.value.find(p => p.id === props.ticket.implementation_project_id)
  return p ? `${p.code} — ${p.name}` : props.ticket.implementation_project_id
})

const projectOptions = computed(() =>
  projectsList.value.map(p => ({ label: `${p.code} — ${p.name}`, value: p.id }))
)

async function loadProjects() {
  try {
    await projectsStore.fetchProjects(1, { status: ['planning', 'in_progress', 'on_hold'] })
    projectsList.value = projectsStore.projects
  } catch {
    projectsList.value = []
  }
}

async function linkToProject() {
  if (!linkProjectId.value) return
  linking.value = true
  try {
    await projectsStore.linkTicket(linkProjectId.value, props.ticket.id, linkAsBlocker.value)
    await store.fetchTicket(props.ticket.id)
    linkProjectId.value = ''
    linkAsBlocker.value = false
    emit('updated')
    toast.add({ severity: 'success', summary: 'Тикет связан с проектом', life: 2000 })
  } catch (err: any) {
    toast.add({ severity: 'error', summary: 'Ошибка', detail: err.message, life: 4000 })
  } finally {
    linking.value = false
  }
}

async function unlinkFromProject() {
  if (!props.ticket.implementation_project_id) return
  linking.value = true
  try {
    await projectsStore.unlinkTicket(props.ticket.implementation_project_id, props.ticket.id)
    await store.fetchTicket(props.ticket.id)
    emit('updated')
    toast.add({ severity: 'success', summary: 'Связь снята', life: 2000 })
  } catch (err: any) {
    toast.add({ severity: 'error', summary: 'Ошибка', detail: err.message, life: 4000 })
  } finally {
    linking.value = false
  }
}

onMounted(loadProjects)
</script>

<template>
  <Panel header="Проект внедрения" toggleable collapsed class="sidebar-panel">
    <template v-if="ticket.implementation_project_id">
      <div class="linked-project">
        <div class="project-info">
          <a class="project-link" @click="router.push(`/projects/${ticket.implementation_project_id}`)">
            {{ linkedProjectName }}
          </a>
          <Tag v-if="ticket.is_implementation_blocker" value="BLOCKER" severity="danger" />
        </div>
        <Button icon="pi pi-times" text severity="danger" size="small" @click="unlinkFromProject" :loading="linking" />
      </div>
    </template>
    <template v-else>
      <div class="link-form">
        <Select
          v-model="linkProjectId"
          :options="projectOptions"
          optionLabel="label"
          optionValue="value"
          placeholder="Выберите проект"
          class="w-full mb-2"
          filter
        />
        <div class="flex align-items-center gap-2 mb-2">
          <Checkbox v-model="linkAsBlocker" :binary="true" inputId="blocker" />
          <label for="blocker" class="text-sm">Является блокером</label>
        </div>
        <Button
          label="Связать"
          icon="pi pi-link"
          size="small"
          :disabled="!linkProjectId"
          :loading="linking"
          @click="linkToProject"
        />
      </div>
    </template>
  </Panel>
</template>

<style scoped>
.linked-project {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.project-info { display: flex; align-items: center; gap: 8px; }
.project-link { color: #2563eb; cursor: pointer; font-size: 13px; }
.project-link:hover { text-decoration: underline; }
.link-form { font-size: 14px; }
</style>

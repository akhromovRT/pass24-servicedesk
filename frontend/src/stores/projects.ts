import { defineStore } from 'pinia'
import { ref } from 'vue'
import { api } from '../api/client'
import type {
  ImplementationProject,
  LinkedTicket,
  PaginatedResponse,
  ProjectComment,
  ProjectCreateInput,
  ProjectDocument,
  ProjectEvent,
  ProjectListItem,
  ProjectStats,
  ProjectStatus,
  ProjectTeamMember,
  ProjectTemplate,
  TeamRole,
} from '../types'

export interface ProjectFilters {
  status?: string[]
  project_type?: string[]
  q?: string
  customer_id?: string
}

export const useProjectsStore = defineStore('projects', () => {
  const projects = ref<ProjectListItem[]>([])
  const currentProject = ref<ImplementationProject | null>(null)
  const total = ref(0)
  const page = ref(1)
  const loading = ref(false)
  const filters = ref<ProjectFilters>({})
  const templates = ref<ProjectTemplate[]>([])
  const stats = ref<ProjectStats | null>(null)

  // ---------------------------------------------------------------------
  // Projects list + detail
  // ---------------------------------------------------------------------

  async function fetchProjects(p?: number, f?: ProjectFilters) {
    loading.value = true
    try {
      if (p !== undefined) page.value = p
      if (f !== undefined) filters.value = f

      const params = new URLSearchParams()
      params.set('page', String(page.value))
      params.set('per_page', '20')
      if (filters.value.status?.length) params.set('status', filters.value.status.join(','))
      if (filters.value.project_type?.length) params.set('project_type', filters.value.project_type.join(','))
      if (filters.value.q) params.set('q', filters.value.q)
      if (filters.value.customer_id) params.set('customer_id', filters.value.customer_id)

      const data = await api.get<PaginatedResponse<ProjectListItem>>(
        `/projects/?${params.toString()}`,
      )
      projects.value = data.items
      total.value = data.total
    } finally {
      loading.value = false
    }
  }

  async function fetchProject(id: string) {
    loading.value = true
    try {
      currentProject.value = await api.get<ImplementationProject>(`/projects/${id}`)
    } finally {
      loading.value = false
    }
  }

  async function createProject(payload: ProjectCreateInput): Promise<ImplementationProject> {
    const project = await api.post<ImplementationProject>('/projects/', payload)
    return project
  }

  async function updateProject(id: string, payload: Partial<ProjectCreateInput>) {
    const project = await api.patch<ImplementationProject>(`/projects/${id}`, payload)
    if (currentProject.value?.id === id) {
      currentProject.value = project
    }
    return project
  }

  async function transitionStatus(id: string, newStatus: ProjectStatus) {
    const project = await api.post<ImplementationProject>(
      `/projects/${id}/transition`,
      { new_status: newStatus },
    )
    if (currentProject.value?.id === id) {
      currentProject.value = project
    }
    return project
  }

  async function deleteProject(id: string) {
    await api.delete(`/projects/${id}`)
  }

  // ---------------------------------------------------------------------
  // Templates + stats
  // ---------------------------------------------------------------------

  async function fetchTemplates() {
    if (templates.value.length > 0) return templates.value
    templates.value = await api.get<ProjectTemplate[]>('/projects/templates')
    return templates.value
  }

  async function fetchStats() {
    try {
      stats.value = await api.get<ProjectStats>('/projects/stats')
    } catch {
      // silent для non-staff
    }
  }

  // ---------------------------------------------------------------------
  // Phases + Tasks
  // ---------------------------------------------------------------------

  async function completeTask(projectId: string, taskId: string) {
    const task = await api.post(`/projects/${projectId}/tasks/${taskId}/complete`, {})
    // После изменения задачи нужно перезагрузить проект для пересчёта прогресса
    if (currentProject.value?.id === projectId) {
      await fetchProject(projectId)
    }
    return task
  }

  async function updateTaskStatus(projectId: string, taskId: string, status: string) {
    const task = await api.patch(`/projects/${projectId}/tasks/${taskId}`, { status })
    if (currentProject.value?.id === projectId) {
      await fetchProject(projectId)
    }
    return task
  }

  async function startPhase(projectId: string, phaseId: string) {
    await api.post(`/projects/${projectId}/phases/${phaseId}/start`, {})
    if (currentProject.value?.id === projectId) {
      await fetchProject(projectId)
    }
  }

  async function completePhase(projectId: string, phaseId: string) {
    await api.post(`/projects/${projectId}/phases/${phaseId}/complete`, {})
    if (currentProject.value?.id === projectId) {
      await fetchProject(projectId)
    }
  }

  // ---------------------------------------------------------------------
  // Workspace
  // ---------------------------------------------------------------------

  async function fetchDocuments(projectId: string) {
    return await api.get<ProjectDocument[]>(`/projects/${projectId}/documents`)
  }

  async function fetchTeam(projectId: string) {
    return await api.get<ProjectTeamMember[]>(`/projects/${projectId}/team`)
  }

  async function addTeamMember(
    projectId: string,
    userId: string,
    teamRole: TeamRole,
    isPrimary = false,
  ) {
    return await api.post<ProjectTeamMember>(`/projects/${projectId}/team`, {
      user_id: userId,
      team_role: teamRole,
      is_primary: isPrimary,
    })
  }

  async function removeTeamMember(projectId: string, memberId: string) {
    await api.delete(`/projects/${projectId}/team/${memberId}`)
  }

  async function fetchComments(projectId: string, taskId?: string) {
    const params = new URLSearchParams()
    if (taskId) params.set('task_id', taskId)
    const qs = params.toString()
    return await api.get<ProjectComment[]>(
      `/projects/${projectId}/comments${qs ? `?${qs}` : ''}`,
    )
  }

  async function addComment(
    projectId: string,
    text: string,
    isInternal = false,
    taskId?: string,
  ) {
    return await api.post<ProjectComment>(`/projects/${projectId}/comments`, {
      text,
      is_internal: isInternal,
      task_id: taskId,
    })
  }

  async function fetchEvents(projectId: string, limit = 50) {
    return await api.get<ProjectEvent[]>(
      `/projects/${projectId}/events?limit=${limit}`,
    )
  }

  async function fetchLinkedTickets(projectId: string) {
    return await api.get<LinkedTicket[]>(`/projects/${projectId}/tickets`)
  }

  async function linkTicket(projectId: string, ticketId: string, isBlocker = false) {
    return await api.post<LinkedTicket>(`/projects/${projectId}/link-ticket`, {
      ticket_id: ticketId,
      is_blocker: isBlocker,
    })
  }

  async function unlinkTicket(projectId: string, ticketId: string) {
    await api.post(`/projects/${projectId}/unlink-ticket/${ticketId}`, {})
  }

  return {
    // state
    projects,
    currentProject,
    total,
    page,
    loading,
    filters,
    templates,
    stats,
    // actions
    fetchProjects,
    fetchProject,
    createProject,
    updateProject,
    transitionStatus,
    deleteProject,
    fetchTemplates,
    fetchStats,
    completeTask,
    updateTaskStatus,
    startPhase,
    completePhase,
    fetchDocuments,
    fetchTeam,
    addTeamMember,
    removeTeamMember,
    fetchComments,
    addComment,
    fetchEvents,
    fetchLinkedTickets,
    linkTicket,
    unlinkTicket,
  }
})

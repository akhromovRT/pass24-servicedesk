import { ref } from 'vue'
import { api } from '../api/client'

interface Agent {
  id: string
  full_name: string
  email: string
}

interface ResponseTemplate {
  id: string
  name: string
  body: string
  usage_count: number
}

interface MacroActions {
  status?: string
  comment?: string
  is_internal_comment?: boolean
  assign_self?: boolean
  assignment_group?: string
}

interface MacroItem {
  id: string
  name: string
  icon?: string
  actions: MacroActions
}

export function useAgentTools() {
  const agents = ref<Agent[]>([])
  const templates = ref<ResponseTemplate[]>([])
  const macros = ref<MacroItem[]>([])

  async function loadAll() {
    try {
      const [a, t, m] = await Promise.all([
        api.get<Agent[]>('/tickets/agents/list'),
        api.get<ResponseTemplate[]>('/tickets/templates'),
        api.get<MacroItem[]>('/tickets/macros'),
      ])
      agents.value = a
      templates.value = t
      macros.value = m
    } catch {}
  }

  return { agents, templates, macros, loadAll }
}

export type { Agent, ResponseTemplate, MacroItem }

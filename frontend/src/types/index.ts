// Типы, соответствующие backend Pydantic-схемам

export interface User {
  id: string
  email: string
  full_name: string
  role: UserRole
  is_active: boolean
  customer_id: string | null
  customer_name: string | null
  created_at: string
}

export type UserRole = 'resident' | 'property_manager' | 'support_agent' | 'admin'

export interface Token {
  access_token: string
  token_type: string
}

export type TicketStatus = 'new' | 'in_progress' | 'waiting_for_user' | 'on_hold' | 'engineer_visit' | 'resolved' | 'closed'
export type TicketPriority = 'low' | 'normal' | 'high' | 'critical'
export type TicketProduct = 'pass24_online' | 'mobile_app' | 'pass24_key' | 'pass24_control' | 'pass24_auto' | 'equipment' | 'integration' | 'other'
export type TicketCategory = 'registration' | 'passes' | 'recognition' | 'app_issues' | 'objects' | 'trusted_persons' | 'equipment_issues' | 'consultation' | 'feature_request' | 'other'
export type TicketType = 'incident' | 'problem' | 'service_request' | 'change_request' | 'question' | 'feature_request'
export type TicketSource = 'web' | 'email' | 'telegram' | 'api' | 'phone'
export type TicketImpact = 'high' | 'medium' | 'low'
export type TicketUrgency = 'high' | 'medium' | 'low'
export type AssignmentGroup = 'l1_support' | 'l2_engineers' | 'l3_development' | 'installers' | 'integrations' | 'billing' | 'unassigned'

export interface Ticket {
  id: string
  creator_id: string
  assignee_id: string | null
  assignment_group: string | null
  title: string
  description: string
  product: string | null
  category: string | null
  ticket_type: string | null
  source: string | null
  status: TicketStatus
  priority: TicketPriority
  impact: string | null
  urgency: string | null
  object_name: string | null
  object_address: string | null
  access_point: string | null
  contact_name: string | null
  contact_email: string | null
  contact_phone: string | null
  company: string | null
  customer_id: string | null
  device_type: string | null
  app_version: string | null
  error_message: string | null
  urgent: boolean
  created_at: string
  updated_at: string
  first_response_at: string | null
  resolved_at: string | null
  sla_response_hours: number | null
  sla_resolve_hours: number | null
  sla_breached: boolean
  sla_paused_at: string | null
  sla_total_pause_seconds: number
  has_unread_reply: boolean
  parent_ticket_id: string | null
  implementation_project_id: string | null
  is_implementation_blocker: boolean
  satisfaction_rating: number | null
  satisfaction_comment: string | null
  satisfaction_submitted_at: string | null
  events: TicketEvent[]
  comments: TicketComment[]
  attachments: Attachment[]
}

export interface TicketEvent {
  id: string
  ticket_id: string
  actor_id: string | null
  description: string
  created_at: string
}

export interface TicketComment {
  id: string
  ticket_id: string
  author_id: string
  author_name: string
  text: string
  is_internal: boolean
  created_at: string
}

export interface Attachment {
  id: string
  ticket_id: string
  uploader_id: string
  filename: string
  content_type: string
  size: number
  comment_id: string | null
  created_at: string
}

export interface TicketCreate {
  title: string
  description: string
  product?: TicketProduct
  category?: TicketCategory
  ticket_type?: TicketType
  source?: TicketSource
  object_name?: string
  object_address?: string
  access_point?: string
  contact_name?: string
  contact_phone?: string
  company?: string
  device_type?: string
  app_version?: string
  error_message?: string
  urgent?: boolean
  on_behalf_of_email?: string
  on_behalf_of_name?: string
  source_article_slug?: string
  customer_id?: string
}

export interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  per_page: number
}

export type ArticleType = 'faq' | 'guide'

export interface Article {
  id: string
  title: string
  slug: string
  category: ArticleCategory
  article_type: ArticleType
  content: string
  is_published: boolean
  views_count: number
  helpful_count: number
  not_helpful_count: number
  tags: string[]
  synonyms: string[]
  slug_aliases: string[]
  author_id: string
  author_name: string
  created_at: string
  updated_at: string
}

export type ArticleCategory = 'access' | 'pass' | 'gate' | 'app' | 'notifications' | 'general'

export interface ArticleCreate {
  title: string
  category: ArticleCategory
  article_type?: ArticleType
  content: string
  is_published?: boolean
}

// -------------------------------------------------------------------------
// Implementation Projects
// -------------------------------------------------------------------------

export type ProjectStatus = 'draft' | 'planning' | 'in_progress' | 'on_hold' | 'completed' | 'cancelled'
export type ProjectType = 'residential' | 'commercial' | 'cameras_only' | 'large_construction'
export type PhaseStatus = 'pending' | 'in_progress' | 'completed' | 'blocked' | 'skipped'
export type TaskStatus = 'todo' | 'in_progress' | 'done' | 'cancelled'
export type TaskPriority = 'low' | 'normal' | 'high' | 'critical'
export type DocumentType = 'contract' | 'specification' | 'act' | 'diagram' | 'photo' | 'report' | 'other'
export type TeamRole = 'project_manager' | 'tech_lead' | 'installer' | 'integrator' | 'trainer'

export interface ProjectTask {
  id: string
  phase_id: string
  project_id: string
  title: string
  description: string | null
  status: TaskStatus
  priority: TaskPriority
  assignee_id: string | null
  due_date: string | null
  order_num: number
  is_milestone: boolean
  estimated_hours: number | null
  actual_hours: number | null
  completed_at: string | null
  completed_by: string | null
  created_at: string
  updated_at: string
}

export interface ProjectPhase {
  id: string
  project_id: string
  name: string
  description: string | null
  order_num: number
  status: PhaseStatus
  weight: number
  planned_duration_days: number | null
  planned_start_date: string | null
  planned_end_date: string | null
  actual_start_date: string | null
  actual_end_date: string | null
  progress_pct: number
  tasks: ProjectTask[]
  created_at: string
}

export interface ProjectTeamMember {
  id: string
  project_id: string
  user_id: string
  user_name: string | null
  user_email: string | null
  team_role: TeamRole
  is_primary: boolean
  added_at: string
}

export interface ProjectDocument {
  id: string
  project_id: string
  phase_id: string | null
  task_id: string | null
  document_type: DocumentType
  name: string
  filename: string
  content_type: string
  size: number
  version: number
  uploaded_by: string
  created_at: string
}

export interface ProjectEvent {
  id: string
  project_id: string
  actor_id: string | null
  event_type: string
  description: string
  meta_json: string | null
  created_at: string
}

export interface ProjectComment {
  id: string
  project_id: string
  task_id: string | null
  author_id: string
  author_name: string
  text: string
  is_internal: boolean
  created_at: string
}

export interface ImplementationProject {
  id: string
  code: string
  name: string
  status: ProjectStatus
  project_type: ProjectType
  progress_pct: number
  customer_id: string
  customer_company: string
  object_name: string
  object_address: string | null
  contract_number: string | null
  contract_signed_at: string | null
  planned_start_date: string | null
  planned_end_date: string | null
  actual_start_date: string | null
  actual_end_date: string | null
  manager_id: string | null
  notes: string | null
  created_by: string
  created_at: string
  updated_at: string
  phases: ProjectPhase[]
  team: ProjectTeamMember[]
  document_count: number
  open_tasks_count: number
}

export interface ProjectListItem {
  id: string
  code: string
  name: string
  status: ProjectStatus
  project_type: ProjectType
  progress_pct: number
  customer_id: string
  customer_company: string
  object_name: string
  planned_end_date: string | null
  manager_id: string | null
  updated_at: string
  created_at: string
}

export interface ProjectCreateInput {
  name: string
  customer_id: string
  customer_company: string
  object_name: string
  object_address?: string
  project_type: ProjectType
  contract_number?: string
  contract_signed_at?: string
  planned_start_date?: string
  planned_end_date?: string
  manager_id?: string
  notes?: string
}

export interface ProjectTemplateTask {
  title: string
  description: string
  is_milestone: boolean
  estimated_hours: number
}

export interface ProjectTemplatePhase {
  order: number
  name: string
  description: string
  duration_days: number
  weight: number
  tasks: ProjectTemplateTask[]
}

export interface ProjectTemplate {
  project_type: ProjectType
  title: string
  description: string
  total_duration_days: number
  phases: ProjectTemplatePhase[]
}

export interface ProjectStats {
  total: number
  active: number
  completed_this_month: number
  on_hold: number
  overdue: number
  by_type: Record<string, number>
}

export interface LinkedTicket {
  id: string
  title: string
  status: string
  priority: string
  is_implementation_blocker: boolean
  created_at: string
  creator_id: string
}

// Approvals
export type ApprovalStatus = 'pending' | 'approved' | 'rejected'

export interface ProjectApproval {
  id: string
  project_id: string
  phase_id: string
  status: ApprovalStatus
  requested_by: string
  reviewed_by: string | null
  feedback: string | null
  requested_at: string
  reviewed_at: string | null
}

// Risks
export type RiskSeverity = 'low' | 'medium' | 'high' | 'critical'
export type RiskProbability = 'low' | 'medium' | 'high'
export type RiskStatus = 'open' | 'mitigated' | 'occurred' | 'closed'

export interface ProjectRisk {
  id: string
  project_id: string
  title: string
  description: string | null
  severity: RiskSeverity
  probability: RiskProbability
  impact: string
  mitigation_plan: string | null
  owner_id: string | null
  status: RiskStatus
  created_by: string
  created_at: string
  updated_at: string
}

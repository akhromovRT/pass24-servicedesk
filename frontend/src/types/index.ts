// Типы, соответствующие backend Pydantic-схемам

export interface User {
  id: string
  email: string
  full_name: string
  role: UserRole
  is_active: boolean
  created_at: string
}

export type UserRole = 'resident' | 'property_manager' | 'support_agent' | 'admin'

export interface Token {
  access_token: string
  token_type: string
}

export type TicketStatus = 'new' | 'in_progress' | 'waiting_for_user' | 'resolved' | 'closed'
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

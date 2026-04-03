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

export interface Ticket {
  id: string
  creator_id: string
  title: string
  description: string
  category: string
  object_id: string | null
  access_point_id: string | null
  user_role: string | null
  occurred_at: string | null
  contact: string | null
  urgent: boolean
  status: TicketStatus
  priority: TicketPriority
  created_at: string
  updated_at: string
  events: TicketEvent[]
  comments: TicketComment[]
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
  created_at: string
}

export interface TicketCreate {
  title: string
  description: string
  category?: string
  object_id?: string
  access_point_id?: string
  user_role?: string
  occurred_at?: string
  contact?: string
  urgent?: boolean
}

export interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  per_page: number
}

export interface Article {
  id: string
  title: string
  slug: string
  category: ArticleCategory
  content: string
  is_published: boolean
  views_count: number
  author_id: string
  author_name: string
  created_at: string
  updated_at: string
}

export type ArticleCategory = 'access' | 'pass' | 'gate' | 'app' | 'notifications' | 'general'

export interface ArticleCreate {
  title: string
  category: ArticleCategory
  content: string
  is_published?: boolean
}

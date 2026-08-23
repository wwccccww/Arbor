export type Capability = 'chat' | 'read_memory' | 'write_memory' | 'admin'

export type PersonaGrant = {
  user_id: string
  capabilities: Capability[]
}

export type Persona = {
  id: string
  skin?: string
  display_name: string
  one_liner?: string
  taboos?: string[]
  relationships?: { name: string; kind: string }[]
  personality?: { traits?: string[] }
  grants?: PersonaGrant[]
  stats?: {
    memory_count?: number
    last_interaction?: string
    thread_count?: number
  }
}

export type PersonaPatch = {
  display_name?: string
  one_liner?: string
  taboos?: string[]
  personality?: { traits?: string[] }
  relationships?: { name: string; kind: string }[]
  skin?: 'companion' | 'employee'
}

export type PersonaDraft = {
  skin: 'companion' | 'employee'
  display_name: string
  one_liner?: string
}

export type Tenant = {
  id: string
  name?: string
  role?: string
}

export type RuntimeInfo = {
  llm: string
  store: string
  embed?: string
}

export type Me = {
  user: { id: string; email: string }
  tenants?: Tenant[]
  runtime?: RuntimeInfo
}

export type AuthTokens = {
  access_token: string
  refresh_token: string
  user: { id: string; email: string }
}

export type TenantMember = {
  user: { id: string; email: string }
  role: string
}

export type MemberList = {
  items: TenantMember[]
  forbidden?: boolean
}

export type Thread = {
  id: string
  persona_id: string
}

export type Citation = {
  memory_id?: string
  event_id?: string
  preview?: string
}

export type ChatAttachment = {
  filename: string
}

export type ChatMessage = {
  id: string
  role: string
  text: string
  citations: Citation[]
  attachments?: ChatAttachment[]
  inbox_created?: number
}

export type MessagePage = {
  items: ChatMessage[]
  total: number
}

export type ThreadExport = {
  id: string
  persona_id: string
  messages: {
    role: string
    content: string
    citations?: string[]
    attachments?: ChatAttachment[]
  }[]
}

export type EventNode = {
  id: string
  title: string
  happened_at?: string
  type?: string
  importance?: number
  summary?: string
  memory_ids?: string[]
}

export type EventTree = {
  nodes: EventNode[]
  edges: { from_id: string; to_id: string; kind: string }[]
  forbidden?: boolean
}

export type EventCard = {
  id: string
  title?: string
  happened_at?: string
  type?: string
  summary?: string
  memories: { id: string; text: string }[]
  attachments: { id: string; type: string; text: string }[]
  forbidden?: boolean
}

export type ApiError = Error & { status: number; code?: string }

export type InboxItem = {
  id: string
  kind?: string
  status?: string
  payload?: { text?: string }
}

export type InboxList = {
  items: InboxItem[]
  forbidden?: boolean
}

export type ImportJob = {
  id: string
  status: string
  filename?: string
  persona_id?: string
  inbox_created?: number
  error?: string | null
  forbidden?: boolean
}

export type MemoryItem = {
  id: string
  text: string
  type?: string
  status?: string
  event_id?: string | null
}

export type MemoryList = {
  items: MemoryItem[]
  total: number
  forbidden?: boolean
}

export type EvalMetrics = {
  identity_consistency?: number
  recall_at_5?: number
  persona_leak_rate?: number
  tenant_leak_count?: number
  key_event_hit_rate?: number
}

export type EvalCase = {
  id: string
  query: string
  skill?: string
  expected_source?: string | null
  expected_behavior?: string
  expected_memory_count?: number
  expected_event_id?: string | null
  hit_ids: string[]
  leak_ids: string[]
  sources: Record<string, string>
  recall: number
  leaked: boolean
  event_hit: boolean
  profile_miss: boolean
  passed: boolean
}

export type EvalRun = {
  id: string
  status?: string
  strategy: string
  suite_version?: string
  mode?: string
  metrics: EvalMetrics
  p0_tenant_leak_zero?: boolean
  cases?: EvalCase[]
}

export type AuditLog = {
  id: string
  actor_user_id?: string
  action: string
  resource_type?: string
  resource_id?: string
  persona_id?: string | null
  payload?: Record<string, unknown>
  created_at?: string
}

export type AuditList = {
  items: AuditLog[]
  forbidden?: boolean
}

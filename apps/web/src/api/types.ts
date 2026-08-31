export type Capability = 'chat' | 'read_memory' | 'write_memory' | 'admin'

export type FeishuCalendarStatus = {
  connected: boolean
  provider: string
  calendar_id?: string
}

export type AgentRunSummary = {
  id: string
  goal: string
  status: string
  current_step: number
  max_steps: number
  version: number
  request_id?: string
  created_at?: string
  updated_at?: string
}

export type AgentStep = {
  id: string
  sequence: number
  kind: string
  status: string
  input: Record<string, unknown>
  output: Record<string, unknown>
  observation: Record<string, unknown>
  trace_id?: string
}

export type AgentStepTreeNode = {
  id?: string
  type?: string
  kind?: string
  status?: string
  label?: string
  sequence?: number
  latency_ms?: number
  started_at?: string
  finished_at?: string
  children?: AgentStepTreeNode[]
}

export type AgentRunDetail = {
  run: AgentRunSummary & {
    employee_definition_version?: string
    final_output?: Record<string, unknown> | null
    failure?: Record<string, unknown> | null
    metadata?: Record<string, unknown>
    consumed_tokens?: number
    token_budget?: number
    consumed_cost_micros?: number
    cost_budget_micros?: number
  }
  steps: AgentStep[]
  step_tree?: AgentStepTreeNode
  lineage?: Array<Record<string, unknown>>
}

export type EmployeeDefinition = {
  persona_id: string
  version: string
  role: string
  goals: string[]
  skills: string[]
  knowledge_scopes: string[]
  tool_policy: Record<string, unknown>
  approval_policy: Record<string, unknown>
  memory_policy: Record<string, unknown>
  escalation_policy: Record<string, unknown>
  run_budget_policy: Record<string, unknown>
  evaluation_suite: string
  release_status: string
  eval_gate_passed?: boolean
}

export type AgentApproval = {
  id: string
  run_id: string
  tool_name: string
  status: string
  reason?: string
}

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
  tool_policy?: { allowed_tools?: string[]; notes?: string }
  avatar?: string
  stats?: {
    memory_count?: number
    last_interaction?: string
    last_interaction_at?: string
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
  tool_policy?: { allowed_tools?: string[]; notes?: string }
  avatar?: string
}

export type PersonaDraft = {
  skin: 'companion' | 'employee'
  display_name: string
  one_liner?: string
  template?: string
  avatar?: string
}

export type PersonaTemplate = {
  id: string
  label: string
  skin: 'companion' | 'employee'
  one_liner: string
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
  feishu?: 'stub' | 'feishu'
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

export type RetrievalMeta = {
  strategy?: string
  hit_ids?: string[]
  sources?: Record<string, string>
  hit_scores?: Record<string, number>
  per_source_counts?: Record<string, number>
  sub_queries?: { query?: string; intent?: string; query_hash?: string }[]
}

export type DecisionTrace = {
  retrieval?: {
    strategy?: string
    sub_queries?: { intent?: string; query_hash?: string }[]
    candidate_count?: number
    selected_count?: number
    per_source_counts?: Record<string, number>
    hit_ids?: string[]
  }
  context?: {
    token_budget?: number
    token_estimate?: number
    injected_memory_ids?: string[]
    truncation_notes?: string[]
  }
  reasoner?: {
    called?: boolean
    operation?: string
    result_kind?: string | null
    conflicts_with?: string | null
    duration_ms?: number
  }
  generation?: {
    model?: string
    latency_ms?: number
    citation_ids?: string[]
    input_tokens?: number | null
    output_tokens?: number | null
  }
}

export type DebugRequest = {
  request_id: string
  tenant_id: string
  persona_id?: string | null
  thread_id?: string | null
  message_id?: string | null
  created_at?: string | null
  expires_at?: string | null
  content_sampled?: boolean
  decision_trace: DecisionTrace
}

export type ChatAttachment = {
  filename: string
}

export type ToolResult = {
  tool?: string
  status?: string
  provider?: string
  ticket_id?: string
  title?: string
  note?: string
  summary?: string
  events?: { title?: string; start?: string; note?: string }[]
}

export type ChatMessage = {
  id: string
  role: string
  text: string
  citations: Citation[]
  attachments?: ChatAttachment[]
  inbox_created?: number
  retrieval_meta?: RetrievalMeta
  decision_trace?: DecisionTrace
  request_id?: string
  tool_results?: ToolResult[]
}

export type MessagePage = {
  items: ChatMessage[]
  total: number
}

export type StreamEvent =
  | { type: 'delta'; text: string }
      | {
      type: 'done'
      message_id?: string
      text: string
      citations: Citation[]
      injected_memory_ids?: string[]
      inbox_created?: number
      attachments?: ChatAttachment[]
      retrieval_meta?: RetrievalMeta
      decision_trace?: DecisionTrace
      request_id?: string
      tool_results?: ToolResult[]
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
  confidence?: number
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
  confidence?: number
  participants?: string[]
  causal_in?: { event_id: string; title: string; kind: string }[]
  causal_out?: { event_id: string; title: string; kind: string }[]
  memories: { id: string; text: string }[]
  verbatim?: { id: string; text: string }[]
  attachments: { id: string; type: string; text: string }[]
  forbidden?: boolean
}

export type ApiError = Error & { status: number; code?: string }

export type InboxItem = {
  id: string
  kind?: string
  status?: string
  payload?: { text?: string; conflicts_with?: string }
  conflicts_with?: string
  conflict_memory_text?: string
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
  parser?: string | null
  media_kind?: string | null
  chunks_parsed?: number
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
  latency_ms?: number
  citation_subset_rate?: number
  ragas_faithfulness?: number | null
  ragas_n?: number
  ragas_skipped?: boolean
  judge_status?: 'configured' | 'missing_key' | 'same_as_generator'
  generation_p0_pass?: boolean
  n_cases?: number
  n_leaking_cases?: number
  refuse_text_leak_count?: number
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
  citation_subset?: boolean
  ragas_faithfulness?: number | null
  text?: string
  injected_memory_ids?: string[]
  citations?: string[]
  text_leak?: boolean
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
  total?: number
  forbidden?: boolean
}

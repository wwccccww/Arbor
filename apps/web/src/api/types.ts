export type Persona = {
  id: string
  skin?: string
  display_name: string
  one_liner?: string
  taboos?: string[]
  relationships?: { name: string; kind: string }[]
  personality?: { traits?: string[] }
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

export type ChatMessage = {
  id: string
  role: string
  text: string
  citations: Citation[]
  inbox_created?: number
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

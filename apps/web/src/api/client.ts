import type { Session } from '../session'
import type {
  ApiError,
  AuditList,
  ChatAttachment,
  ChatMessage,
  Citation,
  EvalRun,
  EventCard,
  EventTree,
  InboxItem,
  InboxList,
  MemberList,
  MemoryList,
  Persona,
  PersonaDraft,
  PersonaGrant,
  PersonaPatch,
  Tenant,
  TenantMember,
  Thread,
  ThreadExport,
} from './types'

function asCitations(raw: unknown): Citation[] {
  if (!Array.isArray(raw)) return []
  return raw.map((item) => {
    if (typeof item === 'string') return { memory_id: item }
    if (item && typeof item === 'object') return item as Citation
    return {}
  })
}

async function parseError(res: Response): Promise<ApiError> {
  let code: string | undefined
  let message = res.statusText
  try {
    const body = await res.json()
    code = body?.error?.code
    if (body?.error?.message) message = body.error.message
  } catch {
    /* keep statusText */
  }
  const err = new Error(message) as ApiError
  err.status = res.status
  err.code = code
  return err
}

export function createClient(session: Session, fetchImpl: typeof fetch = fetch) {
  async function request(path: string, init: RequestInit = {}): Promise<unknown> {
    const headers = new Headers(init.headers)
    headers.set('Authorization', `Bearer ${session.token}`)
    headers.set('X-Tenant-Id', session.tenantId)
    if (init.body && !(init.body instanceof FormData) && !headers.has('Content-Type')) {
      headers.set('Content-Type', 'application/json')
    }
    const res = await fetchImpl(`/v1${path}`, { ...init, headers })
    if (!res.ok) throw await parseError(res)
    if (res.status === 204) return null
    return await res.json()
  }

  return {
    async listPersonas(): Promise<Persona[]> {
      const body = (await request('/personas')) as { items: Persona[] }
      return body.items
    },

    async listTenants(): Promise<Tenant[]> {
      const body = (await request('/tenants')) as { items: Tenant[] }
      return body.items ?? []
    },

    async createPersona(draft: PersonaDraft): Promise<Persona> {
      return (await request('/personas', {
        method: 'POST',
        body: JSON.stringify({
          skin: draft.skin,
          display_name: draft.display_name,
          one_liner: draft.one_liner ?? '',
        }),
      })) as Persona
    },

    async getPersona(personaId: string): Promise<Persona> {
      return (await request(`/personas/${personaId}`)) as Persona
    },

    async patchPersona(personaId: string, patch: PersonaPatch): Promise<Persona> {
      return (await request(`/personas/${personaId}`, {
        method: 'PATCH',
        body: JSON.stringify(patch),
      })) as Persona
    },

    async listMembers(): Promise<MemberList> {
      try {
        const body = (await request(`/tenants/${session.tenantId}/members`)) as MemberList
        return { items: body.items ?? [] }
      } catch (err) {
        const status = (err as ApiError).status
        if (status === 403 || status === 404) {
          return { items: [], forbidden: true }
        }
        throw err
      }
    },

    async addMember(email: string, role = 'member'): Promise<TenantMember> {
      return (await request(`/tenants/${session.tenantId}/members`, {
        method: 'POST',
        body: JSON.stringify({ email, role }),
      })) as TenantMember
    },

    async patchMember(userId: string, role: string): Promise<{ user: { id: string }; role: string }> {
      return (await request(`/tenants/${session.tenantId}/members/${userId}`, {
        method: 'PATCH',
        body: JSON.stringify({ role }),
      })) as { user: { id: string }; role: string }
    },

    async replaceGrants(personaId: string, grants: PersonaGrant[]): Promise<{ ok: boolean; grants: PersonaGrant[] }> {
      return (await request(`/personas/${personaId}/grants`, {
        method: 'PUT',
        body: JSON.stringify({ grants }),
      })) as { ok: boolean; grants: PersonaGrant[] }
    },

    async listThreads(personaId: string): Promise<Thread[]> {
      const body = (await request(`/personas/${personaId}/threads`)) as { items: Thread[] }
      return body.items
    },

    async createThread(personaId: string): Promise<Thread> {
      return (await request(`/personas/${personaId}/threads`, { method: 'POST' })) as Thread
    },

    async listMessages(threadId: string): Promise<ChatMessage[]> {
      const body = (await request(`/threads/${threadId}/messages`)) as {
        items: {
          id: string
          role: string
          content?: string
          text?: string
          citations?: unknown
          attachments?: ChatAttachment[]
        }[]
      }
      return body.items.map((item) => ({
        id: item.id,
        role: item.role,
        text: item.content ?? item.text ?? '',
        citations: asCitations(item.citations),
        attachments: item.attachments ?? [],
      }))
    },

    async sendMessage(threadId: string, text: string, file?: File): Promise<ChatMessage> {
      const init: RequestInit = file
        ? (() => {
            const body = new FormData()
            body.append('text', text)
            body.append('file', file)
            return { method: 'POST', body }
          })()
        : {
            method: 'POST',
            body: JSON.stringify({ text, attachments: [] }),
          }
      const body = (await request(`/threads/${threadId}/messages`, init)) as {
        message_id: string
        role: string
        text: string
        citations?: unknown
        inbox_created?: number
        attachments?: ChatAttachment[]
      }
      return {
        id: body.message_id,
        role: body.role,
        text: body.text,
        citations: asCitations(body.citations),
        inbox_created: body.inbox_created ?? 0,
        attachments: body.attachments ?? [],
      }
    },

    async downloadAttachment(threadId: string, filename: string): Promise<Blob> {
      const headers = new Headers()
      headers.set('Authorization', `Bearer ${session.token}`)
      headers.set('X-Tenant-Id', session.tenantId)
      const res = await fetchImpl(`/v1/threads/${threadId}/attachments/${encodeURIComponent(filename)}`, { headers })
      if (!res.ok) throw await parseError(res)
      return await res.blob()
    },

    async exportThread(threadId: string): Promise<ThreadExport> {
      return (await request(`/threads/${threadId}/export`, { method: 'POST' })) as ThreadExport
    },

    async listInbox(personaId: string): Promise<InboxList> {
      try {
        const body = (await request(`/personas/${personaId}/inbox`)) as { items: InboxItem[] }
        return { items: body.items ?? [] }
      } catch (err) {
        const status = (err as ApiError).status
        if (status === 403 || status === 404) {
          return { items: [], forbidden: true }
        }
        throw err
      }
    },

    async confirmInbox(inboxId: string, opts: { markKeyEvent?: boolean } = {}): Promise<{ id: string; event_id?: string }> {
      return (await request(`/inbox/${inboxId}/confirm`, {
        method: 'POST',
        body: JSON.stringify({ mark_key_event: Boolean(opts.markKeyEvent) }),
      })) as { id: string; event_id?: string }
    },

    async dismissInbox(inboxId: string): Promise<void> {
      await request(`/inbox/${inboxId}/dismiss`, { method: 'POST' })
    },

    async importFile(
      personaId: string,
      file: File,
      hint?: string,
    ): Promise<{ job_id: string; status: string; inbox_created: number }> {
      const body = new FormData()
      body.append('file', file)
      if (hint) body.append('hint', hint)
      return (await request(`/personas/${personaId}/imports`, {
        method: 'POST',
        body,
      })) as { job_id: string; status: string; inbox_created: number }
    },

    async listMemories(personaId: string, opts: { type?: string } = {}): Promise<MemoryList> {
      const query = opts.type ? `?type=${encodeURIComponent(opts.type)}` : ''
      try {
        const body = (await request(`/personas/${personaId}/memories${query}`)) as MemoryList
        return { items: body.items ?? [], total: body.total ?? 0 }
      } catch (err) {
        const status = (err as ApiError).status
        if (status === 403 || status === 404) {
          return { items: [], total: 0, forbidden: true }
        }
        throw err
      }
    },

    async getEventTree(personaId: string, view: 'tree' | 'timeline' = 'tree'): Promise<EventTree> {
      try {
        const body = (await request(`/personas/${personaId}/events/tree?view=${view}`)) as EventTree
        return { nodes: body.nodes ?? [], edges: body.edges ?? [] }
      } catch (err) {
        const status = (err as ApiError).status
        if (status === 403 || status === 404) {
          return { nodes: [], edges: [], forbidden: true }
        }
        throw err
      }
    },

    async getEventCard(eventId: string): Promise<EventCard> {
      try {
        const body = (await request(`/events/${eventId}`)) as EventCard
        return {
          ...body,
          memories: body.memories ?? [],
          attachments: body.attachments ?? [],
        }
      } catch (err) {
        const status = (err as ApiError).status
        if (status === 403 || status === 404) {
          return { id: eventId, memories: [], attachments: [], forbidden: true }
        }
        throw err
      }
    },

    async listAuditLogs(opts: { action?: string } = {}): Promise<AuditList> {
      const query = opts.action ? `?action=${encodeURIComponent(opts.action)}` : ''
      try {
        const body = (await request(`/audit-logs${query}`)) as AuditList
        return { items: body.items ?? [] }
      } catch (err) {
        const status = (err as ApiError).status
        if (status === 403 || status === 404) {
          return { items: [], forbidden: true }
        }
        throw err
      }
    },

    async startEvalRun(strategy = 'layered_tree'): Promise<{ id: string }> {
      return (await request('/eval/runs', {
        method: 'POST',
        body: JSON.stringify({
          strategy,
          suite_version: 'v1',
          mode: 'retrieval',
        }),
      })) as { id: string }
    },

    async getEvalRun(runId: string): Promise<EvalRun> {
      return (await request(`/eval/runs/${runId}`)) as EvalRun
    },
  }
}

export type ArborClient = ReturnType<typeof createClient>

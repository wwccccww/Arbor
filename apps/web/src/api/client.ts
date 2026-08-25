import type { Session } from '../session'
import type {
  ApiError,
  AuthTokens,
  AuditList,
  ChatAttachment,
  ChatMessage,
  Citation,
  EvalRun,
  EventCard,
  EventTree,
  InboxItem,
  InboxList,
  ImportJob,
  Me,
  MemberList,
  MemoryList,
  MessagePage,
  Persona,
  PersonaDraft,
  PersonaGrant,
  PersonaPatch,
  StreamEvent,
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

export async function login(
  email: string,
  password: string,
  fetchImpl: typeof fetch = fetch,
): Promise<AuthTokens> {
  const res = await fetchImpl('/v1/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  })
  if (!res.ok) throw await parseError(res)
  return (await res.json()) as AuthTokens
}

export async function refreshSession(refreshToken: string, fetchImpl: typeof fetch = fetch): Promise<AuthTokens> {
  const res = await fetchImpl('/v1/auth/refresh', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ refresh_token: refreshToken }),
  })
  if (!res.ok) throw await parseError(res)
  return (await res.json()) as AuthTokens
}

export async function logout(refreshToken?: string, fetchImpl: typeof fetch = fetch): Promise<void> {
  await fetchImpl('/v1/auth/logout', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ refresh_token: refreshToken ?? '' }),
  })
}

export type ClientHooks = {
  onTokensRefreshed?: (tokens: AuthTokens) => void
  onUnauthorized?: () => void
}

export function createClient(
  session: Session,
  fetchImpl: typeof fetch = fetch,
  hooks: ClientHooks = {},
) {
  async function refreshAccessToken(): Promise<boolean> {
    if (!session.refreshToken) return false
    try {
      const tokens = await refreshSession(session.refreshToken, fetchImpl)
      session.token = tokens.access_token
      session.refreshToken = tokens.refresh_token
      hooks.onTokensRefreshed?.(tokens)
      return true
    } catch {
      hooks.onUnauthorized?.()
      return false
    }
  }

  async function request(path: string, init: RequestInit = {}, retried = false): Promise<unknown> {
    const headers = new Headers(init.headers)
    headers.set('Authorization', `Bearer ${session.token}`)
    headers.set('X-Tenant-Id', session.tenantId)
    if (init.body && !(init.body instanceof FormData) && !headers.has('Content-Type')) {
      headers.set('Content-Type', 'application/json')
    }
    const res = await fetchImpl(`/v1${path}`, { ...init, headers })
    if (res.status === 401) {
      if (!retried && (await refreshAccessToken())) {
        return request(path, init, true)
      }
      hooks.onUnauthorized?.()
      throw await parseError(res)
    }
    if (!res.ok) throw await parseError(res)
    if (res.status === 204) return null
    return await res.json()
  }

  return {
    async getMe(): Promise<Me> {
      return (await request('/me')) as Me
    },

    async listPersonas(): Promise<Persona[]> {
      const body = (await request('/personas')) as { items?: Persona[] }
      return body.items ?? []
    },

    async listTenants(): Promise<Tenant[]> {
      const body = (await request('/tenants')) as { items: Tenant[] }
      return body.items ?? []
    },

    async createTenant(name: string): Promise<Tenant> {
      return (await request('/tenants', {
        method: 'POST',
        body: JSON.stringify({ name }),
      })) as Tenant
    },

    async deleteTenant(tenantId: string): Promise<void> {
      await request(`/tenants/${tenantId}`, { method: 'DELETE' })
    },

    async createPersona(draft: PersonaDraft): Promise<Persona> {
      return (await request('/personas', {
        method: 'POST',
        body: JSON.stringify({
          skin: draft.skin,
          display_name: draft.display_name,
          one_liner: draft.one_liner ?? '',
          template: draft.template,
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
      const body = (await request(`/personas/${personaId}/threads`)) as { items?: Thread[] }
      return body.items ?? []
    },

    async createThread(personaId: string): Promise<Thread> {
      return (await request(`/personas/${personaId}/threads`, { method: 'POST' })) as Thread
    },

    async listMessages(
      threadId: string,
      opts: { limit?: number; offset?: number } = {},
    ): Promise<MessagePage> {
      const limit = opts.limit ?? 50
      const offset = opts.offset ?? 0
      const body = (await request(`/threads/${threadId}/messages?limit=${limit}&offset=${offset}`)) as {
        items: {
          id: string
          role: string
          content?: string
          text?: string
          citations?: unknown
          attachments?: ChatAttachment[]
        }[]
        total?: number
      }
      return {
        items: body.items.map((item) => ({
          id: item.id,
          role: item.role,
          text: item.content ?? item.text ?? '',
          citations: asCitations(item.citations),
          attachments: item.attachments ?? [],
        })),
        total: body.total ?? body.items.length,
      }
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

    async sendMessageStream(
      threadId: string,
      text: string,
      handlers: {
        onDelta: (chunk: string) => void
        onDone: (msg: ChatMessage, events: StreamEvent[]) => void
      },
      file?: File,
    ): Promise<void> {
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
      const headers = new Headers(init.headers)
      headers.set('Authorization', `Bearer ${session.token}`)
      headers.set('X-Tenant-Id', session.tenantId)
      if (init.body && !(init.body instanceof FormData)) {
        headers.set('Content-Type', 'application/json')
      }
      let res = await fetchImpl(`/v1/threads/${threadId}/messages?stream=true`, { ...init, headers })
      if (res.status === 401 && (await refreshAccessToken())) {
        headers.set('Authorization', `Bearer ${session.token}`)
        res = await fetchImpl(`/v1/threads/${threadId}/messages?stream=true`, { ...init, headers })
      }
      if (res.status === 401) {
        hooks.onUnauthorized?.()
        throw await parseError(res)
      }
      if (!res.ok) throw await parseError(res)
      if (!res.body) throw new Error('streaming not supported')

      const reader = res.body.getReader()
      const decoder = new TextDecoder()
      const events: StreamEvent[] = []
      let buffer = ''
      let parsedDone: StreamEvent | null = null
      for (;;) {
        const { value, done } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        let idx: number
        while ((idx = buffer.indexOf('\n\n')) !== -1) {
          const rawEvent = buffer.slice(0, idx)
          buffer = buffer.slice(idx + 2)
          const piece = rawEvent.trim()
          if (!piece.startsWith('data:')) continue
          const payload = piece.slice(5).trim()
          if (!payload) continue
          let event: StreamEvent
          try {
            event = JSON.parse(payload) as StreamEvent
          } catch {
            continue
          }
          events.push(event)
          if (event.type === 'delta' && event.text) {
            handlers.onDelta(event.text)
          } else if (event.type === 'done') {
            parsedDone = event
          }
        }
      }
      const doneEvent = (parsedDone as Extract<StreamEvent, { type: 'done' }> | null) ?? {
        type: 'done',
        text: '',
        citations: [],
      }
      handlers.onDone(
        {
          id: doneEvent.message_id ?? `stream-${Date.now()}`,
          role: 'assistant',
          text: doneEvent.text,
          citations: asCitations(doneEvent.citations),
          inbox_created: doneEvent.inbox_created ?? 0,
          attachments: doneEvent.attachments ?? [],
        },
        events,
      )
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

    async getImport(jobId: string): Promise<ImportJob> {
      try {
        const body = (await request(`/imports/${jobId}`)) as ImportJob
        return {
          id: body.id,
          status: body.status,
          filename: body.filename,
          persona_id: body.persona_id,
          inbox_created: body.inbox_created ?? 0,
          error: body.error,
        }
      } catch (err) {
        const status = (err as ApiError).status
        if (status === 403 || status === 404) {
          return { id: jobId, status: 'unknown', forbidden: true }
        }
        throw err
      }
    },

    async pollImport(jobId: string, opts: { intervalMs?: number; timeoutMs?: number } = {}): Promise<ImportJob> {
      const intervalMs = opts.intervalMs ?? 500
      const timeoutMs = opts.timeoutMs ?? 30000
      const start = Date.now()
      let job = await this.getImport(jobId)
      while (job.status === 'pending' || job.status === 'running') {
        if (Date.now() - start > timeoutMs) break
        await new Promise((resolve) => setTimeout(resolve, intervalMs))
        job = await this.getImport(jobId)
      }
      return job
    },

    async listMemories(
      personaId: string,
      opts: { type?: string; status?: string; event_id?: string; limit?: number; offset?: number } = {},
    ): Promise<MemoryList> {
      const params = new URLSearchParams()
      if (opts.type) params.set('type', opts.type)
      if (opts.status) params.set('status', opts.status)
      if (opts.event_id) params.set('event_id', opts.event_id)
      if (opts.limit != null) params.set('limit', String(opts.limit))
      if (opts.offset) params.set('offset', String(opts.offset))
      const query = params.size ? `?${params.toString()}` : ''
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

    async getEventTree(
      personaId: string,
      view: 'tree' | 'timeline' = 'tree',
      keyOnly = true,
    ): Promise<EventTree> {
      const params = new URLSearchParams({ view })
      if (!keyOnly) params.set('key_only', 'false')
      try {
        const body = (await request(`/personas/${personaId}/events/tree?${params.toString()}`)) as EventTree
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

    async listAuditLogs(
      opts: {
        action?: string
        persona_id?: string
        since?: string
        until?: string
        limit?: number
        offset?: number
      } = {},
    ): Promise<AuditList> {
      const params = new URLSearchParams()
      if (opts.action) params.set('action', opts.action)
      if (opts.persona_id) params.set('persona_id', opts.persona_id)
      if (opts.since) params.set('since', opts.since)
      if (opts.until) params.set('until', opts.until)
      const query = params.size ? `?${params.toString()}` : ''
      try {
        const body = (await request(`/audit-logs${query}`)) as AuditList
        const items = body.items ?? []
        const limit = opts.limit ?? items.length
        const offset = opts.offset ?? 0
        return {
          items: items.slice(offset, offset + limit),
          total: body.total ?? items.length,
        }
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

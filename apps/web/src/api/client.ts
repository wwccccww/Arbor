import type { Session } from '../session'
import type { ApiError, ChatMessage, Citation, EventTree, Persona, Thread } from './types'

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
    if (init.body && !headers.has('Content-Type')) {
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

    async getPersona(personaId: string): Promise<Persona> {
      return (await request(`/personas/${personaId}`)) as Persona
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
        items: { id: string; role: string; content?: string; text?: string; citations?: unknown }[]
      }
      return body.items.map((item) => ({
        id: item.id,
        role: item.role,
        text: item.content ?? item.text ?? '',
        citations: asCitations(item.citations),
      }))
    },

    async sendMessage(threadId: string, text: string): Promise<ChatMessage> {
      const body = (await request(`/threads/${threadId}/messages`, {
        method: 'POST',
        body: JSON.stringify({ text, attachments: [] }),
      })) as { message_id: string; role: string; text: string; citations?: unknown }
      return {
        id: body.message_id,
        role: body.role,
        text: body.text,
        citations: asCitations(body.citations),
      }
    },

    async getEventTree(personaId: string): Promise<EventTree> {
      try {
        const body = (await request(`/personas/${personaId}/events/tree`)) as EventTree
        return { nodes: body.nodes ?? [], edges: body.edges ?? [] }
      } catch (err) {
        const status = (err as ApiError).status
        if (status === 403 || status === 404) {
          return { nodes: [], edges: [], forbidden: true }
        }
        throw err
      }
    },
  }
}

export type ArborClient = ReturnType<typeof createClient>

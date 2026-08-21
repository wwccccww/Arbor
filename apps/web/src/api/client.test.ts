import { describe, expect, it, vi } from 'vitest'
import { createClient } from './client'
import { DEMO_OWNER } from '../session'

describe('createClient', () => {
  it('sends bearer and tenant headers to list personas', async () => {
    const fetchImpl = vi.fn(async () =>
      new Response(JSON.stringify({ items: [{ id: 'p1', display_name: '林夏' }] }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    ) as unknown as typeof fetch
    const client = createClient(DEMO_OWNER, fetchImpl)
    const items = await client.listPersonas()
    expect(items[0]?.display_name).toBe('林夏')
    expect(fetchImpl).toHaveBeenCalledTimes(1)
    const [url, init] = (fetchImpl as unknown as ReturnType<typeof vi.fn>).mock.calls[0]
    expect(url).toBe('/v1/personas')
    const headers = new Headers((init as RequestInit).headers)
    expect(headers.get('Authorization')).toBe('Bearer token-a')
    expect(headers.get('X-Tenant-Id')).toBe(DEMO_OWNER.tenantId)
  })

  it('loads the current user from /me', async () => {
    const fetchImpl = vi.fn(async () =>
      new Response(
        JSON.stringify({
          user: { id: '0a000000-0000-4000-a000-000000000002', email: 'demo-a@arbor.eval' },
          tenants: [],
        }),
        { status: 200, headers: { 'Content-Type': 'application/json' } },
      ),
    ) as unknown as typeof fetch
    const client = createClient(DEMO_OWNER, fetchImpl)
    const me = await client.getMe()
    expect(me.user.email).toBe('demo-a@arbor.eval')
    expect((fetchImpl as unknown as ReturnType<typeof vi.fn>).mock.calls[0][0]).toBe('/v1/me')
  })

  it('treats a missing event tree as empty rather than inventing nodes', async () => {
    const fetchImpl = vi.fn(
      async () =>
        new Response(JSON.stringify({ error: { code: 'NOT_FOUND', message: 'not found' } }), {
          status: 404,
          headers: { 'Content-Type': 'application/json' },
        }),
    ) as unknown as typeof fetch
    const client = createClient(DEMO_OWNER, fetchImpl)
    const tree = await client.getEventTree('linxia')
    expect(tree.nodes).toEqual([])
    expect(tree.forbidden).toBe(true)
  })

  it('asks the event tree API for a timeline view', async () => {
    const fetchImpl = vi.fn(async () =>
      new Response(JSON.stringify({ nodes: [], edges: [] }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    ) as unknown as typeof fetch
    const client = createClient(DEMO_OWNER, fetchImpl)
    await client.getEventTree('linxia', 'timeline')
    expect((fetchImpl as unknown as ReturnType<typeof vi.fn>).mock.calls[0][0]).toBe(
      '/v1/personas/linxia/events/tree?view=timeline',
    )
  })

  it('asks the event tree API for all events when key_only is off', async () => {
    const fetchImpl = vi.fn(async () =>
      new Response(JSON.stringify({ nodes: [], edges: [] }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    ) as unknown as typeof fetch
    const client = createClient(DEMO_OWNER, fetchImpl)
    await client.getEventTree('linxia', 'tree', false)
    expect((fetchImpl as unknown as ReturnType<typeof vi.fn>).mock.calls[0][0]).toBe(
      '/v1/personas/linxia/events/tree?view=tree&key_only=false',
    )
  })

  it('confirm and dismiss post to inbox routes', async () => {
    const fetchImpl = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input)
      if (url.endsWith('/confirm')) {
        expect(init?.method).toBe('POST')
        expect(JSON.parse(String(init?.body))).toEqual({ mark_key_event: false })
        return new Response(JSON.stringify({ id: 'mem-1', text: 'ok' }), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        })
      }
      return new Response(JSON.stringify({ ok: true }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      })
    }) as unknown as typeof fetch
    const client = createClient(DEMO_OWNER, fetchImpl)
    await client.confirmInbox('in-1')
    await client.dismissInbox('in-1')
    const urls = (fetchImpl as unknown as ReturnType<typeof vi.fn>).mock.calls.map((call) => String(call[0]))
    expect(urls).toContain('/v1/inbox/in-1/confirm')
    expect(urls).toContain('/v1/inbox/in-1/dismiss')
  })

  it('posts multipart imports without a json content type', async () => {
    const fetchImpl = vi.fn(async (_input: RequestInfo | URL, init?: RequestInit) => {
      expect(init?.body).toBeInstanceOf(FormData)
      expect(new Headers(init?.headers).get('Content-Type')).toBeNull()
      return new Response(JSON.stringify({ job_id: 'job-1', status: 'completed', inbox_created: 1 }), {
        status: 202,
        headers: { 'Content-Type': 'application/json' },
      })
    }) as unknown as typeof fetch
    const client = createClient(DEMO_OWNER, fetchImpl)
    const result = await client.importFile(
      'linxia',
      new File(['hello'], 'notes.txt', { type: 'text/plain' }),
      'fact',
    )
    expect(result.inbox_created).toBe(1)
    const [url, init] = (fetchImpl as unknown as ReturnType<typeof vi.fn>).mock.calls[0]
    expect(url).toBe('/v1/personas/linxia/imports')
    expect((init as RequestInit).method).toBe('POST')
    expect(((init as RequestInit).body as FormData).get('hint')).toBe('fact')
  })

  it('lists messages with limit, offset, and total', async () => {
    const fetchImpl = vi.fn(async () =>
      new Response(
        JSON.stringify({
          items: [{ id: 'm1', role: 'user', content: '还在吗', citations: [] }],
          total: 3,
        }),
        { status: 200, headers: { 'Content-Type': 'application/json' } },
      ),
    ) as unknown as typeof fetch
    const client = createClient(DEMO_OWNER, fetchImpl)
    const page = await client.listMessages('0a000000-0000-4000-a000-000000000030', { limit: 1, offset: 2 })
    expect(page.items[0]?.text).toBe('还在吗')
    expect(page.total).toBe(3)
    expect((fetchImpl as unknown as ReturnType<typeof vi.fn>).mock.calls[0][0]).toBe(
      '/v1/threads/0a000000-0000-4000-a000-000000000030/messages?limit=1&offset=2',
    )
  })

  it('lists memories with a superseded status filter', async () => {
    const fetchImpl = vi.fn(async () =>
      new Response(
        JSON.stringify({
          items: [{ id: 'old-1', text: '旧的猫咪名', type: 'fact', status: 'superseded' }],
          total: 1,
        }),
        { status: 200, headers: { 'Content-Type': 'application/json' } },
      ),
    ) as unknown as typeof fetch
    const client = createClient(DEMO_OWNER, fetchImpl)
    const page = await client.listMemories('linxia', { status: 'superseded' })
    expect(page.items[0]?.status).toBe('superseded')
    expect((fetchImpl as unknown as ReturnType<typeof vi.fn>).mock.calls[0][0]).toBe(
      '/v1/personas/linxia/memories?status=superseded',
    )
  })

  it('lists memories with limit and offset', async () => {
    const fetchImpl = vi.fn(async () =>
      new Response(
        JSON.stringify({
          items: [{ id: 'mem-2', text: '旧的猫咪名', type: 'fact' }],
          total: 3,
        }),
        { status: 200, headers: { 'Content-Type': 'application/json' } },
      ),
    ) as unknown as typeof fetch
    const client = createClient(DEMO_OWNER, fetchImpl)
    const page = await client.listMemories('linxia', { limit: 1, offset: 2 })
    expect(page.total).toBe(3)
    expect((fetchImpl as unknown as ReturnType<typeof vi.fn>).mock.calls[0][0]).toBe(
      '/v1/personas/linxia/memories?limit=1&offset=2',
    )
  })

  it('lists memories for one event', async () => {
    const fetchImpl = vi.fn(async () =>
      new Response(
        JSON.stringify({
          items: [{ id: 'cap-1', text: '合影：雨天的店门口', type: 'image_caption', event_id: 'evt-meet' }],
          total: 1,
        }),
        { status: 200, headers: { 'Content-Type': 'application/json' } },
      ),
    ) as unknown as typeof fetch
    const client = createClient(DEMO_OWNER, fetchImpl)
    await client.listMemories('linxia', { event_id: 'evt-meet' })
    expect((fetchImpl as unknown as ReturnType<typeof vi.fn>).mock.calls[0][0]).toBe(
      '/v1/personas/linxia/memories?event_id=evt-meet',
    )
  })

  it('loads an import job by id', async () => {
    const fetchImpl = vi.fn(async () =>
      new Response(
        JSON.stringify({
          id: 'job-1',
          status: 'completed',
          filename: 'notes.txt',
          persona_id: 'linxia',
          inbox_created: 1,
        }),
        { status: 200, headers: { 'Content-Type': 'application/json' } },
      ),
    ) as unknown as typeof fetch
    const client = createClient(DEMO_OWNER, fetchImpl)
    const job = await client.getImport('job-1')
    expect(job.filename).toBe('notes.txt')
    expect(job.inbox_created).toBe(1)
    expect((fetchImpl as unknown as ReturnType<typeof vi.fn>).mock.calls[0][0]).toBe('/v1/imports/job-1')
  })

  it('starts eval runs in retrieval mode only', async () => {
    const fetchImpl = vi.fn(async () =>
      new Response(JSON.stringify({ id: 'run-1' }), {
        status: 202,
        headers: { 'Content-Type': 'application/json' },
      }),
    ) as unknown as typeof fetch
    const client = createClient(DEMO_OWNER, fetchImpl)
    await client.startEvalRun()
    const [, init] = (fetchImpl as unknown as ReturnType<typeof vi.fn>).mock.calls[0]
    expect(JSON.parse(String((init as RequestInit).body))).toEqual({
      strategy: 'layered_tree',
      suite_version: 'v1',
      mode: 'retrieval',
    })
  })

  it('loads an event card and hides missing ones', async () => {
    const fetchImpl = vi.fn(async (input: RequestInfo | URL) => {
      if (String(input).endsWith('/events/evt-1')) {
        return new Response(
          JSON.stringify({
            id: 'evt-1',
            title: '面店争吵',
            memories: [{ id: 'mem-1', text: '吵过' }],
            attachments: [],
          }),
          { status: 200, headers: { 'Content-Type': 'application/json' } },
        )
      }
      return new Response(JSON.stringify({ error: { code: 'NOT_FOUND', message: 'not found' } }), {
        status: 404,
        headers: { 'Content-Type': 'application/json' },
      })
    }) as unknown as typeof fetch
    const client = createClient(DEMO_OWNER, fetchImpl)
    const card = await client.getEventCard('evt-1')
    expect(card.title).toBe('面店争吵')
    expect(card.memories).toHaveLength(1)
    const hidden = await client.getEventCard('missing')
    expect(hidden.forbidden).toBe(true)
    expect(hidden.memories).toEqual([])
  })
})

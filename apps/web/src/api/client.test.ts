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
})

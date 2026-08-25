import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { createClient } from '../api/client'
import { DEMO_OWNER } from '../session'
import { Workbench } from './Workbench'

function mockWorkbenchFetch() {
  return vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input)
    const method = (init as RequestInit | undefined)?.method ?? 'GET'
    if (url.includes('/personas/p1') && method === 'GET' && !url.includes('/threads')) {
      return json({ id: 'p1', display_name: '林夏', skin: 'companion', grants: [] })
    }
    if (url.includes('/personas/p1/threads') && method === 'GET') {
      return json({ items: [{ id: 't-1', persona_id: 'p1' }] })
    }
    if (url.includes('/events/tree')) {
      return json({ nodes: [], edges: [] })
    }
    if (url.includes('/personas/p1/inbox')) {
      return json({ items: [] })
    }
    if (url.includes('/personas/p1/memories')) {
      return json({ items: [], total: 0 })
    }
    if (url.includes('/tenants/') && url.includes('/members')) {
      return json({ items: [] })
    }
    if (url.includes('/threads/t-1/messages') && method === 'GET') {
      return json({ items: [{ id: 'm1', role: 'user', content: '你好', citations: [] }], total: 1 })
    }
    if (url.includes('/threads/t-1/messages') && method === 'POST') {
      return json({ error: { code: 'SERVER', message: 'send failed' } }, 500)
    }
    return json({ error: { code: 'NOT_FOUND', message: 'not found' } }, 404)
  }) as unknown as typeof fetch
}

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

describe('Workbench', () => {
  it('disables chat until the thread is ready and rolls back failed sends', async () => {
    const user = userEvent.setup()
    const fetchImpl = mockWorkbenchFetch()
    const client = createClient(DEMO_OWNER, fetchImpl)
    render(<Workbench client={client} personaId="p1" workspaceAdmin onBack={vi.fn()} />)

    expect(await screen.findByText('你好')).toBeInTheDocument()
    await user.type(screen.getByLabelText('发送消息'), '失败消息')
    const sendButton = screen.getByRole('button', { name: '发送' })
    expect(sendButton).not.toBeDisabled()
    await user.click(sendButton)

    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent('send failed')
    })
    expect(screen.queryByText('失败消息')).not.toBeInTheDocument()
    expect(screen.getByText('你好')).toBeInTheDocument()
  })
})

import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { createClient } from '../api/client'
import { DEMO_OWNER } from '../session'
import { Home } from './Home'

describe('Home', () => {
  it('shows the current user email from /me', async () => {
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

    render(
      <Home
        personas={[]}
        email={me.user.email}
        onOpen={vi.fn()}
        onCheckup={vi.fn()}
      />,
    )
    expect(screen.getByText('demo-a@arbor.eval')).toBeInTheDocument()
    expect((fetchImpl as unknown as ReturnType<typeof vi.fn>).mock.calls[0][0]).toBe('/v1/me')
  })

  it('shows runtime when the API reports a scripted backend', () => {
    render(
      <Home
        personas={[]}
        runtime={{ llm: 'scripted', store: 'memory' }}
        onOpen={vi.fn()}
        onCheckup={vi.fn()}
      />,
    )
    expect(screen.getByText(/当前是脚本回复/)).toBeInTheDocument()
    expect(screen.getByText(/内存库/)).toBeInTheDocument()
  })

  it('shows DeepSeek and Postgres when runtime is live', () => {
    render(
      <Home
        personas={[]}
        runtime={{ llm: 'deepseek', store: 'postgres' }}
        onOpen={vi.fn()}
        onCheckup={vi.fn()}
      />,
    )
    expect(screen.getByText(/DeepSeek 对话已接通/)).toBeInTheDocument()
    expect(screen.getByText(/Postgres 持久化/)).toBeInTheDocument()
  })

  it('shows real embedding when runtime reports bge-m3', () => {
    render(
      <Home
        personas={[]}
        runtime={{ llm: 'deepseek', store: 'memory', embed: 'bge-m3' }}
        onOpen={vi.fn()}
        onCheckup={vi.fn()}
      />,
    )
    expect(screen.getByText(/嵌入 bge-m3/)).toBeInTheDocument()
  })
})

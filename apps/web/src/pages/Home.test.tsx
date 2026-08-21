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
})

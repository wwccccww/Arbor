import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest'
import App from './App'
import { DEMO_TENANT } from './session'

describe('App', () => {
  beforeEach(() => {
    window.localStorage.clear()
    window.location.hash = '#/'
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('shows the login screen without a saved session', () => {
    render(<App />)
    expect(screen.getByRole('button', { name: '登录' })).toBeInTheDocument()
  })

  it('restores a saved session into the home page', async () => {
    window.localStorage.setItem(
      'arbor.session',
      JSON.stringify({ token: 'token-a', refreshToken: 'ref-a', tenantId: DEMO_TENANT }),
    )
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input)
        if (url.endsWith('/me')) {
          return new Response(
            JSON.stringify({
              user: { id: 'u1', email: 'demo-a@arbor.eval' },
              tenants: [{ id: DEMO_TENANT, name: '演示', role: 'owner' }],
            }),
            { status: 200, headers: { 'Content-Type': 'application/json' } },
          )
        }
        if (url.endsWith('/personas')) {
          return new Response(JSON.stringify({ items: [] }), {
            status: 200,
            headers: { 'Content-Type': 'application/json' },
          })
        }
        if (url.endsWith('/tenants')) {
          return new Response(JSON.stringify({ items: [{ id: DEMO_TENANT, name: '演示', role: 'owner' }] }), {
            status: 200,
            headers: { 'Content-Type': 'application/json' },
          })
        }
        return new Response(JSON.stringify({ items: [] }), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        })
      }),
    )
    render(<App />)
    expect(await screen.findByText(/还没有人设/)).toBeInTheDocument()
  })
})

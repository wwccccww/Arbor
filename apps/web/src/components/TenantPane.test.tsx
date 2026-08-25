import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { createClient } from '../api/client'
import { DEMO_OWNER, DEMO_TENANT } from '../session'
import { TenantPane } from './TenantPane'

describe('TenantPane', () => {
  it('creates a workspace then deletes the empty current one', async () => {
    const user = userEvent.setup()
    vi.stubGlobal('confirm', vi.fn(() => true))
    const fetchImpl = vi.fn(async (_input: RequestInfo | URL, init?: RequestInit) => {
      if (init?.method === 'POST') {
        return new Response(JSON.stringify({ id: 'new-tenant', name: '私人空间', role: 'owner' }), {
          status: 201,
          headers: { 'Content-Type': 'application/json' },
        })
      }
      if (init?.method === 'DELETE') {
        return new Response(null, { status: 204 })
      }
      return new Response(JSON.stringify({ error: { code: 'NOT_FOUND', message: 'not found' } }), { status: 404 })
    }) as unknown as typeof fetch
    const client = createClient(DEMO_OWNER, fetchImpl)

    render(
      <TenantPane
        tenants={[
          { id: DEMO_TENANT, name: '演示', role: 'owner' },
          { id: 'new-tenant', name: '私人空间', role: 'owner' },
        ]}
        currentId="new-tenant"
        canDelete
        onSwitch={vi.fn()}
        onCreate={(name) => {
          void client.createTenant(name)
        }}
        onDelete={() => {
          void client.deleteTenant('new-tenant')
        }}
      />,
    )

    await user.type(screen.getByLabelText('空间名'), '私人空间')
    await user.click(screen.getByRole('button', { name: '创建空间' }))
    const createCall = (fetchImpl as unknown as ReturnType<typeof vi.fn>).mock.calls.find(
      (call) => String(call[0]) === '/v1/tenants' && (call[1] as RequestInit).method === 'POST',
    )
    expect(JSON.parse(String((createCall?.[1] as RequestInit).body))).toEqual({ name: '私人空间' })

    await user.click(screen.getByRole('button', { name: '删除当前空间' }))
    const deleteCall = (fetchImpl as unknown as ReturnType<typeof vi.fn>).mock.calls.find(
      (call) => (call[1] as RequestInit).method === 'DELETE',
    )
    expect(deleteCall?.[0]).toBe('/v1/tenants/new-tenant')
  })

  it('hides delete when the workspace still has personas', () => {
    render(
      <TenantPane
        tenants={[{ id: DEMO_TENANT, name: '演示', role: 'owner' }]}
        currentId={DEMO_TENANT}
        onSwitch={vi.fn()}
        onCreate={vi.fn()}
      />,
    )
    expect(screen.queryByRole('button', { name: '删除当前空间' })).not.toBeInTheDocument()
  })
})

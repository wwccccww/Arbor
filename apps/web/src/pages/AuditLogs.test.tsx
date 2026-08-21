import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { createClient } from '../api/client'
import { DEMO_OWNER } from '../session'
import { AuditLogs } from './AuditLogs'

describe('AuditLogs', () => {
  it('lists sanitized audit rows and filters by action', async () => {
    const user = userEvent.setup()
    const fetchImpl = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input)
      const filtered = url.includes('action=thread.export')
      return new Response(
        JSON.stringify({
          items: filtered
            ? [{ id: 'log-2', action: 'thread.export', resource_type: 'thread', resource_id: 't1', payload: { message_count: 2 } }]
            : [
                { id: 'log-1', action: 'persona.update', resource_type: 'persona', resource_id: 'p1', payload: { fields: ['one_liner'] } },
                { id: 'log-2', action: 'thread.export', resource_type: 'thread', resource_id: 't1', payload: { message_count: 2 } },
              ],
        }),
        { status: 200, headers: { 'Content-Type': 'application/json' } },
      )
    }) as unknown as typeof fetch

    render(<AuditLogs client={createClient(DEMO_OWNER, fetchImpl)} onBack={vi.fn()} />)
    expect(await screen.findByText('persona.update')).toBeInTheDocument()
    expect(screen.getByText('{"fields":["one_liner"]}')).toBeInTheDocument()
    expect(screen.queryByText('还在吗')).not.toBeInTheDocument()

    await user.selectOptions(screen.getByLabelText('动作'), 'thread.export')
    expect(await screen.findByText('{"message_count":2}')).toBeInTheDocument()
    expect(screen.queryByText('persona.update')).not.toBeInTheDocument()
    const urls = (fetchImpl as unknown as ReturnType<typeof vi.fn>).mock.calls.map((call) => String(call[0]))
    expect(urls).toContain('/v1/audit-logs')
    expect(urls).toContain('/v1/audit-logs?action=thread.export')
  })

  it('hides payloads without workspace admin', async () => {
    const fetchImpl = vi.fn(async () =>
      new Response(JSON.stringify({ error: { code: 'FORBIDDEN_WORKSPACE', message: 'admin required' } }), {
        status: 403,
        headers: { 'Content-Type': 'application/json' },
      }),
    ) as unknown as typeof fetch
    render(<AuditLogs client={createClient(DEMO_OWNER, fetchImpl)} onBack={vi.fn()} />)
    expect(await screen.findByRole('alert')).toHaveTextContent('没有审计权限')
    expect(screen.queryByText('persona.update')).not.toBeInTheDocument()
    expect(screen.queryByLabelText('动作')).not.toBeInTheDocument()
  })
})

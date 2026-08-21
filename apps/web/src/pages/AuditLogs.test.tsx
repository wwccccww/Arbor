import { fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { createClient } from '../api/client'
import { DEMO_OWNER } from '../session'
import { AuditLogs } from './AuditLogs'

const LINXIA = '0a000000-0000-4000-a000-000000000010'

function jsonOk(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

describe('AuditLogs', () => {
  it('lists sanitized audit rows and filters by action and persona', async () => {
    const user = userEvent.setup()
    const fetchImpl = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input)
      if (url.endsWith('/personas')) {
        return jsonOk({ items: [{ id: LINXIA, display_name: '林夏' }] })
      }
      const byPersona = url.includes(`persona_id=${LINXIA}`)
      const byAction = url.includes('action=thread.export')
      return jsonOk({
        items: byPersona
          ? [{ id: 'log-1', action: 'persona.update', resource_type: 'persona', resource_id: 'p1', persona_id: LINXIA, payload: { fields: ['one_liner'] } }]
          : byAction
            ? [{ id: 'log-2', action: 'thread.export', resource_type: 'thread', resource_id: 't1', payload: { message_count: 2 } }]
            : [
                { id: 'log-1', action: 'persona.update', resource_type: 'persona', resource_id: 'p1', payload: { fields: ['one_liner'] } },
                { id: 'log-2', action: 'thread.export', resource_type: 'thread', resource_id: 't1', payload: { message_count: 2 } },
              ],
      })
    }) as unknown as typeof fetch

    render(<AuditLogs client={createClient(DEMO_OWNER, fetchImpl)} onBack={vi.fn()} />)
    expect(await screen.findByText('persona.update')).toBeInTheDocument()
    expect(screen.getByText('{"fields":["one_liner"]}')).toBeInTheDocument()
    expect(screen.queryByText('还在吗')).not.toBeInTheDocument()

    await user.selectOptions(screen.getByLabelText('动作'), 'thread.export')
    expect(await screen.findByText('{"message_count":2}')).toBeInTheDocument()
    expect(screen.queryByText('persona.update')).not.toBeInTheDocument()

    expect(await screen.findByRole('option', { name: '林夏' })).toBeInTheDocument()
    await user.selectOptions(screen.getByLabelText('人设'), LINXIA)
    expect(await screen.findByText('persona.update')).toBeInTheDocument()
    const urls = (fetchImpl as unknown as ReturnType<typeof vi.fn>).mock.calls.map((call) => String(call[0]))
    expect(urls).toContain('/v1/audit-logs')
    expect(urls).toContain('/v1/audit-logs?action=thread.export')
    expect(urls).toContain(`/v1/audit-logs?action=thread.export&persona_id=${LINXIA}`)
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
    expect(screen.queryByLabelText('人设')).not.toBeInTheDocument()
    expect(screen.queryByLabelText('起始')).not.toBeInTheDocument()
    expect(screen.queryByLabelText('截止')).not.toBeInTheDocument()
  })

  it('filters by since and until', async () => {
    const fetchImpl = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input)
      if (url.endsWith('/personas')) {
        return jsonOk({ items: [] })
      }
      const ranged = url.includes('since=') && url.includes('until=')
      return jsonOk({
        items: ranged
          ? [{ id: 'log-1', action: 'persona.update', resource_type: 'persona', resource_id: 'p1', payload: { fields: ['one_liner'] } }]
          : [
              { id: 'log-1', action: 'persona.update', resource_type: 'persona', resource_id: 'p1', payload: { fields: ['one_liner'] } },
              { id: 'log-2', action: 'thread.export', resource_type: 'thread', resource_id: 't1', payload: { message_count: 2 } },
            ],
      })
    }) as unknown as typeof fetch

    render(<AuditLogs client={createClient(DEMO_OWNER, fetchImpl)} onBack={vi.fn()} />)
    expect(await screen.findByText('thread.export')).toBeInTheDocument()

    fireEvent.change(screen.getByLabelText('起始'), { target: { value: '2026-08-20' } })
    fireEvent.change(screen.getByLabelText('截止'), { target: { value: '2026-08-20' } })
    expect(await screen.findByText('{"fields":["one_liner"]}')).toBeInTheDocument()
    expect(screen.queryByText('thread.export')).not.toBeInTheDocument()
    const urls = (fetchImpl as unknown as ReturnType<typeof vi.fn>).mock.calls.map((call) => String(call[0]))
    expect(urls.some((url) => url.includes('since=2026-08-20T00%3A00%3A00') && url.includes('until=2026-08-20T23%3A59%3A59'))).toBe(true)
  })
})

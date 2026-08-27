import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { createClient } from '../api/client'
import { DEMO_OWNER } from '../session'
import { CalendarToolPane } from './CalendarToolPane'

describe('CalendarToolPane', () => {
  it('shows hint when calendar tool is not allowed', () => {
    render(
      <CalendarToolPane
        client={createClient(DEMO_OWNER)}
        personaId="p1"
        allowed={false}
      />,
    )
    expect(screen.getByText(/calendar/)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '查询日程' })).not.toBeInTheDocument()
  })

  it('queries calendar via API when allowed', async () => {
    const user = userEvent.setup()
    const fetchImpl = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input)
      if (url.endsWith('/tools/calendar') && init?.method === 'POST') {
        return new Response(
          JSON.stringify({
            tool: 'calendar',
            summary: '演示日程',
            events: [{ title: '复盘', start: '2026-08-27T10:00:00' }],
          }),
          { status: 200, headers: { 'Content-Type': 'application/json' } },
        )
      }
      return new Response(JSON.stringify({ error: { code: 'NOT_FOUND', message: 'not found' } }), { status: 404 })
    }) as unknown as typeof fetch
    const client = createClient(DEMO_OWNER, fetchImpl)

    render(<CalendarToolPane client={client} personaId="p1" allowed />)

    await user.clear(screen.getByLabelText('查询'))
    await user.type(screen.getByLabelText('查询'), '这周安排')
    await user.click(screen.getByRole('button', { name: '查询日程' }))

    const postCall = (fetchImpl as unknown as ReturnType<typeof vi.fn>).mock.calls.find((call) =>
      String(call[0]).endsWith('/v1/personas/p1/tools/calendar'),
    )
    expect(postCall).toBeTruthy()
    expect(JSON.parse(String((postCall?.[1] as RequestInit).body))).toEqual({ query_text: '这周安排' })
    expect(await screen.findByText('工具结果（1）')).toBeInTheDocument()
    expect(screen.getByText(/复盘/)).toBeInTheDocument()
  })
})

import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { createClient } from '../api/client'
import { DEMO_OWNER } from '../session'
import { TicketToolPane } from './TicketToolPane'

describe('TicketToolPane', () => {
  it('shows hint when ticket tool is not allowed', () => {
    render(
      <TicketToolPane
        client={createClient(DEMO_OWNER)}
        personaId="p1"
        allowed={false}
      />,
    )
    expect(screen.getByText(/工具权限/)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '登记工单' })).not.toBeInTheDocument()
  })

  it('submits ticket via API when allowed', async () => {
    const user = userEvent.setup()
    const fetchImpl = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input)
      if (url.endsWith('/tools/ticket') && init?.method === 'POST') {
        return new Response(
          JSON.stringify({
            tool: 'ticket',
            ticket_id: 'stub-ticket-001',
            title: '空调故障',
            note: '演示工单',
          }),
          { status: 200, headers: { 'Content-Type': 'application/json' } },
        )
      }
      return new Response(JSON.stringify({ error: { code: 'NOT_FOUND', message: 'not found' } }), { status: 404 })
    }) as unknown as typeof fetch
    const client = createClient(DEMO_OWNER, fetchImpl)

    render(<TicketToolPane client={client} personaId="p1" allowed />)

    await user.type(screen.getByLabelText('标题'), '空调故障')
    await user.type(screen.getByLabelText('描述'), '制冷不足')
    await user.click(screen.getByRole('button', { name: '登记工单' }))

    const postCall = (fetchImpl as unknown as ReturnType<typeof vi.fn>).mock.calls.find((call) =>
      String(call[0]).endsWith('/v1/personas/p1/tools/ticket'),
    )
    expect(postCall).toBeTruthy()
    expect(JSON.parse(String((postCall?.[1] as RequestInit).body))).toEqual({
      title: '空调故障',
      description: '制冷不足',
    })
    expect(await screen.findByText(/stub-ticket-001/)).toBeInTheDocument()
  })
})

import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { createClient } from '../api/client'
import { DEMO_OWNER } from '../session'
import { GrantsPane } from './GrantsPane'

const OWNER = {
  user: { id: '0a000000-0000-4000-a000-000000000002', email: 'demo-a@arbor.eval' },
  role: 'owner',
}
const MEMBER = {
  user: { id: '0a000000-0000-4000-a000-000000000003', email: 'member-a@arbor.eval' },
  role: 'member',
}

describe('GrantsPane', () => {
  it('does not render without admin', () => {
    render(
      <GrantsPane
        members={[MEMBER]}
        grants={[{ user_id: MEMBER.user.id, capabilities: ['chat'] }]}
        forbidden
        onSave={vi.fn()}
      />,
    )
    expect(screen.queryByRole('button', { name: '保存授权' })).not.toBeInTheDocument()
    expect(screen.queryByText('谁能用这个人')).not.toBeInTheDocument()
  })

  it('saves checked capabilities as a full replace', async () => {
    const user = userEvent.setup()
    const fetchImpl = vi.fn(async () =>
      new Response(
        JSON.stringify({
          ok: true,
          grants: [{ user_id: MEMBER.user.id, capabilities: ['chat', 'write_memory'] }],
        }),
        { status: 200, headers: { 'Content-Type': 'application/json' } },
      ),
    ) as unknown as typeof fetch
    const client = createClient(DEMO_OWNER, fetchImpl)

    render(
      <GrantsPane
        members={[OWNER, MEMBER]}
        grants={[{ user_id: MEMBER.user.id, capabilities: ['chat'] }]}
        onSave={(grants) => {
          void client.replaceGrants('0a000000-0000-4000-a000-000000000010', grants)
        }}
      />,
    )

    expect(screen.getByRole('checkbox', { name: 'member-a@arbor.eval 对话' })).toBeChecked()
    expect(screen.getByRole('checkbox', { name: 'member-a@arbor.eval 写记忆' })).not.toBeChecked()
    await user.click(screen.getByRole('checkbox', { name: 'member-a@arbor.eval 写记忆' }))
    await user.click(screen.getByRole('button', { name: '保存授权' }))

    expect(fetchImpl).toHaveBeenCalled()
    const [url, init] = (fetchImpl as unknown as ReturnType<typeof vi.fn>).mock.calls[0]
    expect(url).toBe('/v1/personas/0a000000-0000-4000-a000-000000000010/grants')
    expect((init as RequestInit).method).toBe('PUT')
    expect(JSON.parse(String((init as RequestInit).body))).toEqual({
      grants: [{ user_id: MEMBER.user.id, capabilities: ['chat', 'write_memory'] }],
    })
  })
})

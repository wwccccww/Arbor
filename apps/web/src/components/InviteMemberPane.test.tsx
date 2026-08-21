import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { createClient } from '../api/client'
import { DEMO_OWNER } from '../session'
import { InviteMemberPane } from './InviteMemberPane'

describe('InviteMemberPane', () => {
  it('does not render without workspace admin', () => {
    render(<InviteMemberPane members={[]} forbidden onInvite={vi.fn()} />)
    expect(screen.queryByRole('button', { name: '邀请' })).not.toBeInTheDocument()
    expect(screen.queryByText('空间成员')).not.toBeInTheDocument()
  })

  it('posts an invite to the members API', async () => {
    const user = userEvent.setup()
    const fetchImpl = vi.fn(async () =>
      new Response(
        JSON.stringify({
          user: { id: 'new-user', email: 'c@d.com' },
          role: 'member',
        }),
        { status: 201, headers: { 'Content-Type': 'application/json' } },
      ),
    ) as unknown as typeof fetch
    const client = createClient(DEMO_OWNER, fetchImpl)

    render(
      <InviteMemberPane
        members={[{ user: { id: 'owner', email: 'demo-a@arbor.eval' }, role: 'owner' }]}
        onInvite={(email, role) => {
          void client.addMember(email, role)
        }}
      />,
    )

    await user.type(screen.getByLabelText('邮箱'), 'c@d.com')
    await user.click(screen.getByRole('button', { name: '邀请' }))

    expect(fetchImpl).toHaveBeenCalled()
    const [url, init] = (fetchImpl as unknown as ReturnType<typeof vi.fn>).mock.calls[0]
    expect(url).toBe('/v1/tenants/0a000000-0000-4000-a000-000000000001/members')
    expect((init as RequestInit).method).toBe('POST')
    expect(JSON.parse(String((init as RequestInit).body))).toEqual({
      email: 'c@d.com',
      role: 'member',
    })
  })
})

import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { createClient } from '../api/client'
import { DEMO_OWNER } from '../session'
import { CreatePersonaPane } from './CreatePersonaPane'

describe('CreatePersonaPane', () => {
  it('does not render without workspace admin', () => {
    render(<CreatePersonaPane forbidden onCreate={vi.fn()} />)
    expect(screen.queryByRole('button', { name: '创建' })).not.toBeInTheDocument()
    expect(screen.queryByText('创建人设')).not.toBeInTheDocument()
  })

  it('posts a new persona to the personas API', async () => {
    const user = userEvent.setup()
    const fetchImpl = vi.fn(async () =>
      new Response(
        JSON.stringify({
          id: 'new-persona',
          skin: 'employee',
          display_name: '阿宁',
          one_liner: '前台数字员工',
          grants: [],
        }),
        { status: 201, headers: { 'Content-Type': 'application/json' } },
      ),
    ) as unknown as typeof fetch
    const client = createClient(DEMO_OWNER, fetchImpl)

    render(
      <CreatePersonaPane
        onCreate={(draft) => {
          void client.createPersona(draft)
        }}
      />,
    )

    await user.selectOptions(screen.getByLabelText('类型'), 'employee')
    await user.type(screen.getByLabelText('显示名'), '阿宁')
    await user.type(screen.getByLabelText('一句话'), '前台数字员工')
    await user.click(screen.getByRole('button', { name: '创建' }))

    expect(fetchImpl).toHaveBeenCalled()
    const [url, init] = (fetchImpl as unknown as ReturnType<typeof vi.fn>).mock.calls[0]
    expect(url).toBe('/v1/personas')
    expect((init as RequestInit).method).toBe('POST')
    expect(JSON.parse(String((init as RequestInit).body))).toEqual({
      skin: 'employee',
      display_name: '阿宁',
      one_liner: '前台数字员工',
    })
  })
})

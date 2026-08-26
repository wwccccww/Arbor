import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { createClient } from '../api/client'
import { DEMO_OWNER } from '../session'
import { ProfilePane } from './ProfilePane'

describe('ProfilePane', () => {
  it('hides taboos when the API omitted them', () => {
    render(
      <ProfilePane
        persona={{
          id: 'linxia',
          display_name: '林夏',
          one_liner: '住在杭州的陪伴助手',
        }}
      />,
    )
    expect(screen.getByText('林夏')).toBeInTheDocument()
    expect(screen.queryByText('禁忌')).not.toBeInTheDocument()
    expect(screen.queryByText('香菜')).not.toBeInTheDocument()
    expect(screen.queryByText('性格')).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '保存档案' })).not.toBeInTheDocument()
  })

  it('shows taboos when the API included them', () => {
    render(
      <ProfilePane
        persona={{
          id: 'linxia',
          display_name: '林夏',
          taboos: ['香菜'],
        }}
      />,
    )
    expect(screen.getByText('禁忌')).toBeInTheDocument()
    expect(screen.getByText('香菜')).toBeInTheDocument()
  })

  it('patches skin, personality and relationships when admin', async () => {
    const user = userEvent.setup()
    const fetchImpl = vi.fn(async () =>
      new Response(
        JSON.stringify({
          id: '0a000000-0000-4000-a000-000000000010',
          display_name: '林夏',
          one_liner: '住在杭州，不吃香菜',
          taboos: ['香菜', '冷场'],
          personality: { traits: ['冷静'] },
          relationships: [{ name: '用户', kind: 'partner' }],
          skin: 'employee',
          grants: [],
        }),
        { status: 200, headers: { 'Content-Type': 'application/json' } },
      ),
    ) as unknown as typeof fetch
    const client = createClient(DEMO_OWNER, fetchImpl)

    render(
      <ProfilePane
        persona={{
          id: '0a000000-0000-4000-a000-000000000010',
          display_name: '林夏',
          one_liner: '住在杭州的陪伴助手',
          taboos: ['香菜'],
          grants: [],
        }}
        editable
        onSave={(patch) => {
          void client.patchPersona('0a000000-0000-4000-a000-000000000010', patch)
        }}
      />,
    )

    await user.selectOptions(screen.getByLabelText('类型'), 'employee')
    await user.clear(screen.getByLabelText('一句话'))
    await user.type(screen.getByLabelText('一句话'), '住在杭州，不吃香菜')
    await user.type(screen.getByLabelText('性格'), '冷静')
    await user.type(screen.getByLabelText('禁忌'), '\n冷场')
    await user.type(screen.getByLabelText('关系'), '用户 · partner')
    await user.click(screen.getByRole('button', { name: '保存档案' }))

    expect(fetchImpl).toHaveBeenCalled()
    const [url, init] = (fetchImpl as unknown as ReturnType<typeof vi.fn>).mock.calls[0]
    expect(url).toBe('/v1/personas/0a000000-0000-4000-a000-000000000010')
    expect((init as RequestInit).method).toBe('PATCH')
    expect(JSON.parse(String((init as RequestInit).body))).toEqual({
      skin: 'employee',
      display_name: '林夏',
      one_liner: '住在杭州，不吃香菜',
      taboos: ['香菜', '冷场'],
      personality: { traits: ['冷静'] },
      relationships: [{ name: '用户', kind: 'partner' }],
      tool_policy: { allowed_tools: [], notes: '' },
    })
  })
})

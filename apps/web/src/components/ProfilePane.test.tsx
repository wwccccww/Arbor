import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
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
})

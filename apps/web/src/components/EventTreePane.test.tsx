import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { EventTreePane } from './EventTreePane'

describe('EventTreePane', () => {
  it('shows an empty state without read_memory', () => {
    render(<EventTreePane nodes={[]} forbidden />)
    expect(screen.getByText('没有记忆权限，事件树为空。')).toBeInTheDocument()
    expect(screen.queryByRole('list')).not.toBeInTheDocument()
  })
})

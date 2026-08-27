import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { DemoGuidePane } from './DemoGuidePane'

describe('DemoGuidePane', () => {
  it('marks import done when inbox has items', () => {
    render(<DemoGuidePane inboxCount={2} eventCount={0} />)
    expect(screen.getByText('导入旧聊天').closest('[data-done="true"]')).toBeInTheDocument()
  })

  it('opens checkup when requested', async () => {
    const user = userEvent.setup()
    const onOpenCheckup = vi.fn()
    render(<DemoGuidePane onOpenCheckup={onOpenCheckup} />)
    await user.click(screen.getByRole('button', { name: '打开记忆体检' }))
    expect(onOpenCheckup).toHaveBeenCalled()
  })
})

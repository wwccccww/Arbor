import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { ChatPane } from './ChatPane'

describe('ChatPane', () => {
  it('renders assistant citations in the reply area', async () => {
    const user = userEvent.setup()
    const onJump = vi.fn()
    render(
      <ChatPane
        messages={[
          {
            id: 'a1',
            role: 'assistant',
            text: '上次是在西湖附近吵的。',
            citations: [{ memory_id: 'mem-1', event_id: 'evt-1', preview: '去年十一月在西湖' }],
          },
        ]}
        onSend={vi.fn()}
        onJump={onJump}
      />,
    )
    expect(screen.getByLabelText('依据')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: '去年十一月在西湖' }))
    expect(onJump).toHaveBeenCalledWith('evt-1')
  })
})

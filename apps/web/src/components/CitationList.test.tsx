import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { CitationList } from './CitationList'

describe('CitationList', () => {
  it('renders citations and jumps to the event node', async () => {
    const user = userEvent.setup()
    const onJump = vi.fn()
    render(
      <CitationList
        citations={[
          {
            memory_id: 'mem-1',
            event_id: 'evt-fight',
            preview: '去年十一月在西湖吵过',
          },
        ]}
        onJump={onJump}
      />,
    )
    const chip = screen.getByRole('button', { name: '去年十一月在西湖吵过' })
    await user.click(chip)
    expect(onJump).toHaveBeenCalledWith('evt-fight')
  })
})

import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { describe, expect, it } from 'vitest'
import { WorkbenchLayout } from './WorkbenchLayout'

function Harness() {
  const [open, setOpen] = useState(false)
  return (
    <WorkbenchLayout
      narrow
      treeOpen={open}
      onToggleTree={() => setOpen((value) => !value)}
      left={<span>档案</span>}
      center={<span>对话</span>}
      right={<span>生命线</span>}
    />
  )
}

describe('WorkbenchLayout', () => {
  it('keeps an event-tree entry on a narrow screen', async () => {
    const user = userEvent.setup()
    render(<Harness />)
    expect(screen.getByRole('button', { name: '事件树' })).toBeInTheDocument()
    expect(screen.queryByText('生命线')).not.toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: '事件树' }))
    expect(screen.getByText('生命线')).toBeInTheDocument()
  })
})

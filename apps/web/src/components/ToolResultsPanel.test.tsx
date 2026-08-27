import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { ToolResultsPanel } from './ToolResultsPanel'

describe('ToolResultsPanel', () => {
  it('renders ticket and calendar tool results', () => {
    render(
      <ToolResultsPanel
        results={[
          { tool: 'ticket', ticket_id: 't-1', title: '退货纠纷', note: '已登记' },
          {
            tool: 'calendar',
            summary: '今日会议',
            events: [{ title: '复盘', start: '2026-08-27T10:00:00' }],
          },
        ]}
      />,
    )
    expect(screen.getByText('工具结果（2）')).toBeInTheDocument()
    expect(screen.getByText('工单 t-1')).toBeInTheDocument()
    expect(screen.getByText('退货纠纷')).toBeInTheDocument()
    expect(screen.getByText('今日会议')).toBeInTheDocument()
    expect(screen.getByText(/复盘/)).toBeInTheDocument()
  })

  it('returns null when empty', () => {
    const { container } = render(<ToolResultsPanel results={[]} />)
    expect(container).toBeEmptyDOMElement()
  })
})

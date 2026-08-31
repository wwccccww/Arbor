import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { AgentStepTree } from './AgentStepTree'

describe('AgentStepTree', () => {
  it('renders nested step trace nodes', () => {
    render(
      <AgentStepTree
        tree={{
          type: 'run',
          label: '登记工单',
          children: [
            {
              id: 'step-1',
              sequence: 1,
              kind: 'retrieve',
              status: 'completed',
              label: '1. retrieve',
              latency_ms: 12,
              children: [{ type: 'rag', label: '检索命中 2', children: [] }],
            },
          ],
        }}
      />,
    )
    expect(screen.getByText('登记工单')).toBeInTheDocument()
    expect(screen.getByText('1. retrieve')).toBeInTheDocument()
    expect(screen.getByText('12ms')).toBeInTheDocument()
    expect(screen.getByText('检索命中 2')).toBeInTheDocument()
  })
})

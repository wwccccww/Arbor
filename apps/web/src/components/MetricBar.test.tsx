import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { MetricBar } from './MetricBar'

describe('MetricBar', () => {
  it('marks tenant leak zero as passing', () => {
    render(
      <MetricBar
        metrics={{
          identity_consistency: 1,
          recall_at_5: 0.9,
          persona_leak_rate: 0,
          tenant_leak_count: 0,
        }}
        leakZero
      />,
    )
    const leak = screen.getByText(/跨租户泄漏/)
    expect(leak).toHaveTextContent('通过')
    expect(leak).toHaveAttribute('data-fail', 'false')
  })

  it('fails when tenant leak is not zero', () => {
    render(
      <MetricBar
        metrics={{
          identity_consistency: 1,
          recall_at_5: 0.9,
          persona_leak_rate: 0,
          tenant_leak_count: 2,
        }}
        leakZero={false}
      />,
    )
    const leak = screen.getByText(/跨租户泄漏/)
    expect(leak).toHaveTextContent('未通过')
    expect(leak).toHaveAttribute('data-fail', 'true')
  })
})

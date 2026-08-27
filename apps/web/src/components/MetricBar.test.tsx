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

  it('shows generation metrics and judge skip hint', () => {
    render(
      <MetricBar
        mode="generation"
        metrics={{
          citation_subset_rate: 1,
          ragas_faithfulness: null,
          ragas_skipped: true,
          judge_status: 'missing_key',
          generation_p0_pass: true,
          n_leaking_cases: 0,
          refuse_text_leak_count: 0,
        }}
        leakZero
      />,
    )
    expect(screen.getByLabelText('生成评测指标')).toBeInTheDocument()
    expect(screen.getByText(/引用子集/)).toHaveTextContent('1')
    expect(screen.getByText(/未配置 ARBOR_JUDGE_API_KEY/)).toBeInTheDocument()
    expect(screen.getByText(/生成 P0/)).toHaveTextContent('通过')
  })
})

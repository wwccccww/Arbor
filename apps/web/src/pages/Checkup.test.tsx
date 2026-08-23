import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { createClient } from '../api/client'
import { DEMO_OWNER } from '../session'
import { Checkup } from './Checkup'

function evalFetch() {
  return vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input)
    if (url === '/v1/eval/runs' && init?.method === 'POST') {
      const body = JSON.parse(String(init.body)) as { mode: string; strategy: string }
      expect(body.mode).toBe('retrieval')
      return new Response(JSON.stringify({ id: `run-${body.strategy}` }), {
        status: 202,
        headers: { 'Content-Type': 'application/json' },
      })
    }
    if (url.startsWith('/v1/eval/runs/')) {
      const strategy = url.replace('/v1/eval/runs/run-', '')
      return new Response(
        JSON.stringify({
          id: `run-${strategy}`,
          strategy,
          mode: 'retrieval',
          metrics: {
            identity_consistency: 1,
            recall_at_5: 0.9,
            persona_leak_rate: 0,
            tenant_leak_count: 0,
          },
          p0_tenant_leak_zero: true,
          cases: [
            {
              id: 'case-1',
              query: '你住在哪里？',
              skill: 'profile_fact',
              expected_source: 'profile',
              expected_behavior: 'answer',
              expected_memory_count: 1,
              hit_ids: ['m1'],
              leak_ids: [],
              sources: { m1: 'profile' },
              recall: 1,
              leaked: false,
              event_hit: true,
              profile_miss: false,
              passed: true,
            },
            {
              id: 'case-2',
              query: '你们在哪家店吵起来？',
              skill: 'episode_detail',
              expected_source: 'event_tree',
              expected_behavior: 'cite',
              expected_memory_count: 1,
              expected_event_id: 'evt-1',
              hit_ids: ['m2', 'm3'],
              leak_ids: ['mX'],
              sources: { m2: 'event_tree', mX: 'vector' },
              recall: 0.5,
              leaked: true,
              event_hit: false,
              profile_miss: false,
              passed: false,
            },
          ],
        }),
        { status: 200, headers: { 'Content-Type': 'application/json' } },
      )
    }
    return new Response(JSON.stringify({ error: { code: 'NOT_FOUND', message: 'not found' } }), { status: 404 })
  }) as unknown as typeof fetch
}

describe('Checkup', () => {
  it('runs retrieval eval and shows tenant leak as passing', async () => {
    const user = userEvent.setup()
    const fetchImpl = evalFetch()
    render(<Checkup client={createClient(DEMO_OWNER, fetchImpl)} onBack={vi.fn()} />)
    await user.click(screen.getByRole('button', { name: '跑 suite-v1 检索' }))
    expect(await screen.findByLabelText('体检指标')).toBeInTheDocument()
    expect(screen.getByText(/跨租户泄漏/)).toHaveTextContent('通过')
    const posted = (fetchImpl as unknown as ReturnType<typeof vi.fn>).mock.calls.find(
      (call) => String(call[0]) === '/v1/eval/runs',
    )
    expect(JSON.parse(String((posted?.[1] as RequestInit).body))).toEqual({
      strategy: 'layered_tree',
      suite_version: 'v1',
      mode: 'retrieval',
    })
  })

  it('shows forbidden instead of metrics for members', async () => {
    const user = userEvent.setup()
    const fetchImpl = vi.fn(async () =>
      new Response(JSON.stringify({ error: { code: 'FORBIDDEN_WORKSPACE', message: 'admin required' } }), {
        status: 403,
        headers: { 'Content-Type': 'application/json' },
      }),
    ) as unknown as typeof fetch
    render(<Checkup client={createClient(DEMO_OWNER, fetchImpl)} onBack={vi.fn()} />)
    await user.click(screen.getByRole('button', { name: '跑 suite-v1 检索' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('没有评测权限')
    expect(screen.queryByLabelText('体检指标')).not.toBeInTheDocument()
  })

  it('renders per-case pass/fail list after a run', async () => {
    const user = userEvent.setup()
    const fetchImpl = evalFetch()
    render(<Checkup client={createClient(DEMO_OWNER, fetchImpl)} onBack={vi.fn()} />)
    await user.click(screen.getByRole('button', { name: '跑 suite-v1 检索' }))
    expect(await screen.findByLabelText('逐题红绿清单')).toBeInTheDocument()
    expect(screen.getByText(/你住在哪里/)).toBeInTheDocument()
    expect(screen.getByText(/你们在哪家店吵起来/)).toBeInTheDocument()
    expect(screen.getAllByText('通过').length).toBeGreaterThan(0)
    expect(screen.getAllByText('未通过').length).toBeGreaterThan(0)
  })
})

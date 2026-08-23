import { useState } from 'react'
import type { ArborClient } from '../api/client'
import type { ApiError, EvalCase, EvalRun } from '../api/types'
import { MetricBar } from '../components/MetricBar'

const STRATEGIES = ['summary_only', 'vector_only', 'layered', 'layered_tree'] as const

const STRATEGY_LABELS: Record<string, string> = {
  summary_only: '仅摘要',
  vector_only: '仅向量',
  layered: '分层',
  layered_tree: '分层 + 事件树',
}

const SOURCE_LABELS: Record<string, string> = {
  profile: '档案',
  vector: '向量',
  event_tree: '事件树',
}

const SKILL_LABELS: Record<string, string> = {
  profile_fact: '档案事实',
  episode_detail: '事件细节',
  temporal: '时间',
  causal: '因果',
  persona_isolation: '人设隔离',
  tenant_isolation: '租户隔离',
  conflict: '冲突',
  irrelevant: '无关',
  multimodal: '多模态',
}

type Filter = 'all' | 'passed' | 'failed'

function CaseRow({ row, index }: { row: EvalCase; index: number }) {
  const sourceLabel = SOURCE_LABELS[row.expected_source ?? ''] ?? row.expected_source ?? '无'
  const hitCount = row.hit_ids.length
  const missReasons: string[] = []
  if (row.leaked) missReasons.push('泄漏')
  if ((row.expected_memory_count ?? 0) > 0 && row.recall < 1) missReasons.push('未召回')
  if (row.expected_source === 'event_tree' && row.expected_event_id && !row.event_hit) missReasons.push('事件未命中')

  return (
    <li className="case-row" data-pass={row.passed ? 'true' : 'false'}>
      <span className={`badge ${row.passed ? 'badge--ok' : 'badge--fail'}`}>
        {row.passed ? '通过' : '未通过'}
      </span>
      <div className="case-row__body">
        <p className="case-row__query">
          {index + 1}. {row.query}
        </p>
        <p className="case-row__meta">
          <span className="badge">{SKILL_LABELS[row.skill ?? ''] ?? row.skill ?? '—'}</span>
          <span className="badge">来源 {sourceLabel}</span>
          <span className="badge">命中 {hitCount}</span>
          <span className="badge">召回 {row.recall.toFixed(2)}</span>
        </p>
        {row.expected_behavior ? <p className="case-row__behavior">期望：{row.expected_behavior}</p> : null}
        {missReasons.length ? (
          <p className="case-row__reason">
            未达标：{missReasons.join('、')}
          </p>
        ) : null}
      </div>
    </li>
  )
}

export function Checkup({
  client,
  onBack,
}: {
  client: ArborClient
  onBack: () => void
}) {
  const [run, setRun] = useState<EvalRun | null>(null)
  const [rows, setRows] = useState<EvalRun[]>([])
  const [busy, setBusy] = useState(false)
  const [forbidden, setForbidden] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [filter, setFilter] = useState<Filter>('all')

  async function fetchRun(strategy: string): Promise<EvalRun> {
    const started = await client.startEvalRun(strategy)
    return await client.getEvalRun(started.id)
  }

  function asForbidden(err: unknown): boolean {
    const api = err as ApiError
    return api.status === 403 || api.code === 'FORBIDDEN_WORKSPACE'
  }

  async function runDefault() {
    setBusy(true)
    setError(null)
    try {
      setRun(await fetchRun('layered_tree'))
    } catch (err) {
      if (asForbidden(err)) setForbidden(true)
      else setError((err as Error).message)
    } finally {
      setBusy(false)
    }
  }

  async function runComparison() {
    setBusy(true)
    setError(null)
    try {
      const next: EvalRun[] = []
      for (const strategy of STRATEGIES) {
        next.push(await fetchRun(strategy))
      }
      setRows(next)
      setRun(next.find((item) => item.strategy === 'layered_tree') ?? next[0] ?? null)
    } catch (err) {
      if (asForbidden(err)) setForbidden(true)
      else setError((err as Error).message)
    } finally {
      setBusy(false)
    }
  }

  const cases = (run?.cases ?? []).filter((row) => {
    if (filter === 'all') return true
    return filter === 'passed' ? row.passed : !row.passed
  })

  return (
    <section className="checkup">
      <header className="topbar">
        <div className="topbar__brand">
          Arbor
          <small>记忆体检</small>
        </div>
        <div className="topbar__spacer" />
        <nav className="topbar__nav">
          <button type="button" className="btn--ghost" onClick={onBack}>
            返回工作空间
          </button>
        </nav>
      </header>

      <main>
        <div className="home-bar">
          <h1>记忆体检</h1>
          <span className="badge">suite-v1 检索</span>
        </div>
        <p className="form-hint">只跑 suite-v1 检索，不调用生成模型。逐题红绿由检索结果逐题判定。</p>

        {forbidden ? <p role="alert">没有评测权限</p> : null}
        {error ? <p role="alert">{error}</p> : null}

        <div className="checkup-actions">
          <button type="button" className="btn--primary" disabled={busy || forbidden} onClick={() => void runDefault()}>
            跑 suite-v1 检索
          </button>
          <button type="button" disabled={busy || forbidden} onClick={() => void runComparison()}>
            四策略对比
          </button>
        </div>

        {run ? <MetricBar metrics={run.metrics} leakZero={run.p0_tenant_leak_zero} /> : null}

        {rows.length ? (
          <div className="table-wrap">
            <table>
              <caption>四策略对比</caption>
              <thead>
                <tr>
                  <th>策略</th>
                  <th>身份一致</th>
                  <th>Recall@5</th>
                  <th>人设泄漏</th>
                  <th>跨租户泄漏</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((item) => (
                  <tr key={item.strategy}>
                    <td>{STRATEGY_LABELS[item.strategy] ?? item.strategy}</td>
                    <td>{item.metrics.identity_consistency}</td>
                    <td>{item.metrics.recall_at_5}</td>
                    <td>{item.metrics.persona_leak_rate}</td>
                    <td>{item.metrics.tenant_leak_count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}

        {run?.cases?.length ? (
          <section className="case-section">
            <div className="case-section__head">
              <h2>逐题结果</h2>
              <div className="view-toggle" role="group" aria-label="逐题筛选">
                <button type="button" aria-pressed={filter === 'all'} onClick={() => setFilter('all')}>
                  全部
                </button>
                <button type="button" aria-pressed={filter === 'passed'} onClick={() => setFilter('passed')}>
                  通过
                </button>
                <button type="button" aria-pressed={filter === 'failed'} onClick={() => setFilter('failed')}>
                  未通过
                </button>
              </div>
            </div>
            <ul className="case-list" aria-label="逐题红绿清单">
              {cases.map((row, index) => (
                <CaseRow key={row.id} row={row} index={index} />
              ))}
            </ul>
          </section>
        ) : null}
      </main>
    </section>
  )
}

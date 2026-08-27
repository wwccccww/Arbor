import { useEffect, useState } from 'react'
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
        {row.hit_ids.length ? (
          <p className="case-row__meta">命中 ID：{row.hit_ids.join(', ')}</p>
        ) : null}
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
  personas = [],
  onBack,
}: {
  client: ArborClient
  personas?: { id: string; display_name: string }[]
  onBack: () => void
}) {
  const [run, setRun] = useState<EvalRun | null>(null)
  const [rows, setRows] = useState<EvalRun[]>([])
  const [busy, setBusy] = useState(false)
  const [busyLabel, setBusyLabel] = useState<string | null>(null)
  const [forbidden, setForbidden] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [filter, setFilter] = useState<Filter>('all')
  const [personaId, setPersonaId] = useState(personas[0]?.id ?? '')
  const [casePage, setCasePage] = useState(0)
  const CASE_PAGE_SIZE = 50

  useEffect(() => {
    if (!personaId && personas.length) setPersonaId(personas[0].id)
  }, [personas, personaId])

  async function fetchRun(
    strategy: string,
    opts?: { suite_version?: string; mode?: string },
  ): Promise<EvalRun> {
    const started = await client.startEvalRun(strategy, opts)
    return await client.getEvalRun(started.id)
  }

  function asForbidden(err: unknown): boolean {
    const api = err as ApiError
    return api.status === 403 || api.code === 'FORBIDDEN_WORKSPACE'
  }

  async function runPersonaSmoke() {
    if (!personaId) return
    setBusy(true)
    setBusyLabel('正在为人设生成轻量体检题…')
    setError(null)
    setForbidden(false)
    try {
      const started = await client.startPersonaEvalRun(personaId, 'layered_tree')
      setRun(await client.getEvalRun(started.id))
      setRows([])
    } catch (err) {
      if (asForbidden(err)) setForbidden(true)
      else setError((err as Error).message)
    } finally {
      setBusy(false)
      setBusyLabel(null)
    }
  }

  async function runDefault() {
    setBusy(true)
    setBusyLabel('正在跑 layered_tree…')
    setError(null)
    try {
      setRun(await fetchRun('layered_tree'))
    } catch (err) {
      if (asForbidden(err)) setForbidden(true)
      else setError((err as Error).message)
    } finally {
      setBusy(false)
      setBusyLabel(null)
    }
  }

  async function runComparison() {
    setBusy(true)
    setError(null)
    try {
      const next: EvalRun[] = []
      for (const strategy of STRATEGIES) {
        setBusyLabel(`正在跑 ${STRATEGY_LABELS[strategy] ?? strategy}…`)
        next.push(await fetchRun(strategy))
      }
      setRows(next)
      setRun(next.find((item) => item.strategy === 'layered_tree') ?? next[0] ?? null)
    } catch (err) {
      if (asForbidden(err)) setForbidden(true)
      else setError((err as Error).message)
    } finally {
      setBusy(false)
      setBusyLabel(null)
    }
  }

  async function runRagas() {
    setBusy(true)
    setBusyLabel('正在跑 ragas-v1（477 题）…')
    setError(null)
    setCasePage(0)
    try {
      setRun(await fetchRun('layered_tree', { suite_version: 'ragas-v1' }))
    } catch (err) {
      if (asForbidden(err)) setForbidden(true)
      else setError((err as Error).message)
    } finally {
      setBusy(false)
      setBusyLabel(null)
    }
  }

  async function seedFrozenWorld() {
    setBusy(true)
    setBusyLabel('正在装载 suite-v1 冻结世界…')
    setError(null)
    try {
      await client.seedEvalWorld()
      setError(null)
    } catch (err) {
      if (asForbidden(err)) setForbidden(true)
      else setError((err as Error).message)
    } finally {
      setBusy(false)
      setBusyLabel(null)
    }
  }

  async function runGeneration() {
    setBusy(true)
    setBusyLabel('正在跑生成评测…')
    setError(null)
    try {
      setRun(await fetchRun('layered_tree', { mode: 'generation' }))
    } catch (err) {
      if (asForbidden(err)) setForbidden(true)
      else setError((err as Error).message)
    } finally {
      setBusy(false)
      setBusyLabel(null)
    }
  }

  const cases = (run?.cases ?? []).filter((row) => {
    if (filter === 'all') return true
    return filter === 'passed' ? row.passed : !row.passed
  })
  const casePageCount = Math.max(1, Math.ceil(cases.length / CASE_PAGE_SIZE))
  const safeCasePage = Math.min(casePage, casePageCount - 1)
  const visibleCases = cases.slice(
    safeCasePage * CASE_PAGE_SIZE,
    safeCasePage * CASE_PAGE_SIZE + CASE_PAGE_SIZE,
  )

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
          <span className="badge">
            {run?.suite_version === 'ragas-v1' ? 'ragas-v1 · 477 题' : 'suite 检索 / 生成'}
          </span>
        </div>
        <p className="form-hint">检索模式不调用生成模型；生成模式需配置 DEEPSEEK_API_KEY。</p>

        {forbidden ? <p role="alert">没有评测权限</p> : null}
        {error ? <p role="alert">{error}</p> : null}
        {busyLabel ? <p className="checkup-progress">{busyLabel}</p> : null}

        <div className="checkup-actions">
          {personas.length ? (
            <label>
              当前人设
              <select value={personaId} onChange={(e) => setPersonaId(e.target.value)}>
                {personas.map((p) => (
                  <option key={p.id} value={p.id}>{p.display_name}</option>
                ))}
              </select>
            </label>
          ) : null}
          <button
            type="button"
            disabled={busy || forbidden || !personaId}
            onClick={() => void runPersonaSmoke()}
          >
            人设轻量体检
          </button>
          <button type="button" className="btn--primary" disabled={busy || forbidden} onClick={() => void runDefault()}>
            跑 suite-v1 检索（13 题）
          </button>
          <button
            type="button"
            disabled={busy || forbidden}
            onClick={() => void seedFrozenWorld()}
          >
            装载 suite-v1 冻结世界
          </button>
          <button
            type="button"
            disabled={busy || forbidden}
            onClick={() => void runRagas()}
          >
            跑 ragas-v1 检索（477 题）
          </button>
          <button
            type="button"
            disabled={busy || forbidden}
            onClick={() => void runGeneration()}
          >
            suite-v1 生成评测
          </button>
          <button type="button" disabled={busy || forbidden} onClick={() => void runComparison()}>
            四策略对比
          </button>
        </div>

        {run ? <MetricBar metrics={run.metrics} leakZero={run.p0_tenant_leak_zero} mode={run.mode} /> : null}

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
              <h2>
                逐题结果
                {run.cases?.length ? `（${cases.length} / ${run.cases.length}）` : ''}
              </h2>
              <div className="view-toggle" role="group" aria-label="逐题筛选">
                <button
                  type="button"
                  aria-pressed={filter === 'all'}
                  onClick={() => {
                    setFilter('all')
                    setCasePage(0)
                  }}
                >
                  全部
                </button>
                <button
                  type="button"
                  aria-pressed={filter === 'passed'}
                  onClick={() => {
                    setFilter('passed')
                    setCasePage(0)
                  }}
                >
                  通过
                </button>
                <button
                  type="button"
                  aria-pressed={filter === 'failed'}
                  onClick={() => {
                    setFilter('failed')
                    setCasePage(0)
                  }}
                >
                  未通过
                </button>
              </div>
            </div>
            {cases.length > CASE_PAGE_SIZE ? (
              <div className="case-pagination">
                <button
                  type="button"
                  disabled={safeCasePage <= 0}
                  onClick={() => setCasePage((page) => Math.max(0, page - 1))}
                >
                  上一页
                </button>
                <span>
                  第 {safeCasePage + 1} / {casePageCount} 页
                </span>
                <button
                  type="button"
                  disabled={safeCasePage >= casePageCount - 1}
                  onClick={() => setCasePage((page) => Math.min(casePageCount - 1, page + 1))}
                >
                  下一页
                </button>
              </div>
            ) : null}
            <ul className="case-list" aria-label="逐题红绿清单">
              {visibleCases.map((row, index) => (
                <CaseRow
                  key={row.id}
                  row={row}
                  index={safeCasePage * CASE_PAGE_SIZE + index}
                />
              ))}
            </ul>
          </section>
        ) : null}
      </main>
    </section>
  )
}

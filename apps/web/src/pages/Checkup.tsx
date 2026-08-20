import { useState } from 'react'
import type { ArborClient } from '../api/client'
import type { ApiError, EvalRun } from '../api/types'
import { MetricBar } from '../components/MetricBar'

const STRATEGIES = ['summary_only', 'vector_only', 'layered', 'layered_tree'] as const

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

  return (
    <section className="checkup">
      <header className="workbench-bar">
        <button type="button" onClick={onBack}>
          返回
        </button>
        <h1>记忆体检</h1>
      </header>
      <p>只跑 suite-v1 检索，不调用生成模型。</p>
      {forbidden ? <p role="alert">没有评测权限</p> : null}
      {error ? <p role="alert">{error}</p> : null}
      <div className="checkup-actions">
        <button type="button" disabled={busy || forbidden} onClick={() => void runDefault()}>
          跑 suite-v1 检索
        </button>
        <button type="button" disabled={busy || forbidden} onClick={() => void runComparison()}>
          四策略对比
        </button>
      </div>
      {run ? <MetricBar metrics={run.metrics} leakZero={run.p0_tenant_leak_zero} /> : null}
      {rows.length ? (
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
                <td>{item.strategy}</td>
                <td>{item.metrics.identity_consistency}</td>
                <td>{item.metrics.recall_at_5}</td>
                <td>{item.metrics.persona_leak_rate}</td>
                <td>{item.metrics.tenant_leak_count}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : null}
    </section>
  )
}

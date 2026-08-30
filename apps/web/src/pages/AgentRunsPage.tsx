import { useCallback, useEffect, useState } from 'react'
import type { ArborClient } from '../api/client'
import type { AgentApproval, AgentRunDetail, AgentRunSummary } from '../api/types'

type Props = {
  client: ArborClient
  personaId: string
  workspaceAdmin: boolean
  onBack: () => void
}

export function AgentRunsPage({ client, personaId, workspaceAdmin, onBack }: Props) {
  const [runs, setRuns] = useState<AgentRunSummary[]>([])
  const [approvals, setApprovals] = useState<AgentApproval[]>([])
  const [selectedId, setSelectedId] = useState<string | undefined>()
  const [detail, setDetail] = useState<AgentRunDetail | null>(null)
  const [goal, setGoal] = useState('登记工单：会议室设备故障')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | undefined>()

  const refresh = useCallback(async () => {
    const listed = await client.listAgentRuns(personaId)
    setRuns(listed.items)
    if (workspaceAdmin) {
      const pending = await client.listAgentApprovals()
      setApprovals(pending.items)
    }
  }, [client, personaId, workspaceAdmin])

  useEffect(() => {
    void refresh().catch((err) => setError((err as Error).message))
  }, [refresh])

  async function loadDetail(runId: string) {
    setSelectedId(runId)
    setBusy(true)
    setError(undefined)
    try {
      const payload = await client.getAgentRun(runId)
      setDetail(payload)
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setBusy(false)
    }
  }

  async function createRun() {
    setBusy(true)
    setError(undefined)
    try {
      const created = await client.createAgentRun(personaId, { goal })
      await refresh()
      await loadDetail(created.id)
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setBusy(false)
    }
  }

  async function approve(approvalId: string) {
    setBusy(true)
    try {
      await client.approveAgentAction(approvalId)
      await refresh()
      if (selectedId) await loadDetail(selectedId)
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setBusy(false)
    }
  }

  async function reject(approvalId: string) {
    setBusy(true)
    try {
      await client.rejectAgentAction(approvalId)
      await refresh()
      if (selectedId) await loadDetail(selectedId)
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <main className="page agent-page">
      <header className="page-header">
        <button type="button" className="link-button" onClick={onBack}>
          ← 返回
        </button>
        <h1>数字员工 Agent</h1>
        <p className="muted">任务 Run 时间线、审批队列与步骤账本。</p>
      </header>

      <section className="card">
        <label htmlFor="agent-goal">任务目标</label>
        <div className="inline-form">
          <input id="agent-goal" value={goal} onChange={(e) => setGoal(e.target.value)} />
          <button type="button" disabled={busy} onClick={() => void createRun()}>
            创建 Run
          </button>
        </div>
        {error ? <p className="error">{error}</p> : null}
      </section>

      {workspaceAdmin && approvals.length ? (
        <section className="card">
          <h2>待审批</h2>
          <ul className="list-plain">
            {approvals.map((item) => (
              <li key={item.id} className="inline-form">
                <span>{item.tool_name} · run {item.run_id}</span>
                <button type="button" disabled={busy} onClick={() => void approve(item.id)}>
                  批准
                </button>
                <button type="button" disabled={busy} onClick={() => void reject(item.id)}>
                  拒绝
                </button>
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      <section className="card">
        <h2>最近 Run</h2>
        <ul className="list-plain">
          {runs.map((run) => (
            <li key={run.id}>
              <button type="button" className="link-button" onClick={() => void loadDetail(run.id)}>
                {run.goal.slice(0, 48)} — {run.status} ({run.current_step}/{run.max_steps})
              </button>
            </li>
          ))}
        </ul>
      </section>

      {detail ? (
        <section className="card">
          <h2>Run {detail.run.id}</h2>
          <p className="muted">
            状态：{detail.run.status} · 版本 {detail.run.version}
            {detail.run.employee_definition_version
              ? ` · 岗位 v${detail.run.employee_definition_version}`
              : ''}
          </p>
          {detail.run.metadata?.context_manifest ? (
            <details className="agent-trace">
              <summary>上下文 manifest</summary>
              <pre className="code-block">
                {JSON.stringify(detail.run.metadata.context_manifest, null, 2)}
              </pre>
            </details>
          ) : null}
          {detail.lineage?.length ? (
            <details className="agent-trace">
              <summary>多模态证据链（{detail.lineage.length}）</summary>
              <pre className="code-block">{JSON.stringify(detail.lineage, null, 2)}</pre>
            </details>
          ) : null}
          <ol className="agent-steps">
            {detail.steps.map((step) => (
              <li key={step.id}>
                <strong>{step.sequence}. {step.kind}</strong> — {step.status}
                <pre className="code-block">{JSON.stringify(step.output, null, 2)}</pre>
              </li>
            ))}
          </ol>
        </section>
      ) : null}
    </main>
  )
}

import { useCallback, useEffect, useState } from 'react'
import type { ArborClient } from '../api/client'
import type { AgentApproval, AgentRunDetail, AgentRunSummary, EmployeeDefinition } from '../api/types'
import { AgentStepTree } from '../components/AgentStepTree'

const GRAFANA_BASE = (import.meta.env.VITE_GRAFANA_URL as string | undefined)?.replace(/\/$/, '') || 'http://localhost:3000'

function grafanaExploreLink(requestId: string, datasource: 'loki' | 'tempo') {
  if (datasource === 'loki') {
    const left = encodeURIComponent(
      JSON.stringify({
        datasource: 'loki',
        queries: [{ expr: `{service=~"arbor-.*"} |= "${requestId}"`, refId: 'A' }],
      }),
    )
    return `${GRAFANA_BASE}/explore?left=${left}`
  }
  const left = encodeURIComponent(
    JSON.stringify({
      datasource: 'tempo',
      queries: [{ query: requestId, queryType: 'traceql', refId: 'A' }],
    }),
  )
  return `${GRAFANA_BASE}/explore?left=${left}`
}

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
  const [employeeDef, setEmployeeDef] = useState<EmployeeDefinition | null>(null)
  const [employeeVersions, setEmployeeVersions] = useState<EmployeeDefinition[]>([])
  const [employeeEval, setEmployeeEval] = useState<Record<string, unknown> | null>(null)

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
    void client
      .getEmployeeDefinition(personaId)
      .then(setEmployeeDef)
      .catch(() => setEmployeeDef(null))
    void client
      .listEmployeeDefinitionVersions(personaId)
      .then((payload) => setEmployeeVersions(payload.items || []))
      .catch(() => setEmployeeVersions([]))
  }, [refresh, client, personaId])

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

  async function runEmployeeEval() {
    setBusy(true)
    setError(undefined)
    try {
      const report = await client.startEmployeeEval(personaId)
      setEmployeeEval(report)
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setBusy(false)
    }
  }

  const traceRequestId =
    detail?.run.request_id ||
    (detail?.run.metadata?.request_id as string | undefined) ||
    detail?.steps.find((s) => s.trace_id)?.trace_id

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
        {employeeDef ? (
          <p className="muted">
            岗位 {employeeDef.role} v{employeeDef.version} · 评测套件 {employeeDef.evaluation_suite} ·{' '}
            {employeeDef.release_status}
            {employeeDef.eval_gate_passed != null ? ` · 门禁 ${employeeDef.eval_gate_passed ? '通过' : '未通过'}` : ''}
          </p>
        ) : null}
        {employeeVersions.length > 0 ? (
          <p className="muted">
            版本历史：
            {employeeVersions.map((v) => (
              <span key={v.version} style={{ marginRight: '0.75rem' }}>
                v{v.version} ({v.release_status}
                {v.eval_gate_passed != null ? ` · gate ${v.eval_gate_passed ? '✓' : '✗'}` : ''})
              </span>
            ))}
          </p>
        ) : null}
      </header>

      {workspaceAdmin && employeeDef ? (
        <section className="card">
          <h2>岗位评测门禁</h2>
          <p className="muted">发布前跑 {employeeDef.evaluation_suite}，对比基线 task_success_rate 与 P0 安全指标。</p>
          <div className="inline-form">
            <button type="button" disabled={busy} onClick={() => void runEmployeeEval()}>
              跑岗位评测
            </button>
            {employeeEval ? (
              <span className={employeeEval.gate_passed ? 'ok' : 'error'}>
                {employeeEval.gate_passed ? '门禁通过' : '门禁未通过'} · 成功率{' '}
                {String(employeeEval.task_success_rate)} / 基线{' '}
                {String(employeeEval.baseline_task_success_rate)}
              </span>
            ) : null}
          </div>
        </section>
      ) : null}

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
            {detail.run.consumed_tokens != null
              ? ` · tokens ${detail.run.consumed_tokens}/${detail.run.token_budget ?? '—'}`
              : ''}
            {detail.run.consumed_cost_micros != null
              ? ` · 成本 ${detail.run.consumed_cost_micros}µ`
              : ''}
          </p>
          {traceRequestId ? (
            <p className="inline-form">
              <a
                className="link-button"
                href={grafanaExploreLink(traceRequestId, 'tempo')}
                target="_blank"
                rel="noreferrer"
              >
                Tempo 追踪
              </a>
              <a
                className="link-button"
                href={grafanaExploreLink(traceRequestId, 'loki')}
                target="_blank"
                rel="noreferrer"
              >
                Loki 日志
              </a>
            </p>
          ) : null}
          {detail.step_tree ? (
            <details className="agent-trace" open>
              <summary>步骤树（Run → Step → RAG/Tool/Approval）</summary>
              <AgentStepTree tree={detail.step_tree} />
            </details>
          ) : null}
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

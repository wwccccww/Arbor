import type { EvalMetrics } from '../api/types'

export function tenantLeakFailed(metrics: EvalMetrics, leakZero?: boolean): boolean {
  if (leakZero === false) return true
  return (metrics.tenant_leak_count ?? 0) !== 0
}

function fmt(value: number | undefined | null): string {
  if (value == null) return '—'
  return Number.isInteger(value) ? String(value) : value.toFixed(2)
}

const JUDGE_HINTS: Record<string, string> = {
  missing_key: '未配置 ARBOR_JUDGE_API_KEY',
  same_as_generator: '评委密钥与生成密钥相同（已跳过）',
  configured: '评委已配置',
}

export function MetricBar({
  metrics,
  leakZero,
  mode,
}: {
  metrics: EvalMetrics
  leakZero?: boolean
  mode?: string
}) {
  const leakFail = tenantLeakFailed(metrics, leakZero)
  const isGeneration = mode === 'generation' || metrics.citation_subset_rate != null

  if (isGeneration) {
    const p0Pass = metrics.generation_p0_pass ?? leakZero
    const p0Fail = p0Pass === false
    const judgeHint = JUDGE_HINTS[metrics.judge_status ?? ''] ?? null
    return (
      <ul aria-label="生成评测指标" className="metric-bar">
        <li data-fail={p0Fail ? 'true' : 'false'} data-pass={p0Fail ? 'false' : 'true'}>
          生成 P0 <strong>{p0Fail ? '未通过' : '通过'}</strong>
          <span className={`badge ${p0Fail ? 'badge--fail' : 'badge--ok'}`}>
            {p0Fail ? '未通过' : '通过'}
          </span>
        </li>
        <li>
          引用子集 <strong>{fmt(metrics.citation_subset_rate)}</strong>
        </li>
        <li>
          RAGAS 忠实度 <strong>{fmt(metrics.ragas_faithfulness)}</strong>
          {metrics.ragas_n ? <span className="badge">n={metrics.ragas_n}</span> : null}
          {metrics.ragas_skipped ? (
            <span className="badge" title={judgeHint ?? undefined}>已跳过</span>
          ) : null}
          {judgeHint && metrics.ragas_skipped ? (
            <span className="form-hint">{judgeHint}</span>
          ) : null}
        </li>
        <li>
          泄漏题数 <strong>{fmt(metrics.n_leaking_cases)}</strong>
        </li>
        <li>
          拒答泄漏 <strong>{fmt(metrics.refuse_text_leak_count)}</strong>
        </li>
      </ul>
    )
  }

  return (
    <ul aria-label="体检指标" className="metric-bar">
      <li>
        身份一致 <strong>{fmt(metrics.identity_consistency)}</strong>
      </li>
      <li>
        Recall@5 <strong>{fmt(metrics.recall_at_5)}</strong>
      </li>
      <li>
        人设泄漏 <strong>{fmt(metrics.persona_leak_rate)}</strong>
      </li>
      <li data-fail={leakFail ? 'true' : 'false'} data-pass={leakFail ? 'false' : 'true'}>
        跨租户泄漏 <strong>{fmt(metrics.tenant_leak_count)}</strong>
        <span className={`badge ${leakFail ? 'badge--fail' : 'badge--ok'}`}>
          {leakFail ? '未通过' : '通过'}
        </span>
      </li>
    </ul>
  )
}

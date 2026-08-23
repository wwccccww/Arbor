import type { EvalMetrics } from '../api/types'

export function tenantLeakFailed(metrics: EvalMetrics, leakZero?: boolean): boolean {
  if (leakZero === false) return true
  return (metrics.tenant_leak_count ?? 0) !== 0
}

function fmt(value: number | undefined): string {
  if (value == null) return '—'
  return Number.isInteger(value) ? String(value) : value.toFixed(2)
}

export function MetricBar({
  metrics,
  leakZero,
}: {
  metrics: EvalMetrics
  leakZero?: boolean
}) {
  const leakFail = tenantLeakFailed(metrics, leakZero)
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

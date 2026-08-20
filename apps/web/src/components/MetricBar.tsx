import type { EvalMetrics } from '../api/types'

export function tenantLeakFailed(metrics: EvalMetrics, leakZero?: boolean): boolean {
  if (leakZero === false) return true
  return (metrics.tenant_leak_count ?? 0) !== 0
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
      <li>身份一致 {metrics.identity_consistency ?? '—'}</li>
      <li>Recall@5 {metrics.recall_at_5 ?? '—'}</li>
      <li>人设泄漏 {metrics.persona_leak_rate ?? '—'}</li>
      <li data-fail={leakFail ? 'true' : 'false'}>
        跨租户泄漏 {metrics.tenant_leak_count ?? '—'}
        {leakFail ? ' 未通过' : ' 通过'}
      </li>
    </ul>
  )
}

import type { DecisionTrace, RetrievalMeta } from '../api/types'

const SOURCE_LABELS: Record<string, string> = {
  profile: '档案',
  vector: '向量',
  event_tree: '事件树',
}

const INTENT_LABELS: Record<string, string> = {
  profile: '档案',
  episode: '事件',
  general: '通用',
}

export function DecisionTracePanel({
  meta,
  trace,
  requestId,
}: {
  meta?: RetrievalMeta
  trace?: DecisionTrace
  requestId?: string
}) {
  const retrieval = trace?.retrieval
  const context = trace?.context
  const reasoner = trace?.reasoner
  const generation = trace?.generation
  const hasTrace = Boolean(trace && (retrieval || context || reasoner || generation))
  const hasMeta = Boolean(meta && meta.hit_ids?.length)

  if (!hasTrace && !hasMeta) return null

  const counts = retrieval?.per_source_counts ?? meta?.per_source_counts ?? {}
  const countParts = Object.entries(counts)
    .filter(([, value]) => value > 0)
    .map(([key, value]) => `${SOURCE_LABELS[key] ?? key} ${value}`)
  const subQueries = retrieval?.sub_queries ?? meta?.sub_queries ?? []

  return (
    <details className="retrieval-meta">
      <summary>
        处理过程
        {retrieval?.strategy || meta?.strategy ? ` · ${retrieval?.strategy ?? meta?.strategy}` : ''}
        {requestId ? ` · ${requestId}` : ''}
      </summary>
      {countParts.length ? <p className="retrieval-meta__counts">来源：{countParts.join('、')}</p> : null}
      {context?.truncation_notes?.length ? (
        <p className="retrieval-meta__counts">裁剪：{context.truncation_notes.join('、')}</p>
      ) : null}
      {context?.injected_memory_ids?.length ? (
        <p className="retrieval-meta__counts">注入 {context.injected_memory_ids.length} 条记忆</p>
      ) : null}
      {reasoner?.called ? (
        <p className="retrieval-meta__counts">
          Reasoner：{reasoner.operation ?? 'extract'}
          {reasoner.result_kind ? ` · ${reasoner.result_kind}` : ''}
          {reasoner.conflicts_with ? ` · 冲突 ${reasoner.conflicts_with}` : ''}
        </p>
      ) : null}
      {generation?.model ? (
        <p className="retrieval-meta__counts">
          模型 {generation.model}
          {generation.latency_ms != null ? ` · ${generation.latency_ms}ms` : ''}
        </p>
      ) : null}
      {subQueries.length > 1 ? (
        <ul className="retrieval-meta__subs" aria-label="子 query">
          {subQueries.map((item, index) => (
            <li key={`${item.intent ?? 'q'}-${index}`}>
              <span className="badge">{INTENT_LABELS[item.intent ?? ''] ?? item.intent ?? '—'}</span>
              {item.query_hash ? `hash ${item.query_hash.slice(0, 18)}…` : '—'}
            </li>
          ))}
        </ul>
      ) : null}
    </details>
  )
}

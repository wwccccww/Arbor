import type { RetrievalMeta } from '../api/types'

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

export function RetrievalMetaPanel({ meta }: { meta?: RetrievalMeta }) {
  if (!meta || !meta.hit_ids?.length) return null
  const counts = meta.per_source_counts ?? {}
  const countParts = Object.entries(counts)
    .filter(([, value]) => value > 0)
    .map(([key, value]) => `${SOURCE_LABELS[key] ?? key} ${value}`)
  const subQueries = meta.sub_queries ?? []

  return (
    <details className="retrieval-meta">
      <summary>
        检索 {meta.hit_ids.length} 条
        {meta.strategy ? ` · ${meta.strategy}` : ''}
      </summary>
      {countParts.length ? <p className="retrieval-meta__counts">来源：{countParts.join('、')}</p> : null}
      {subQueries.length > 1 ? (
        <ul className="retrieval-meta__subs" aria-label="子 query">
          {subQueries.map((item) => (
            <li key={item.query}>
              <span className="badge">{INTENT_LABELS[item.intent ?? ''] ?? item.intent ?? '—'}</span>
              {item.query}
            </li>
          ))}
        </ul>
      ) : null}
    </details>
  )
}

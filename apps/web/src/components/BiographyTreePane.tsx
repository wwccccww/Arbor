import { useMemo } from 'react'
import type { EventNode } from '../api/types'
import { filterEventNodes, isKeyEvent, type EventEdge } from '../lib/eventTreeFilters'

const TYPE_LABELS: Record<string, string> = {
  milestone: '里程碑',
  promise: '承诺',
  conflict: '冲突',
  daily: '日常',
  work: '工作',
}

function typeBadgeClass(type?: string) {
  if (type === 'conflict') return 'badge badge--fail'
  if (type === 'promise') return 'badge badge--promise'
  if (type === 'milestone') return 'badge badge--milestone'
  return 'badge badge--companion'
}

export function BiographyTreePane({
  nodes,
  edges = [],
  keyOnly = true,
  personFilter = '',
  highlightedId,
  onSelect,
}: {
  nodes: EventNode[]
  edges?: EventEdge[]
  keyOnly?: boolean
  personFilter?: string
  highlightedId?: string
  onSelect?: (eventId: string) => void
}) {
  const filtered = useMemo(
    () => filterEventNodes(nodes, edges, { keyOnly, personFilter }),
    [nodes, edges, keyOnly, personFilter],
  )

  const daily = useMemo(() => {
    const scoped = filterEventNodes(nodes, edges, { keyOnly: false, personFilter })
    return scoped
      .filter((node) => !isKeyEvent(node))
      .sort((a, b) => (a.happened_at ?? '').localeCompare(b.happened_at ?? ''))
  }, [nodes, edges, personFilter])

  if (!nodes.length) {
    return <p className="empty-state">暂无事件</p>
  }

  return (
    <div className="biography-tree" aria-label="传记目录">
      <ol className="biography-tree__list biography-tree__list--spine">
        {filtered.map((node) => (
          <li
            key={node.id}
            className={`biography-tree__item biography-tree__item--${node.type ?? 'daily'}`}
            data-highlight={highlightedId === node.id ? 'true' : undefined}
          >
            <button type="button" className="biography-tree__node" onClick={() => onSelect?.(node.id)}>
              <span className="biography-tree__when">{node.happened_at?.slice(0, 10) ?? '—'}</span>
              <span className={typeBadgeClass(node.type)}>
                {TYPE_LABELS[node.type ?? ''] ?? node.type ?? '事件'}
              </span>
              <strong>{node.title}</strong>
              {node.summary ? <span className="biography-tree__summary">{node.summary}</span> : null}
            </button>
          </li>
        ))}
      </ol>
      {!keyOnly && daily.length ? (
        <details>
          <summary>日常小事（{daily.length}）</summary>
          <ol className="biography-tree__list biography-tree__list--daily">
            {daily.map((node) => (
              <li key={node.id} className="biography-tree__item biography-tree__item--daily">
                <button type="button" onClick={() => onSelect?.(node.id)}>
                  {node.title}
                </button>
              </li>
            ))}
          </ol>
        </details>
      ) : null}
    </div>
  )
}

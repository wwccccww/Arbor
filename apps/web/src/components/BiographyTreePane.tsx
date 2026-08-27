import { useMemo, useState } from 'react'
import type { EventNode } from '../api/types'

const TYPE_LABELS: Record<string, string> = {
  milestone: '里程碑',
  promise: '承诺',
  conflict: '冲突',
  daily: '日常',
  work: '工作',
}

function isKey(node: EventNode) {
  const importance = node.importance ?? 3
  const type = node.type ?? 'daily'
  return importance >= 4 || type === 'milestone' || type === 'promise' || type === 'conflict'
}

function participantsFromEdges(
  nodes: EventNode[],
  edges: { from_id: string; to_id: string; kind: string }[],
) {
  const titles = new Map(nodes.map((n) => [n.id, n.title]))
  const people = new Set<string>()
  for (const edge of edges) {
    if (edge.kind !== 'involves_person') continue
    const from = titles.get(edge.from_id)
    const to = titles.get(edge.to_id)
    if (from) people.add(from)
    if (to) people.add(to)
  }
  return [...people].sort()
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
  highlightedId,
  onSelect,
}: {
  nodes: EventNode[]
  edges?: { from_id: string; to_id: string; kind: string }[]
  keyOnly?: boolean
  highlightedId?: string
  onSelect?: (eventId: string) => void
}) {
  const [personFilter, setPersonFilter] = useState('')
  const [expandedDaily, setExpandedDaily] = useState(false)

  const participants = useMemo(() => participantsFromEdges(nodes, edges), [nodes, edges])

  const filtered = useMemo(() => {
    let list = [...nodes]
    if (keyOnly) {
      list = list.filter((node) => isKey(node))
    }
    if (personFilter) {
      const relatedIds = new Set<string>()
      for (const edge of edges) {
        if (edge.kind !== 'involves_person') continue
        const from = nodes.find((n) => n.id === edge.from_id)
        const to = nodes.find((n) => n.id === edge.to_id)
        if (from?.title === personFilter || to?.title === personFilter) {
          relatedIds.add(edge.from_id)
          relatedIds.add(edge.to_id)
        }
      }
      list = list.filter((node) => relatedIds.has(node.id))
    }
    return list.sort((a, b) => (a.happened_at ?? '').localeCompare(b.happened_at ?? ''))
  }, [nodes, edges, keyOnly, personFilter])

  const daily = useMemo(
    () =>
      nodes
        .filter((node) => !isKey(node))
        .sort((a, b) => (a.happened_at ?? '').localeCompare(b.happened_at ?? '')),
    [nodes],
  )

  if (!nodes.length) {
    return <p className="empty-state">暂无事件</p>
  }

  return (
    <div className="biography-tree" aria-label="传记目录">
      {participants.length ? (
        <label className="biography-tree__filter">
          按人物
          <select value={personFilter} onChange={(event) => setPersonFilter(event.target.value)}>
            <option value="">全部</option>
            {participants.map((name) => (
              <option key={name} value={name}>{name}</option>
            ))}
          </select>
        </label>
      ) : null}
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
        <details open={expandedDaily} onToggle={(e) => setExpandedDaily((e.target as HTMLDetailsElement).open)}>
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

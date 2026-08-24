import type { EventNode } from '../api/types'

export type EventView = 'tree' | 'timeline'

const TYPE_LABELS: Record<string, string> = {
  milestone: '里程碑',
  promise: '承诺',
  conflict: '冲突',
  daily: '日常',
  work: '工作',
}

type Edge = { from_id: string; to_id: string; kind: string }

export function EventTreePane({
  nodes,
  edges,
  forbidden,
  view = 'tree',
  keyOnly = true,
  highlightedId,
  onSelect,
  onChangeView,
  onChangeKeyOnly,
}: {
  nodes: EventNode[]
  edges?: Edge[]
  forbidden?: boolean
  view?: EventView
  keyOnly?: boolean
  highlightedId?: string
  onSelect?: (eventId: string) => void
  onChangeView?: (view: EventView) => void
  onChangeKeyOnly?: (keyOnly: boolean) => void
}) {
  if (forbidden) {
    return <p className="empty-state">没有记忆权限，事件树为空。</p>
  }
  const children = buildChildren(nodes, edges)
  const roots = nodes.filter((node) => !children.parentIds.has(node.id))
  return (
    <section>
      <section className="event-pane-head">
        <div className="view-toggle" role="group" aria-label="生命线视图">
          <button type="button" aria-pressed={view === 'tree'} onClick={() => onChangeView?.('tree')}>
            事件树
          </button>
          <button type="button" aria-pressed={view === 'timeline'} onClick={() => onChangeView?.('timeline')}>
            时间轴
          </button>
        </div>
        {onChangeKeyOnly ? (
          <label className="event-filter-row">
            <input
              type="checkbox"
              checked={keyOnly}
              onChange={(event) => onChangeKeyOnly(event.target.checked)}
            />
            仅关键事件
          </label>
        ) : null}
      </section>
      {nodes.length ? (
        view === 'tree' ? (
          <ol className="event-tree" data-view="tree">
            {roots.map((node) => (
              <TreeNode
                key={node.id}
                node={node}
                depth={0}
                childrenByParent={children.byParent}
                highlightedId={highlightedId}
                onSelect={onSelect}
              />
            ))}
          </ol>
        ) : (
          <ol className="event-tree event-timeline" data-view="timeline">
            {[...nodes]
              .sort((a, b) => String(a.happened_at ?? '').localeCompare(String(b.happened_at ?? '')))
              .map((node) => (
                <li
                  key={node.id}
                  id={`event-${node.id}`}
                  data-type={node.type}
                  data-highlighted={highlightedId === node.id ? 'true' : 'false'}
                >
                  <button type="button" onClick={() => onSelect?.(node.id)}>
                    <span className="node-title">{node.title}</span>
                    <span className="node-meta">
                      {node.type ? `${TYPE_LABELS[node.type] ?? node.type}` : ''}
                      {node.happened_at ? (node.type ? ' · ' : '') + node.happened_at : ''}
                    </span>
                  </button>
                </li>
              ))}
          </ol>
        )
      ) : (
        <p className="empty-state">{keyOnly ? '暂无关键事件' : '暂无事件'}</p>
      )}
    </section>
  )
}

function TreeNode({
  node,
  depth,
  childrenByParent,
  highlightedId,
  onSelect,
}: {
  node: EventNode
  depth: number
  childrenByParent: Map<string, EventNode[]>
  highlightedId?: string
  onSelect?: (eventId: string) => void
}) {
  const kids = childrenByParent.get(node.id) ?? []
  return (
    <li
      id={`event-${node.id}`}
      data-type={node.type}
      data-depth={depth}
      data-highlighted={highlightedId === node.id ? 'true' : 'false'}
    >
      <button type="button" onClick={() => onSelect?.(node.id)}>
        <span className="node-title">{node.title}</span>
        <span className="node-meta">
          {node.type ? `${TYPE_LABELS[node.type] ?? node.type}` : ''}
          {node.happened_at ? (node.type ? ' · ' : '') + node.happened_at : ''}
        </span>
      </button>
      {kids.length ? (
        <ol>
          {kids.map((child) => (
            <TreeNode
              key={child.id}
              node={child}
              depth={depth + 1}
              childrenByParent={childrenByParent}
              highlightedId={highlightedId}
              onSelect={onSelect}
            />
          ))}
        </ol>
      ) : null}
    </li>
  )
}

function buildChildren(nodes: EventNode[], edges?: Edge[]) {
  const byId = new Map(nodes.map((node) => [node.id, node]))
  const byParent = new Map<string, EventNode[]>()
  const parentIds = new Set<string>()
  const visited = new Set<string>()
  for (const edge of edges ?? []) {
    const parent = byId.get(edge.from_id)
    const child = byId.get(edge.to_id)
    if (!parent || !child || visited.has(child.id)) continue
    visited.add(child.id)
    parentIds.add(child.id)
    const list = byParent.get(edge.from_id) ?? []
    list.push(child)
    byParent.set(edge.from_id, list)
  }
  const seen = new Set<string>()
  for (const list of byParent.values()) {
    list.sort((a, b) => String(a.happened_at ?? '').localeCompare(String(b.happened_at ?? '')))
    for (const item of list) {
      seen.add(item.id)
      parentIds.add(item.id)
    }
  }
  return { byParent, parentIds }
}

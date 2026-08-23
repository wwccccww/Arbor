import type { EventNode } from '../api/types'

export type EventView = 'tree' | 'timeline'

const TYPE_LABELS: Record<string, string> = {
  milestone: '里程碑',
  promise: '承诺',
  conflict: '冲突',
  daily: '日常',
  work: '工作',
}

export function EventTreePane({
  nodes,
  forbidden,
  view = 'tree',
  keyOnly = true,
  highlightedId,
  onSelect,
  onChangeView,
  onChangeKeyOnly,
}: {
  nodes: EventNode[]
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
  return (
    <section>
      <section>
        <div className="view-toggle" role="group" aria-label="生命线视图">
          <button type="button" aria-pressed={view === 'tree'} onClick={() => onChangeView?.('tree')}>
            事件树
          </button>
          <button type="button" aria-pressed={view === 'timeline'} onClick={() => onChangeView?.('timeline')}>
            时间轴
          </button>
        </div>
        {onChangeKeyOnly ? (
          <div className="event-filter-row">
            <label>
              <input
                type="checkbox"
                checked={keyOnly}
                onChange={(event) => onChangeKeyOnly(event.target.checked)}
              />
              仅关键事件
            </label>
          </div>
        ) : null}
      </section>
      {nodes.length ? (
        <ol className="event-tree" data-view={view}>
          {nodes.map((node) => (
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
      ) : (
        <p className="empty-state">{keyOnly ? '暂无关键事件' : '暂无事件'}</p>
      )}
    </section>
  )
}

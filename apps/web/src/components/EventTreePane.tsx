import type { EventNode } from '../api/types'

export type EventView = 'tree' | 'timeline'

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
    return <p>没有记忆权限，事件树为空。</p>
  }
  return (
    <section>
      {onChangeView ? (
        <div className="view-toggle" role="group" aria-label="生命线视图">
          <button type="button" aria-pressed={view === 'tree'} onClick={() => onChangeView('tree')}>
            事件树
          </button>
          <button type="button" aria-pressed={view === 'timeline'} onClick={() => onChangeView('timeline')}>
            时间轴
          </button>
        </div>
      ) : null}
      {onChangeKeyOnly ? (
        <label>
          仅关键事件
          <input
            type="checkbox"
            checked={keyOnly}
            onChange={(event) => onChangeKeyOnly(event.target.checked)}
          />
        </label>
      ) : null}
      {nodes.length ? (
        <ol className="event-tree" data-view={view}>
          {nodes.map((node) => (
            <li key={node.id} id={`event-${node.id}`} data-highlighted={highlightedId === node.id ? 'true' : 'false'}>
              <button type="button" onClick={() => onSelect?.(node.id)}>
                {view === 'timeline' && node.happened_at ? <span className="eyebrow">{node.happened_at}</span> : null}
                {node.title}
              </button>
            </li>
          ))}
        </ol>
      ) : (
        <p>{keyOnly ? '暂无关键事件' : '暂无事件'}</p>
      )}
    </section>
  )
}

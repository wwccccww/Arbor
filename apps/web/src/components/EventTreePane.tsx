import { useMemo, useState } from 'react'
import type { EventNode } from '../api/types'
import { filterEventNodes, participantsFromEdges } from '../lib/eventTreeFilters'
import { BiographyTreePane } from './BiographyTreePane'
import { EventFlowCanvas } from './EventFlowCanvas'
import type { EventEdge } from './eventTreeLayout'

export type EventView = 'tree' | 'timeline' | 'biography'

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
  edges?: EventEdge[]
  forbidden?: boolean
  view?: EventView
  keyOnly?: boolean
  highlightedId?: string
  onSelect?: (eventId: string) => void
  onChangeView?: (view: EventView) => void
  onChangeKeyOnly?: (keyOnly: boolean) => void
}) {
  const [personFilter, setPersonFilter] = useState('')
  const edgeList = edges ?? []
  const participants = useMemo(
    () => participantsFromEdges(nodes, edgeList),
    [nodes, edgeList],
  )
  const filteredNodes = useMemo(
    () => filterEventNodes(nodes, edgeList, { keyOnly: false, personFilter }),
    [nodes, edgeList, personFilter],
  )

  if (forbidden) {
    return <p className="empty-state">没有记忆权限，事件树为空。</p>
  }

  return (
    <section className="event-tree-pane">
      <section className="event-pane-head">
        <div className="view-toggle" role="group" aria-label="生命线视图">
          <button type="button" aria-pressed={view === 'biography'} onClick={() => onChangeView?.('biography')}>
            传记目录
          </button>
          <button type="button" aria-pressed={view === 'tree'} onClick={() => onChangeView?.('tree')}>
            事件树
          </button>
          <button type="button" aria-pressed={view === 'timeline'} onClick={() => onChangeView?.('timeline')}>
            时间轴
          </button>
        </div>
        <div className="event-filter-row event-filter-row--group">
          {onChangeKeyOnly ? (
            <label>
              <input
                type="checkbox"
                checked={keyOnly}
                onChange={(event) => onChangeKeyOnly(event.target.checked)}
              />
              仅关键事件
            </label>
          ) : null}
          {participants.length ? (
            <label>
              按人物
              <select value={personFilter} onChange={(event) => setPersonFilter(event.target.value)}>
                <option value="">全部</option>
                {participants.map((name) => (
                  <option key={name} value={name}>{name}</option>
                ))}
              </select>
            </label>
          ) : null}
        </div>
      </section>
      {nodes.length ? (
        view === 'biography' ? (
          <BiographyTreePane
            nodes={nodes}
            edges={edgeList}
            keyOnly={keyOnly}
            personFilter={personFilter}
            highlightedId={highlightedId}
            onSelect={onSelect}
          />
        ) : (
          <div className="event-flow" data-view={view}>
            <EventFlowCanvas
              nodes={filteredNodes}
              edges={edgeList}
              view={view}
              highlightedId={highlightedId}
              onSelect={onSelect}
            />
          </div>
        )
      ) : (
        <p className="empty-state">{keyOnly ? '暂无关键事件' : '暂无事件'}</p>
      )}
    </section>
  )
}

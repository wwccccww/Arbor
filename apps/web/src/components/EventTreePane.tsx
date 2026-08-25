import { useEffect, useMemo } from 'react'
import {
  Background,
  Controls,
  ReactFlow,
  ReactFlowProvider,
  useReactFlow,
  type NodeTypes,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import type { EventNode } from '../api/types'
import { EventFlowNode } from './EventFlowNode'
import { type EventEdge, toFlowGraph } from './eventTreeLayout'

export type EventView = 'tree' | 'timeline'

const nodeTypes: NodeTypes = { event: EventFlowNode }

function EventFlowCanvas({
  nodes,
  edges,
  view,
  highlightedId,
  onSelect,
}: {
  nodes: EventNode[]
  edges?: EventEdge[]
  view: EventView
  highlightedId?: string
  onSelect?: (eventId: string) => void
}) {
  const { fitView } = useReactFlow()
  const graph = useMemo(
    () => toFlowGraph(nodes, edges, view, highlightedId),
    [nodes, edges, view, highlightedId],
  )

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void fitView({ padding: 0.18, duration: 200 })
    }, 0)
    return () => window.clearTimeout(timer)
  }, [graph, fitView])

  return (
    <ReactFlow
      nodes={graph.nodes}
      edges={graph.edges}
      nodeTypes={nodeTypes}
      nodesDraggable={false}
      nodesConnectable={false}
      elementsSelectable={false}
      panOnScroll
      zoomOnScroll
      minZoom={0.35}
      maxZoom={1.6}
      proOptions={{ hideAttribution: true }}
      onNodeClick={(_, node) => onSelect?.(node.id)}
    >
      <Background gap={18} size={1} />
      <Controls showInteractive={false} />
    </ReactFlow>
  )
}

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
  if (forbidden) {
    return <p className="empty-state">没有记忆权限，事件树为空。</p>
  }

  return (
    <section className="event-tree-pane">
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
        <div className="event-flow" data-view={view}>
          <ReactFlowProvider>
            <EventFlowCanvas
              nodes={nodes}
              edges={edges}
              view={view}
              highlightedId={highlightedId}
              onSelect={onSelect}
            />
          </ReactFlowProvider>
        </div>
      ) : (
        <p className="empty-state">{keyOnly ? '暂无关键事件' : '暂无事件'}</p>
      )}
    </section>
  )
}

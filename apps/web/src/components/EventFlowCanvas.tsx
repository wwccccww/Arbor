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

const nodeTypes: NodeTypes = { event: EventFlowNode }

function EventFlowCanvasInner({
  nodes,
  edges,
  view,
  highlightedId,
  onSelect,
}: {
  nodes: EventNode[]
  edges?: EventEdge[]
  view: 'tree' | 'timeline'
  highlightedId?: string
  onSelect?: (eventId: string) => void
}) {
  const { fitView } = useReactFlow()
  const graph = useMemo(
    () => toFlowGraph(nodes, edges, view === 'timeline' ? 'timeline' : 'tree', highlightedId),
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

export function EventFlowCanvas({
  nodes,
  edges,
  view,
  highlightedId,
  onSelect,
}: {
  nodes: EventNode[]
  edges?: EventEdge[]
  view: 'tree' | 'timeline'
  highlightedId?: string
  onSelect?: (eventId: string) => void
}) {
  return (
    <ReactFlowProvider>
      <EventFlowCanvasInner
        nodes={nodes}
        edges={edges}
        view={view}
        highlightedId={highlightedId}
        onSelect={onSelect}
      />
    </ReactFlowProvider>
  )
}

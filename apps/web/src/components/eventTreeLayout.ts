import type { Edge, Node } from '@xyflow/react'
import type { EventNode } from '../api/types'

export type EventEdge = { from_id: string; to_id: string; kind: string }

const NODE_WIDTH = 196
const NODE_HEIGHT = 72
const H_GAP = 48
const V_GAP = 56

export function buildChildren(nodes: EventNode[], edges?: EventEdge[]) {
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
  for (const list of byParent.values()) {
    list.sort((a, b) => String(a.happened_at ?? '').localeCompare(String(b.happened_at ?? '')))
  }
  return { byParent, parentIds }
}

function subtreeWidth(nodeId: string, byParent: Map<string, EventNode[]>): number {
  const kids = byParent.get(nodeId) ?? []
  if (!kids.length) return NODE_WIDTH
  return kids.reduce((sum, kid) => sum + subtreeWidth(kid.id, byParent) + H_GAP, -H_GAP)
}

function placeTreeNode(
  node: EventNode,
  depth: number,
  xCenter: number,
  byParent: Map<string, EventNode[]>,
  positions: Map<string, { x: number; y: number }>,
) {
  positions.set(node.id, { x: xCenter - NODE_WIDTH / 2, y: depth * (NODE_HEIGHT + V_GAP) })
  const kids = byParent.get(node.id) ?? []
  if (!kids.length) return
  const totalW = kids.reduce((sum, kid) => sum + subtreeWidth(kid.id, byParent) + H_GAP, -H_GAP)
  let x = xCenter - totalW / 2
  for (const kid of kids) {
    const w = subtreeWidth(kid.id, byParent)
    placeTreeNode(kid, depth + 1, x + w / 2, byParent, positions)
    x += w + H_GAP
  }
}

function layoutTreePositions(nodes: EventNode[], edges?: EventEdge[]) {
  const { byParent, parentIds } = buildChildren(nodes, edges)
  let roots = nodes.filter((node) => !parentIds.has(node.id))
  if (!roots.length && nodes.length) roots = [...nodes]
  const positions = new Map<string, { x: number; y: number }>()
  let cursor = 0
  for (const root of roots) {
    const w = subtreeWidth(root.id, byParent)
    placeTreeNode(root, 0, cursor + w / 2, byParent, positions)
    cursor += w + H_GAP * 2
  }
  return positions
}

function layoutTimelinePositions(nodes: EventNode[]) {
  const positions = new Map<string, { x: number; y: number }>()
  const sorted = [...nodes].sort((a, b) =>
    String(a.happened_at ?? '').localeCompare(String(b.happened_at ?? '')),
  )
  sorted.forEach((node, index) => {
    positions.set(node.id, { x: index * (NODE_WIDTH + H_GAP), y: 0 })
  })
  return positions
}

export type EventFlowNodeData = {
  title: string
  type?: string
  happened_at?: string
  highlighted?: boolean
  view: 'tree' | 'timeline'
}

export function toFlowGraph(
  nodes: EventNode[],
  edges: EventEdge[] | undefined,
  view: 'tree' | 'timeline',
  highlightedId?: string,
): { nodes: Node<EventFlowNodeData>[]; edges: Edge[] } {
  const positions =
    view === 'timeline' ? layoutTimelinePositions(nodes) : layoutTreePositions(nodes, edges)

  const flowNodes: Node<EventFlowNodeData>[] = nodes.map((node) => ({
    id: node.id,
    type: 'event',
    position: positions.get(node.id) ?? { x: 0, y: 0 },
    style: { width: NODE_WIDTH },
    data: {
      title: node.title,
      type: node.type,
      happened_at: node.happened_at,
      highlighted: highlightedId === node.id,
      view,
    },
  }))

  const flowEdges: Edge[] = (edges ?? []).map((edge) => ({
    id: `${edge.from_id}-${edge.to_id}-${edge.kind}`,
    source: edge.from_id,
    target: edge.to_id,
    type: view === 'timeline' ? 'smoothstep' : 'default',
    label: edge.kind,
    animated: edge.kind === 'caused_by',
  }))

  return { nodes: flowNodes, edges: flowEdges }
}

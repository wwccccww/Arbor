import type { EventNode } from '../api/types'

export type EventEdge = { from_id: string; to_id: string; kind: string }

export function isKeyEvent(node: EventNode) {
  const importance = node.importance ?? 3
  const type = node.type ?? 'daily'
  return importance >= 4 || type === 'milestone' || type === 'promise' || type === 'conflict'
}

export function participantsFromEdges(nodes: EventNode[], edges: EventEdge[]) {
  const titles = new Map(nodes.map((node) => [node.id, node.title]))
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

export function filterEventNodes(
  nodes: EventNode[],
  edges: EventEdge[],
  options: { keyOnly?: boolean; personFilter?: string },
) {
  const { keyOnly = true, personFilter = '' } = options
  let list = [...nodes]
  if (keyOnly) {
    list = list.filter((node) => isKeyEvent(node))
  }
  if (personFilter) {
    const relatedIds = new Set<string>()
    for (const edge of edges) {
      if (edge.kind !== 'involves_person') continue
      const from = nodes.find((node) => node.id === edge.from_id)
      const to = nodes.find((node) => node.id === edge.to_id)
      if (from?.title === personFilter || to?.title === personFilter) {
        relatedIds.add(edge.from_id)
        relatedIds.add(edge.to_id)
      }
    }
    list = list.filter((node) => relatedIds.has(node.id))
  }
  return list
}

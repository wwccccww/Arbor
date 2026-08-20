import type { EventNode } from '../api/types'

export function EventTreePane({
  nodes,
  forbidden,
  highlightedId,
  onSelect,
}: {
  nodes: EventNode[]
  forbidden?: boolean
  highlightedId?: string
  onSelect?: (eventId: string) => void
}) {
  if (forbidden) {
    return <p>没有记忆权限，事件树为空。</p>
  }
  if (!nodes.length) {
    return <p>暂无关键事件</p>
  }
  return (
    <ol className="event-tree">
      {nodes.map((node) => (
        <li key={node.id} id={`event-${node.id}`} data-highlighted={highlightedId === node.id ? 'true' : 'false'}>
          <button type="button" onClick={() => onSelect?.(node.id)}>
            {node.title}
          </button>
        </li>
      ))}
    </ol>
  )
}

import { Handle, Position, type Node, type NodeProps } from '@xyflow/react'
import type { EventFlowNodeData } from './eventTreeLayout'

const TYPE_LABELS: Record<string, string> = {
  milestone: '里程碑',
  promise: '承诺',
  conflict: '冲突',
  daily: '日常',
  work: '工作',
}

export function EventFlowNode({ id, data }: NodeProps<Node<EventFlowNodeData, 'event'>>) {
  const typeLabel = data.type ? (TYPE_LABELS[data.type] ?? data.type) : ''
  const meta = [typeLabel, data.happened_at].filter(Boolean).join(' · ')
  const target = data.view === 'timeline' ? Position.Left : Position.Top
  const source = data.view === 'timeline' ? Position.Right : Position.Bottom

  return (
    <button
      type="button"
      aria-label={data.title}
      className={`event-flow-node${data.highlighted ? ' event-flow-node--highlighted' : ''}`}
      data-type={data.type}
      id={`event-${id}`}
    >
      <Handle type="target" position={target} />
      <span className="node-title">{data.title}</span>
      {meta ? <span className="node-meta">{meta}</span> : null}
      <Handle type="source" position={source} />
    </button>
  )
}

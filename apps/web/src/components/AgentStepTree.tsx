import type { AgentStepTreeNode } from '../api/types'

type Props = {
  tree: AgentStepTreeNode
}

function StepTreeNode({ node, depth = 0 }: { node: AgentStepTreeNode; depth?: number }) {
  const hasChildren = Array.isArray(node.children) && node.children.length > 0
  return (
    <li className="agent-step-tree__item" data-depth={depth}>
      <div className="agent-step-tree__row">
        <span className="agent-step-tree__label">{node.label ?? node.kind ?? node.type}</span>
        {node.status ? <span className="badge">{node.status}</span> : null}
        {node.latency_ms != null ? <span className="muted">{node.latency_ms}ms</span> : null}
        {node.type && node.type !== 'run' ? <span className="badge badge--promise">{node.type}</span> : null}
      </div>
      {hasChildren ? (
        <ul className="agent-step-tree">
          {node.children!.map((child, index) => (
            <StepTreeNode key={`${child.id ?? child.type}-${index}`} node={child} depth={depth + 1} />
          ))}
        </ul>
      ) : null}
    </li>
  )
}

export function AgentStepTree({ tree }: Props) {
  return (
    <ul className="agent-step-tree agent-step-tree--root">
      <StepTreeNode node={tree} />
    </ul>
  )
}

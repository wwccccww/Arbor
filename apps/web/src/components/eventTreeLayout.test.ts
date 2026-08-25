import { describe, expect, it } from 'vitest'
import { toFlowGraph } from './eventTreeLayout'

describe('toFlowGraph', () => {
  it('lays out tree nodes with parent-child edges', () => {
    const { nodes, edges } = toFlowGraph(
      [
        { id: 'a', title: '第一次见面', happened_at: '2024-01-01' },
        { id: 'b', title: '面店争吵', happened_at: '2024-02-01' },
      ],
      [{ from_id: 'a', to_id: 'b', kind: 'temporal' }],
      'tree',
    )
    expect(nodes).toHaveLength(2)
    expect(edges).toHaveLength(1)
    expect(edges[0]?.source).toBe('a')
    expect(edges[0]?.target).toBe('b')
    const root = nodes.find((node) => node.id === 'a')
    const child = nodes.find((node) => node.id === 'b')
    expect(root?.position.y).toBeLessThan(child?.position.y ?? 0)
  })

  it('orders timeline nodes left to right by happened_at', () => {
    const { nodes } = toFlowGraph(
      [
        { id: 'b', title: '后', happened_at: '2024-02-01' },
        { id: 'a', title: '先', happened_at: '2024-01-01' },
      ],
      [],
      'timeline',
    )
    const first = nodes.find((node) => node.id === 'a')
    const second = nodes.find((node) => node.id === 'b')
    expect(first?.position.x).toBeLessThan(second?.position.x ?? 0)
    expect(first?.data.view).toBe('timeline')
  })
})

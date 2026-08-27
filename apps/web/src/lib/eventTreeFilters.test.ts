import { describe, expect, it } from 'vitest'
import { filterEventNodes, participantsFromEdges } from './eventTreeFilters'

describe('eventTreeFilters', () => {
  const nodes = [
    { id: 'e1', title: '面店争吵', type: 'conflict', importance: 5 },
    { id: 'e2', title: '日常通话', type: 'daily', importance: 2 },
  ]
  const edges = [
    { from_id: 'e1', to_id: 'p-linxia', kind: 'involves_person' },
    { from_id: 'p-linxia', to_id: 'e2', kind: 'involves_person' },
  ]

  it('filters by person name across nodes', () => {
    const people = participantsFromEdges(
      [...nodes, { id: 'p-linxia', title: '林夏' }],
      edges,
    )
    expect(people).toContain('林夏')
    const filtered = filterEventNodes(
      [...nodes, { id: 'p-linxia', title: '林夏' }],
      edges,
      { keyOnly: false, personFilter: '林夏' },
    )
    expect(filtered.map((node) => node.id)).toEqual(['e1', 'e2', 'p-linxia'])
  })

  it('filters key events only', () => {
    const filtered = filterEventNodes(nodes, edges, { keyOnly: true, personFilter: '' })
    expect(filtered.map((node) => node.id)).toEqual(['e1'])
  })
})

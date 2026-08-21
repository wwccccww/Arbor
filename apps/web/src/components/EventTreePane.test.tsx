import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { describe, expect, it, vi } from 'vitest'
import { createClient } from '../api/client'
import { DEMO_OWNER } from '../session'
import type { EventNode } from '../api/types'
import { EventTreePane, type EventView } from './EventTreePane'

describe('EventTreePane', () => {
  it('shows an empty state without read_memory', () => {
    render(<EventTreePane nodes={[]} forbidden />)
    expect(screen.getByText('没有记忆权限，事件树为空。')).toBeInTheDocument()
    expect(screen.queryByRole('list')).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '时间轴' })).not.toBeInTheDocument()
  })

  it('reloads the same API with view=timeline', async () => {
    const user = userEvent.setup()
    const fetchImpl = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input)
      const timeline = url.includes('view=timeline')
      return new Response(
        JSON.stringify({
          nodes: timeline
            ? [
                { id: 'evt-meet', title: '第一次见面', happened_at: '2024-01-01T00:00:00Z' },
                { id: 'evt-fight', title: '面店争吵', happened_at: '2024-11-02T00:00:00Z' },
              ]
            : [{ id: 'evt-fight', title: '面店争吵', happened_at: '2024-11-02T00:00:00Z' }],
          edges: [],
        }),
        { status: 200, headers: { 'Content-Type': 'application/json' } },
      )
    }) as unknown as typeof fetch
    const client = createClient(DEMO_OWNER, fetchImpl)

    function Harness() {
      const [view, setView] = useState<EventView>('tree')
      const [nodes, setNodes] = useState<EventNode[]>([
        { id: 'evt-fight', title: '面店争吵', happened_at: '2024-11-02T00:00:00Z' },
      ])
      return (
        <EventTreePane
          nodes={nodes}
          view={view}
          onChangeView={(next) => {
            setView(next)
            void client.getEventTree('linxia', next).then((tree) => setNodes(tree.nodes))
          }}
        />
      )
    }

    render(<Harness />)
    await user.click(screen.getByRole('button', { name: '时间轴' }))
    expect(await screen.findByText('第一次见面')).toBeInTheDocument()
    expect(screen.getByText('2024-01-01T00:00:00Z')).toBeInTheDocument()
    const urls = (fetchImpl as unknown as ReturnType<typeof vi.fn>).mock.calls.map((call) => String(call[0]))
    expect(urls).toContain('/v1/personas/linxia/events/tree?view=timeline')
  })
})

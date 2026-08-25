import { fireEvent, render, screen } from '@testing-library/react'
import { useState } from 'react'
import { describe, expect, it, vi } from 'vitest'
import { createClient } from '../api/client'
import { DEMO_OWNER } from '../session'
import type { EventCard } from '../api/types'
import { EventCardPane } from './EventCardPane'
import { EventTreePane } from './EventTreePane'

describe('EventCardPane', () => {
  it('loads the event card from GET /v1/events/:id', async () => {
    const fetchImpl = vi.fn(async (input: RequestInfo | URL) => {
      expect(String(input)).toBe('/v1/events/evt-fight')
      return new Response(
        JSON.stringify({
          id: 'evt-fight',
          title: '面店争吵',
          happened_at: '2024-11-02T00:00:00Z',
          summary: '去年十一月在面店吵过',
          memories: [{ id: 'mem-1', text: '在西湖附近的面店吵了一架' }],
          attachments: [{ id: 'att-1', type: 'image_caption', text: '合影：雨天的店门口' }],
        }),
        { status: 200, headers: { 'Content-Type': 'application/json' } },
      )
    }) as unknown as typeof fetch
    const client = createClient(DEMO_OWNER, fetchImpl)

    function Harness() {
      const [card, setCard] = useState<EventCard | null>(null)
      return (
        <>
          <EventTreePane
            nodes={[{ id: 'evt-fight', title: '面店争吵' }]}
            onSelect={(eventId) => {
              void client.getEventCard(eventId).then(setCard)
            }}
          />
          <EventCardPane card={card} />
        </>
      )
    }

    render(<Harness />)
    const node = await screen.findByText('面店争吵')
    fireEvent.click(node.closest('button')!)
    expect(await screen.findByRole('heading', { name: '面店争吵' })).toBeInTheDocument()
    expect(screen.getByText('在西湖附近的面店吵了一架')).toBeInTheDocument()
    expect(screen.getByText('合影：雨天的店门口')).toBeInTheDocument()
    expect(screen.getByText('image_caption')).toBeInTheDocument()
  })

  it('does not show memories without read_memory', () => {
    render(
      <EventCardPane
        card={{
          id: 'evt-fight',
          forbidden: true,
          memories: [{ id: 'mem-1', text: '不该泄露的正文' }],
          attachments: [],
        }}
      />,
    )
    expect(screen.getByText('没有记忆权限，无法打开事件卡。')).toBeInTheDocument()
    expect(screen.queryByText('不该泄露的正文')).not.toBeInTheDocument()
  })
})

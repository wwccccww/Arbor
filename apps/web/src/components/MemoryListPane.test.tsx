import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { describe, expect, it, vi } from 'vitest'
import { createClient } from '../api/client'
import { DEMO_OWNER } from '../session'
import type { MemoryItem } from '../api/types'
import { MemoryListPane } from './MemoryListPane'

describe('MemoryListPane', () => {
  it('hides memory text without read_memory', () => {
    render(
      <MemoryListPane
        items={[{ id: 'mem-1', text: '林夏讨厌香菜', type: 'fact' }]}
        forbidden
      />,
    )
    expect(screen.getByText('没有记忆权限，列表为空。')).toBeInTheDocument()
    expect(screen.queryByText('林夏讨厌香菜')).not.toBeInTheDocument()
    expect(screen.queryByLabelText('类型')).not.toBeInTheDocument()
  })

  it('filters by type and opens the related event', async () => {
    const user = userEvent.setup()
    const fetchImpl = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input)
      const captions = url.includes('type=image_caption')
      return new Response(
        JSON.stringify({
          items: captions
            ? [{ id: 'cap-1', text: '合影：雨天的店门口', type: 'image_caption', event_id: 'evt-meet' }]
            : [{ id: 'fact-1', text: '林夏讨厌香菜', type: 'fact' }],
          total: 1,
        }),
        { status: 200, headers: { 'Content-Type': 'application/json' } },
      )
    }) as unknown as typeof fetch
    const client = createClient(DEMO_OWNER, fetchImpl)
    const onSelect = vi.fn()

    function Harness() {
      const [items, setItems] = useState<MemoryItem[]>([
        { id: 'fact-1', text: '林夏讨厌香菜', type: 'fact' },
      ])
      const [type, setType] = useState('')
      return (
        <MemoryListPane
          items={items}
          total={items.length}
          type={type}
          onSelect={onSelect}
          onChangeType={(next) => {
            setType(next)
            void client.listMemories('linxia', { type: next || undefined }).then((page) => setItems(page.items))
          }}
        />
      )
    }

    render(<Harness />)
    await user.selectOptions(screen.getByLabelText('类型'), 'image_caption')
    expect(await screen.findByText('合影：雨天的店门口')).toBeInTheDocument()
    expect((fetchImpl as unknown as ReturnType<typeof vi.fn>).mock.calls[0][0]).toBe(
      '/v1/personas/linxia/memories?type=image_caption',
    )
    await user.click(screen.getByRole('button', { name: /合影：雨天的店门口/ }))
    expect(onSelect).toHaveBeenCalledWith('evt-meet')
  })
})

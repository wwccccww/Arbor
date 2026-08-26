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
    expect(screen.queryByLabelText('状态')).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '下一页' })).not.toBeInTheDocument()
    expect(screen.queryByLabelText('仅当前事件')).not.toBeInTheDocument()
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

  it('filters by superseded status', async () => {
    const user = userEvent.setup()
    const fetchImpl = vi.fn(async (input: RequestInfo | URL) => {
      const superseded = String(input).includes('status=superseded')
      return new Response(
        JSON.stringify({
          items: superseded
            ? [{ id: 'old-1', text: '旧的猫咪名', type: 'fact', status: 'superseded' }]
            : [{ id: 'fact-1', text: '林夏讨厌香菜', type: 'fact', status: 'active' }],
          total: 1,
        }),
        { status: 200, headers: { 'Content-Type': 'application/json' } },
      )
    }) as unknown as typeof fetch
    const client = createClient(DEMO_OWNER, fetchImpl)

    function Harness() {
      const [items, setItems] = useState<MemoryItem[]>([
        { id: 'fact-1', text: '林夏讨厌香菜', type: 'fact', status: 'active' },
      ])
      const [status, setStatus] = useState('active')
      return (
        <MemoryListPane
          items={items}
          total={items.length}
          status={status}
          onChangeStatus={(next) => {
            setStatus(next)
            void client.listMemories('linxia', { status: next !== 'active' ? next : undefined }).then((page) => {
              setItems(page.items)
            })
          }}
        />
      )
    }

    render(<Harness />)
    await user.selectOptions(screen.getByLabelText('状态'), 'superseded')
    expect(await screen.findByText('旧的猫咪名')).toBeInTheDocument()
    expect(screen.getByText(/fact · superseded/)).toBeInTheDocument()
    expect((fetchImpl as unknown as ReturnType<typeof vi.fn>).mock.calls[0][0]).toBe(
      '/v1/personas/linxia/memories?status=superseded',
    )
  })

  it('pages memories with offset', async () => {
    const user = userEvent.setup()
    const fetchImpl = vi.fn(async (input: RequestInfo | URL) => {
      const second = String(input).includes('offset=1')
      return new Response(
        JSON.stringify({
          items: second
            ? [{ id: 'mem-2', text: '旧的猫咪名', type: 'fact' }]
            : [{ id: 'mem-1', text: '林夏讨厌香菜', type: 'fact' }],
          total: 2,
        }),
        { status: 200, headers: { 'Content-Type': 'application/json' } },
      )
    }) as unknown as typeof fetch
    const client = createClient(DEMO_OWNER, fetchImpl)
    const pageSize = 1

    function Harness() {
      const [items, setItems] = useState<MemoryItem[]>([{ id: 'mem-1', text: '林夏讨厌香菜', type: 'fact' }])
      const [offset, setOffset] = useState(0)
      return (
        <MemoryListPane
          items={items}
          total={2}
          offset={offset}
          pageSize={pageSize}
          onPage={(next) => {
            setOffset(next)
            void client.listMemories('linxia', { limit: pageSize, offset: next }).then((page) => setItems(page.items))
          }}
        />
      )
    }

    render(<Harness />)
    expect(screen.getByText('1–1 / 2')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: '下一页' }))
    expect(await screen.findByText('旧的猫咪名')).toBeInTheDocument()
    expect((fetchImpl as unknown as ReturnType<typeof vi.fn>).mock.calls[0][0]).toBe(
      '/v1/personas/linxia/memories?limit=1&offset=1',
    )
  })

  it('filters memories by the current event', async () => {
    const user = userEvent.setup()
    const fetchImpl = vi.fn(async (input: RequestInfo | URL) => {
      const byEvent = String(input).includes('event_id=evt-meet')
      return new Response(
        JSON.stringify({
          items: byEvent
            ? [{ id: 'cap-1', text: '合影：雨天的店门口', type: 'image_caption', event_id: 'evt-meet' }]
            : [{ id: 'fact-1', text: '林夏讨厌香菜', type: 'fact' }],
          total: 1,
        }),
        { status: 200, headers: { 'Content-Type': 'application/json' } },
      )
    }) as unknown as typeof fetch
    const client = createClient(DEMO_OWNER, fetchImpl)

    function Harness() {
      const [items, setItems] = useState<MemoryItem[]>([{ id: 'fact-1', text: '林夏讨厌香菜', type: 'fact' }])
      const [filterByEvent, setFilterByEvent] = useState(false)
      return (
        <MemoryListPane
          items={items}
          total={items.length}
          eventId="evt-meet"
          filterByEvent={filterByEvent}
          onToggleEventFilter={(next) => {
            setFilterByEvent(next)
            void client
              .listMemories('linxia', { event_id: next ? 'evt-meet' : undefined })
              .then((page) => setItems(page.items))
          }}
        />
      )
    }

    render(<Harness />)
    await user.click(screen.getByLabelText('仅当前事件'))
    expect(await screen.findByText('合影：雨天的店门口')).toBeInTheDocument()
    expect((fetchImpl as unknown as ReturnType<typeof vi.fn>).mock.calls[0][0]).toBe(
      '/v1/personas/linxia/memories?event_id=evt-meet',
    )
  })

  it('deletes a memory when admin callback is provided', async () => {
    const user = userEvent.setup()
    const fetchImpl = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input)
      if (init?.method === 'DELETE') {
        return new Response(null, { status: 204 })
      }
      return new Response(
        JSON.stringify({
          items: [{ id: 'mem-del', text: '待删记忆', type: 'fact' }],
          total: 1,
        }),
        { status: 200, headers: { 'Content-Type': 'application/json' } },
      )
    }) as unknown as typeof fetch
    const client = createClient(DEMO_OWNER, fetchImpl)
    const onDelete = vi.fn(async (memoryId: string) => {
      await client.deleteMemory('linxia', memoryId)
    })

    render(
      <MemoryListPane
        items={[{ id: 'mem-del', text: '待删记忆', type: 'fact' }]}
        onDelete={(id) => void onDelete(id)}
      />,
    )

    await user.click(screen.getByRole('button', { name: '删除记忆 mem-del' }))
    const deleteCall = (fetchImpl as unknown as ReturnType<typeof vi.fn>).mock.calls.find(
      (call) => (call[1] as RequestInit | undefined)?.method === 'DELETE',
    )
    expect(deleteCall?.[0]).toBe('/v1/personas/linxia/memories/mem-del')
    expect(onDelete).toHaveBeenCalledWith('mem-del')
  })
})

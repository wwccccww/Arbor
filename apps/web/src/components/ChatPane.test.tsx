import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { describe, expect, it, vi } from 'vitest'
import { createClient } from '../api/client'
import { DEMO_OWNER } from '../session'
import type { ChatMessage, Thread } from '../api/types'
import { ChatPane } from './ChatPane'

describe('ChatPane', () => {
  it('renders assistant citations in the reply area', async () => {
    const user = userEvent.setup()
    const onJump = vi.fn()
    render(
      <ChatPane
        messages={[
          {
            id: 'a1',
            role: 'assistant',
            text: '上次是在西湖附近吵的。',
            citations: [{ memory_id: 'mem-1', event_id: 'evt-1', preview: '去年十一月在西湖' }],
          },
        ]}
        onSend={vi.fn()}
        onJump={onJump}
      />,
    )
    expect(screen.getByLabelText('依据')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: '去年十一月在西湖' }))
    expect(onJump).toHaveBeenCalledWith('evt-1')
  })

  it('sends a multipart file and downloads it from history', async () => {
    const user = userEvent.setup()
    const fetchImpl = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input)
      if (url.endsWith('/messages') && init?.method === 'POST') {
        return new Response(
          JSON.stringify({
            message_id: 'a1',
            role: 'assistant',
            text: '看到了',
            citations: [],
            attachments: [{ filename: 'note.txt' }],
          }),
          { status: 200, headers: { 'Content-Type': 'application/json' } },
        )
      }
      if (url.endsWith('/attachments/note.txt')) {
        return new Response('聊天附件不该进记忆', {
          status: 200,
          headers: { 'Content-Type': 'application/octet-stream' },
        })
      }
      return new Response(JSON.stringify({ error: { code: 'NOT_FOUND', message: 'not found' } }), { status: 404 })
    }) as unknown as typeof fetch
    const client = createClient(DEMO_OWNER, fetchImpl)
    const onSend = vi.fn(async (text: string, file?: File) => {
      await client.sendMessage('0a000000-0000-4000-a000-000000000030', text, file)
    })
    const onOpen = vi.fn(async (filename: string) => {
      await client.downloadAttachment('0a000000-0000-4000-a000-000000000030', filename)
    })
    const file = new File(['聊天附件不该进记忆'], 'note.txt', { type: 'text/plain' })

    render(
      <ChatPane
        messages={[
          {
            id: 'u1',
            role: 'user',
            text: '看看这个',
            citations: [],
            attachments: [{ filename: 'note.txt' }],
          },
        ]}
        onSend={(text, picked) => void onSend(text, picked)}
        onJump={vi.fn()}
        onOpenAttachment={(filename) => void onOpen(filename)}
      />,
    )

    await user.upload(screen.getByLabelText('选择附件'), file)
    await user.type(screen.getByLabelText('发送消息'), '看看这个')
    await user.click(screen.getByRole('button', { name: '发送' }))

    const sendCall = (fetchImpl as unknown as ReturnType<typeof vi.fn>).mock.calls.find((call) =>
      String(call[0]).endsWith('/v1/threads/0a000000-0000-4000-a000-000000000030/messages'),
    )
    expect(sendCall).toBeTruthy()
    expect((sendCall?.[1] as RequestInit).method).toBe('POST')
    expect((sendCall?.[1] as RequestInit).body).toBeInstanceOf(FormData)
    const sent = (sendCall?.[1] as RequestInit).body as FormData
    expect((sent.get('file') as File).name).toBe('note.txt')
    expect(sent.get('text')).toBe('看看这个')
    expect(new Headers((sendCall?.[1] as RequestInit).headers).get('Content-Type')).toBeNull()

    await user.click(screen.getByRole('button', { name: 'note.txt' }))
    const downloadCall = (fetchImpl as unknown as ReturnType<typeof vi.fn>).mock.calls.find((call) =>
      String(call[0]).endsWith('/v1/threads/0a000000-0000-4000-a000-000000000030/attachments/note.txt'),
    )
    expect(downloadCall).toBeTruthy()
  })

  it('exports the thread as JSON', async () => {
    const user = userEvent.setup()
    const fetchImpl = vi.fn(async () =>
      new Response(
        JSON.stringify({
          id: '0a000000-0000-4000-a000-000000000030',
          persona_id: '0a000000-0000-4000-a000-000000000010',
          messages: [{ role: 'user', content: '还在吗', citations: [], attachments: [] }],
        }),
        { status: 200, headers: { 'Content-Type': 'application/json' } },
      ),
    ) as unknown as typeof fetch
    const client = createClient(DEMO_OWNER, fetchImpl)

    render(
      <ChatPane
        messages={[]}
        onSend={vi.fn()}
        onJump={vi.fn()}
        onExport={() => {
          void client.exportThread('0a000000-0000-4000-a000-000000000030')
        }}
      />,
    )

    await user.click(screen.getByRole('button', { name: '导出会话' }))
    const [url, init] = (fetchImpl as unknown as ReturnType<typeof vi.fn>).mock.calls[0]
    expect(url).toBe('/v1/threads/0a000000-0000-4000-a000-000000000030/export')
    expect((init as RequestInit).method).toBe('POST')
  })

  it('pages older messages with offset', async () => {
    const user = userEvent.setup()
    const fetchImpl = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input)
      const second = url.includes('offset=1')
      return new Response(
        JSON.stringify({
          items: [
            {
              id: second ? 'm1' : 'm0',
              role: 'user',
              content: second ? '第二页' : '第一页',
              citations: [],
            },
          ],
          total: 2,
        }),
        { status: 200, headers: { 'Content-Type': 'application/json' } },
      )
    }) as unknown as typeof fetch
    const client = createClient(DEMO_OWNER, fetchImpl)
    const pageSize = 1

    function Harness() {
      const [messages, setMessages] = useState<ChatMessage[]>([
        { id: 'm0', role: 'user', text: '第一页', citations: [] },
      ])
      const [offset, setOffset] = useState(0)
      return (
        <ChatPane
          messages={messages}
          offset={offset}
          total={2}
          pageSize={pageSize}
          onSend={vi.fn()}
          onJump={vi.fn()}
          onPage={(next) => {
            setOffset(next)
            void client
              .listMessages('0a000000-0000-4000-a000-000000000030', { limit: pageSize, offset: next })
              .then((page) => setMessages(page.items))
          }}
        />
      )
    }

    render(<Harness />)
    expect(screen.getByText('1–1 / 2')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: '下一页' }))
    expect(await screen.findByText('第二页')).toBeInTheDocument()
    expect((fetchImpl as unknown as ReturnType<typeof vi.fn>).mock.calls[0][0]).toBe(
      '/v1/threads/0a000000-0000-4000-a000-000000000030/messages?limit=1&offset=1',
    )
  })

  it('loads messages for the selected thread', async () => {
    const user = userEvent.setup()
    const fetchImpl = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input)
      if (url.includes('/threads/t-2/messages')) {
        return new Response(
          JSON.stringify({
            items: [{ id: 'm2', role: 'user', content: '第二段', citations: [] }],
            total: 1,
          }),
          { status: 200, headers: { 'Content-Type': 'application/json' } },
        )
      }
      return new Response(JSON.stringify({ error: { code: 'NOT_FOUND', message: 'not found' } }), { status: 404 })
    }) as unknown as typeof fetch
    const client = createClient(DEMO_OWNER, fetchImpl)

    function Harness() {
      const [threadId, setThreadId] = useState('t-1')
      const [messages, setMessages] = useState<ChatMessage[]>([
        { id: 'm1', role: 'user', text: '第一段', citations: [] },
      ])
      return (
        <ChatPane
          messages={messages}
          threads={[
            { id: 't-1', persona_id: 'p1' },
            { id: 't-2', persona_id: 'p1' },
          ]}
          threadId={threadId}
          onSend={vi.fn()}
          onJump={vi.fn()}
          onSwitchThread={(id) => {
            setThreadId(id)
            void client.listMessages(id).then((page) => setMessages(page.items))
          }}
        />
      )
    }

    render(<Harness />)
    expect(screen.getByText('第一段')).toBeInTheDocument()
    await user.selectOptions(screen.getByLabelText('会话'), 't-2')
    expect(await screen.findByText('第二段')).toBeInTheDocument()
    expect((fetchImpl as unknown as ReturnType<typeof vi.fn>).mock.calls[0][0]).toBe(
      '/v1/threads/t-2/messages?limit=50&offset=0',
    )
  })

  it('creates a new thread', async () => {
    const user = userEvent.setup()
    const fetchImpl = vi.fn(async (_input: RequestInfo | URL, init?: RequestInit) => {
      if (init?.method === 'POST') {
        return new Response(JSON.stringify({ id: 't-3', persona_id: 'p1' }), {
          status: 201,
          headers: { 'Content-Type': 'application/json' },
        })
      }
      return new Response(JSON.stringify({ items: [], total: 0 }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      })
    }) as unknown as typeof fetch
    const client = createClient(DEMO_OWNER, fetchImpl)

    function Harness() {
      const [threadId, setThreadId] = useState('t-1')
      const [threads, setThreads] = useState<Thread[]>([{ id: 't-1', persona_id: 'p1' }])
      return (
        <ChatPane
          messages={[]}
          threads={threads}
          threadId={threadId}
          onSend={vi.fn()}
          onJump={vi.fn()}
          onSwitchThread={setThreadId}
          onNewThread={() => {
            void client.createThread('p1').then((created) => {
              setThreads((current) => [...current, created])
              setThreadId(created.id)
            })
          }}
        />
      )
    }

    render(<Harness />)
    await user.click(screen.getByRole('button', { name: '新会话' }))
    expect(await screen.findByRole('option', { name: '会话 2' })).toBeInTheDocument()
    const postCall = (fetchImpl as unknown as ReturnType<typeof vi.fn>).mock.calls.find(
      (call) => (call[1] as RequestInit | undefined)?.method === 'POST',
    )
    expect(postCall?.[0]).toBe('/v1/personas/p1/threads')
  })
})

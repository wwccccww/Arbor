import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { createClient } from '../api/client'
import { DEMO_OWNER } from '../session'
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
})

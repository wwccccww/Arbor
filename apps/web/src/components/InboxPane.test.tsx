import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { createClient } from '../api/client'
import { DEMO_OWNER } from '../session'
import { InboxPane } from './InboxPane'

describe('InboxPane', () => {
  it('confirm and dismiss call the inbox API', async () => {
    const user = userEvent.setup()
    const fetchImpl = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input)
      if (url.endsWith('/confirm') || url.endsWith('/dismiss')) {
        return new Response(JSON.stringify({ ok: true, id: 'mem-1' }), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        })
      }
      return new Response(JSON.stringify({ error: { code: 'NOT_FOUND', message: 'not found' } }), { status: 404 })
    }) as unknown as typeof fetch
    const client = createClient(DEMO_OWNER, fetchImpl)
    const onConfirm = async (inboxId: string, opts: { markKeyEvent: boolean }) => {
      await client.confirmInbox(inboxId, opts)
    }
    const onDismiss = async (inboxId: string) => {
      await client.dismissInbox(inboxId)
    }

    render(
      <InboxPane
        items={[{ id: 'in-1', kind: 'fact', status: 'pending', payload: { text: '林夏最近开始喝美式' } }]}
        onConfirm={(id, opts) => void onConfirm(id, opts)}
        onDismiss={(id) => void onDismiss(id)}
      />,
    )

    await user.click(screen.getByRole('checkbox', { name: '标成关键事件' }))
    await user.click(screen.getByRole('button', { name: '记下来' }))
    const confirmCall = (fetchImpl as unknown as ReturnType<typeof vi.fn>).mock.calls.find((call) =>
      String(call[0]).endsWith('/v1/inbox/in-1/confirm'),
    )
    expect(confirmCall).toBeTruthy()
    expect((confirmCall?.[1] as RequestInit).method).toBe('POST')
    expect(JSON.parse(String((confirmCall?.[1] as RequestInit).body))).toEqual({ mark_key_event: true })

    await user.click(screen.getByRole('button', { name: '忽略' }))
    const dismissCall = (fetchImpl as unknown as ReturnType<typeof vi.fn>).mock.calls.find((call) =>
      String(call[0]).endsWith('/v1/inbox/in-1/dismiss'),
    )
    expect(dismissCall).toBeTruthy()
    expect((dismissCall?.[1] as RequestInit).method).toBe('POST')
  })

  it('calls bootstrap handler when provided', async () => {
    const user = userEvent.setup()
    const onBootstrap = vi.fn()
    render(
      <InboxPane
        items={[{ id: 'in-1', kind: 'fact', status: 'pending', payload: { text: '测试' } }]}
        onConfirm={vi.fn()}
        onDismiss={vi.fn()}
        onBootstrap={onBootstrap}
      />,
    )
    await user.click(screen.getByRole('button', { name: '一键写入记忆并建树' }))
    expect(onBootstrap).toHaveBeenCalled()
  })

  it('does not list payload text without write_memory', () => {
    render(
      <InboxPane
        items={[]}
        forbidden
        onConfirm={vi.fn()}
        onDismiss={vi.fn()}
      />,
    )
    expect(screen.getByText('没有写入权限，收件箱为空。')).toBeInTheDocument()
    expect(screen.queryByText('林夏最近开始喝美式')).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '记下来' })).not.toBeInTheDocument()
  })
})

import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { FeishuCalendarConnect } from './FeishuCalendarConnect'

describe('FeishuCalendarConnect', () => {
  it('renders nothing when integration is disabled', () => {
    const client = {
      getFeishuCalendarStatus: vi.fn(),
    }
    const { container } = render(
      <FeishuCalendarConnect client={client as never} editable enabled={false} />,
    )
    expect(container).toBeEmptyDOMElement()
    expect(client.getFeishuCalendarStatus).not.toHaveBeenCalled()
  })

  it('shows connect button when not linked', async () => {
    const client = {
      getFeishuCalendarStatus: vi.fn(async () => ({
        connected: false,
        provider: 'feishu',
      })),
      getFeishuConnectUrl: vi.fn(),
      disconnectFeishu: vi.fn(),
    }
    render(<FeishuCalendarConnect client={client as never} editable />)
    expect(await screen.findByRole('button', { name: '连接飞书日历' })).toBeInTheDocument()
    expect(screen.getByText(/未连接/)).toBeInTheDocument()
  })

  it('opens authorize url on connect', async () => {
    const user = userEvent.setup()
    const client = {
      getFeishuCalendarStatus: vi.fn(async () => ({
        connected: false,
        provider: 'feishu',
      })),
      getFeishuConnectUrl: vi.fn(async () => ({
        authorize_url: 'https://open.feishu.cn/oauth',
        provider: 'feishu',
      })),
      disconnectFeishu: vi.fn(),
    }
    const assign = vi.fn()
    vi.stubGlobal('location', { ...window.location, href: '', assign })
    Object.defineProperty(window, 'location', {
      value: { href: '' },
      writable: true,
    })
    render(<FeishuCalendarConnect client={client as never} editable />)
    await waitFor(() => screen.getByRole('button', { name: '连接飞书日历' }))
    await user.click(screen.getByRole('button', { name: '连接飞书日历' }))
    expect(client.getFeishuConnectUrl).toHaveBeenCalled()
    expect(window.location.href).toBe('https://open.feishu.cn/oauth')
    vi.unstubAllGlobals()
  })
})

import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { YunhuiToolPane } from './YunhuiToolPane'

describe('YunhuiToolPane', () => {
  it('shows hint when mall tools are not allowed', () => {
    render(
      <YunhuiToolPane
        client={{ queryYunhuiOrder: vi.fn() } as never}
        personaId="p1"
        allowed={false}
      />,
    )
    expect(screen.getByText(/工具权限/)).toBeInTheDocument()
  })

  it('queries orders via API when allowed', async () => {
    const user = userEvent.setup()
    const queryYunhuiOrder = vi.fn().mockResolvedValue({
      tool: 'order',
      status: 'ok',
      note: '演示订单',
      orders: [{ order_id: 'YH20260318001', status_label: '已发货', items: [{ name: '云汇智选 降噪耳机' }] }],
    })
    render(
      <YunhuiToolPane
        client={{ queryYunhuiOrder, recommendYunhuiProducts: vi.fn(), createYunhuiAftersale: vi.fn() } as never}
        personaId="p1"
        allowed
      />,
    )
    await user.type(screen.getByPlaceholderText(/YH20260318001/), 'YH20260318001')
    await user.click(screen.getByRole('button', { name: '查订单' }))
    expect(queryYunhuiOrder).toHaveBeenCalledWith('p1', {
      query: '',
      order_id: 'YH20260318001',
    })
    expect(await screen.findByText(/已发货/)).toBeInTheDocument()
  })
})

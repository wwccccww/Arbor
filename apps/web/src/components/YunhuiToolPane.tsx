import { useState, type FormEvent } from 'react'
import type { ArborClient } from '../api/client'
import type { ToolResult } from '../api/types'

export function YunhuiToolPane({
  client,
  personaId,
  allowed,
  disabled,
}: {
  client: ArborClient
  personaId: string
  allowed?: boolean
  disabled?: boolean
}) {
  const [orderId, setOrderId] = useState('')
  const [query, setQuery] = useState('')
  const [reason, setReason] = useState('')
  const [kind, setKind] = useState('return')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [last, setLast] = useState<ToolResult | null>(null)

  if (!allowed) {
    return (
      <section className="yunhui-tool" aria-label="云汇智选">
        <h3>云汇智选</h3>
        <p className="form-hint">
          在档案「工具权限」中加入 <code>order</code>、<code>recommend</code>、<code>aftersale</code> 后可查订单、荐货、登记售后。
        </p>
      </section>
    )
  }

  async function run(task: 'order' | 'recommend' | 'aftersale', event: FormEvent) {
    event.preventDefault()
    if (disabled || busy) return
    setBusy(true)
    setError(null)
    try {
      if (task === 'order') {
        setLast(await client.queryYunhuiOrder(personaId, { query, order_id: orderId }))
      } else if (task === 'recommend') {
        setLast(await client.recommendYunhuiProducts(personaId, { query }))
      } else {
        setLast(
          await client.createYunhuiAftersale(personaId, {
            order_id: orderId,
            reason,
            kind,
          }),
        )
      }
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setBusy(false)
    }
  }

  const orders = last?.orders ?? []
  const products = last?.products ?? []

  return (
    <section className="yunhui-tool" aria-label="云汇智选">
      <h3>云汇智选</h3>
      <p className="form-hint">连接商城：查订单、推荐货品、登记售后。未配置商城地址时返回演示数据。</p>
      {error ? <p role="alert">{error}</p> : null}
      <form onSubmit={(event) => void run('order', event)}>
        <label>
          订单号
          <input
            value={orderId}
            disabled={disabled || busy}
            onChange={(event) => setOrderId(event.target.value)}
            placeholder="例如 YH20260318001"
          />
        </label>
        <label>
          查询或推荐
          <input
            value={query}
            disabled={disabled || busy}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="例如 耳机、物流"
          />
        </label>
        <div className="yunhui-tool__actions">
          <button type="submit" disabled={disabled || busy}>
            查订单
          </button>
          <button type="button" disabled={disabled || busy} onClick={(event) => void run('recommend', event)}>
            推荐货品
          </button>
        </div>
      </form>
      <form onSubmit={(event) => void run('aftersale', event)}>
        <label>
          售后原因
          <input
            value={reason}
            disabled={disabled || busy}
            onChange={(event) => setReason(event.target.value)}
            placeholder="例如 耳机有杂音，申请退货"
          />
        </label>
        <label>
          类型
          <select value={kind} disabled={disabled || busy} onChange={(event) => setKind(event.target.value)}>
            <option value="return">退货</option>
            <option value="refund">退款</option>
            <option value="exchange">换货</option>
          </select>
        </label>
        <button type="submit" disabled={disabled || busy || !orderId.trim()}>
          登记售后
        </button>
      </form>
      {last ? (
        <div className="yunhui-tool__result">
          <p>
            {last.note ?? last.status}
            {last.aftersale_id ? ` · ${last.aftersale_id}` : ''}
          </p>
          {orders.map((order) => (
            <p key={order.order_id}>
              {order.order_id} · {order.status_label}
              {order.items?.[0]?.name ? ` · ${order.items[0].name}` : ''}
            </p>
          ))}
          {products.map((product) => (
            <p key={product.sku}>
              {product.name}
              {product.price_cents != null ? ` · ¥${(product.price_cents / 100).toFixed(0)}` : ''}
            </p>
          ))}
        </div>
      ) : null}
    </section>
  )
}

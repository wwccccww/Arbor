import { useState, type FormEvent } from 'react'
import type { ArborClient } from '../api/client'
import type { ToolResult } from '../api/types'

export function TicketToolPane({
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
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [last, setLast] = useState<ToolResult | null>(null)

  if (!allowed) {
    return (
      <section className="ticket-tool" aria-label="工单工具">
        <h3>工单登记</h3>
        <p className="form-hint">在档案「工具权限」中加入 <code>ticket</code> 后可用。</p>
      </section>
    )
  }

  async function submit(event: FormEvent) {
    event.preventDefault()
    const trimmed = title.trim() || description.trim()
    if (!trimmed || disabled || busy) return
    setBusy(true)
    setError(null)
    try {
      const result = await client.createTicket(personaId, {
        title: title.trim(),
        description: description.trim() || title.trim(),
      })
      setLast(result)
      setTitle('')
      setDescription('')
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="ticket-tool" aria-label="工单工具">
      <h3>工单登记</h3>
      <p className="form-hint">直接调用工单工具（stub 或 HTTP 后端），不经过对话关键词。</p>
      {error ? <p role="alert">{error}</p> : null}
      <form onSubmit={(event) => void submit(event)}>
        <label>
          标题
          <input
            value={title}
            disabled={disabled || busy}
            onChange={(event) => setTitle(event.target.value)}
            placeholder="例如：面店空调故障"
          />
        </label>
        <label>
          描述
          <textarea
            value={description}
            rows={3}
            disabled={disabled || busy}
            onChange={(event) => setDescription(event.target.value)}
            placeholder="补充故障现象、地点、期望处理时间"
          />
        </label>
        <button type="submit" disabled={disabled || busy || !title.trim() && !description.trim()}>
          登记工单
        </button>
      </form>
      {last ? (
        <p className="ticket-tool__result">
          已登记：
          {last.ticket_id ?? '—'}
          {last.title ? ` · ${last.title}` : ''}
          {last.note ? `（${last.note}）` : ''}
        </p>
      ) : null}
    </section>
  )
}

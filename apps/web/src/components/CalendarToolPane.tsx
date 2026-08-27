import { useState, type FormEvent } from 'react'
import type { ArborClient } from '../api/client'
import type { ToolResult } from '../api/types'
import { ToolResultsPanel } from './ToolResultsPanel'

export function CalendarToolPane({
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
  const [query, setQuery] = useState('近期日程')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [last, setLast] = useState<ToolResult | null>(null)

  if (!allowed) {
    return (
      <section className="calendar-tool" aria-label="日历工具">
        <h3>日程查询</h3>
        <p className="form-hint">在档案「工具权限」中加入 <code>calendar</code> 后可用；飞书绑定见上方。</p>
      </section>
    )
  }

  async function submit(event: FormEvent) {
    event.preventDefault()
    const trimmed = query.trim()
    if (!trimmed || disabled || busy) return
    setBusy(true)
    setError(null)
    try {
      const result = await client.queryCalendar(personaId, trimmed)
      setLast(result)
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="calendar-tool" aria-label="日历工具">
      <h3>日程查询</h3>
      <p className="form-hint">直接调用日历工具（stub 或飞书），不经过对话关键词。</p>
      {error ? <p role="alert">{error}</p> : null}
      <form onSubmit={(event) => void submit(event)}>
        <label>
          查询
          <input
            value={query}
            disabled={disabled || busy}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="例如：这周有什么安排"
          />
        </label>
        <button type="submit" disabled={disabled || busy || !query.trim()}>
          查询日程
        </button>
      </form>
      {last ? <ToolResultsPanel results={[last]} /> : null}
    </section>
  )
}

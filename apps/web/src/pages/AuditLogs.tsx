import { useEffect, useState } from 'react'
import type { ArborClient } from '../api/client'
import type { AuditLog, Persona } from '../api/types'

const ACTIONS = [
  { id: '', label: '全部' },
  { id: 'persona.update', label: '改档案' },
  { id: 'memory.import', label: '导入' },
  { id: 'memory.confirm', label: '确认记忆' },
  { id: 'thread.export', label: '导出会话' },
]

function payloadText(payload?: Record<string, unknown>) {
  if (!payload) return ''
  return JSON.stringify(payload)
}

export function AuditLogs({
  client,
  onBack,
}: {
  client: ArborClient
  onBack: () => void
}) {
  const [items, setItems] = useState<AuditLog[]>([])
  const [personas, setPersonas] = useState<Persona[]>([])
  const [action, setAction] = useState('')
  const [personaId, setPersonaId] = useState('')
  const [since, setSince] = useState('')
  const [until, setUntil] = useState('')
  const [forbidden, setForbidden] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    async function load() {
      try {
        const listed = await client.listAuditLogs({
          action: action || undefined,
          persona_id: personaId || undefined,
          since: since ? `${since}T00:00:00` : undefined,
          until: until ? `${until}T23:59:59` : undefined,
        })
        if (cancelled) return
        setForbidden(Boolean(listed.forbidden))
        setItems(listed.items)
        if (!listed.forbidden) {
          const people = await client.listPersonas()
          if (!cancelled) setPersonas(people)
        }
      } catch (err) {
        if (!cancelled) setError((err as Error).message)
      }
    }
    void load()
    return () => {
      cancelled = true
    }
  }, [client, action, personaId, since, until])

  return (
    <section className="checkup">
      <header className="workbench-bar">
        <button type="button" onClick={onBack}>
          返回
        </button>
        <h1>审计日志</h1>
      </header>
      <p>只显示脱敏后的操作记录，不含对话正文。</p>
      {forbidden ? <p role="alert">没有审计权限</p> : null}
      {error ? <p role="alert">{error}</p> : null}
      {forbidden ? null : (
        <>
          <label>
            动作
            <select value={action} onChange={(event) => setAction(event.target.value)}>
              {ACTIONS.map((item) => (
                <option key={item.id || 'all'} value={item.id}>
                  {item.label}
                </option>
              ))}
            </select>
          </label>
          <label>
            人设
            <select value={personaId} onChange={(event) => setPersonaId(event.target.value)}>
              <option value="">全部</option>
              {personas.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.display_name}
                </option>
              ))}
            </select>
          </label>
          <label>
            起始
            <input type="date" value={since} onChange={(event) => setSince(event.target.value)} />
          </label>
          <label>
            截止
            <input type="date" value={until} onChange={(event) => setUntil(event.target.value)} />
          </label>
          {items.length === 0 ? (
            <p>暂无记录</p>
          ) : (
            <ul className="audit-list">
              {items.map((item) => (
                <li key={item.id}>
                  <span className="eyebrow">{item.action}</span>
                  <p>{item.resource_type} {item.resource_id}</p>
                  {item.payload ? <p>{payloadText(item.payload)}</p> : null}
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </section>
  )
}

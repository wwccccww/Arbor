import { useState } from 'react'
import type { ArborClient } from '../api/client'
import { DecisionTracePanel } from '../components/DecisionTracePanel'
import type { DebugRequest } from '../api/types'

type Props = {
  client: ArborClient
  onBack: () => void
}

export function DebugPage({ client, onBack }: Props) {
  const [requestId, setRequestId] = useState('')
  const [result, setResult] = useState<DebugRequest | null>(null)
  const [content, setContent] = useState<Record<string, unknown> | null>(null)
  const [error, setError] = useState<string | undefined>()
  const [busy, setBusy] = useState(false)

  async function lookup() {
    const trimmed = requestId.trim()
    if (!trimmed) return
    setBusy(true)
    setError(undefined)
    setContent(null)
    try {
      const entry = await client.getDebugRequest(trimmed)
      setResult(entry)
    } catch (err) {
      setResult(null)
      setError((err as Error).message)
    } finally {
      setBusy(false)
    }
  }

  async function loadContent() {
    if (!result?.request_id) return
    setBusy(true)
    setError(undefined)
    try {
      const payload = await client.getDebugRequestContent(result.request_id)
      setContent(payload.content)
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setBusy(false)
    }
  }

  async function removeTrace() {
    if (!result?.request_id) return
    setBusy(true)
    setError(undefined)
    try {
      await client.deleteDebugRequest(result.request_id)
      setResult(null)
      setContent(null)
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <main className="page debug-page">
      <header className="page-header">
        <button type="button" className="link-button" onClick={onBack}>
          ← 返回
        </button>
        <h1>请求调试</h1>
        <p className="muted">按 request_id 查看决策轨迹；内容采样需 tenant 开关且 Admin 权限。</p>
      </header>

      <section className="card">
        <label htmlFor="debug-request-id">Request ID</label>
        <div className="inline-form">
          <input
            id="debug-request-id"
            value={requestId}
            onChange={(event) => setRequestId(event.target.value)}
            placeholder="01J..."
          />
          <button type="button" disabled={busy} onClick={() => void lookup()}>
            查询
          </button>
        </div>
        {error ? <p className="error">{error}</p> : null}
      </section>

      {result ? (
        <section className="card">
          <h2>{result.request_id}</h2>
          <p className="muted">
            thread {result.thread_id ?? '—'} · message {result.message_id ?? '—'}
          </p>
          {result.content_sampled ? (
            <div className="inline-form">
              <button type="button" disabled={busy} onClick={() => void loadContent()}>
                加载加密采样内容
              </button>
              <button type="button" className="danger" disabled={busy} onClick={() => void removeTrace()}>
                删除轨迹
              </button>
            </div>
          ) : (
            <button type="button" className="danger" disabled={busy} onClick={() => void removeTrace()}>
              删除轨迹
            </button>
          )}
          <DecisionTracePanel trace={result.decision_trace} requestId={result.request_id} />
          {content ? (
            <pre className="debug-content">{JSON.stringify(content, null, 2)}</pre>
          ) : null}
        </section>
      ) : null}
    </main>
  )
}

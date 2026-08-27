import { useEffect, useState } from 'react'
import type { ArborClient } from '../api/client'
import type { InboxItem, Persona } from '../api/types'
import { InboxPane } from '../components/InboxPane'

export function InboxPage({
  client,
  personaId,
  onBack,
  onOpenWorkbench,
}: {
  client: ArborClient
  personaId: string
  onBack: () => void
  onOpenWorkbench: () => void
}) {
  const [persona, setPersona] = useState<Persona | null>(null)
  const [inbox, setInbox] = useState<InboxItem[]>([])
  const [forbidden, setForbidden] = useState(false)
  const [busyId, setBusyId] = useState<string | undefined>()
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  async function refresh() {
    setLoading(true)
    setError(null)
    try {
      const detail = await client.getPersona(personaId)
      setPersona(detail)
      const listed = await client.listInbox(personaId)
      setForbidden(Boolean(listed.forbidden))
      setInbox(listed.items)
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void refresh()
  }, [personaId])

  async function confirmItem(id: string, opts: { markKeyEvent: boolean }) {
    setBusyId(id)
    try {
      await client.confirmInbox(id, opts)
      await refresh()
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setBusyId(undefined)
    }
  }

  async function dismissItem(id: string) {
    setBusyId(id)
    try {
      await client.dismissInbox(id)
      await refresh()
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setBusyId(undefined)
    }
  }

  async function bootstrap() {
    setBusyId('bootstrap')
    try {
      await client.bootstrapInbox(personaId)
      await refresh()
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setBusyId(undefined)
    }
  }

  return (
    <section className="inbox-page">
      <header className="topbar">
        <button type="button" className="btn--ghost" onClick={onBack}>← 首页</button>
        <div className="topbar__brand">
          记忆收件箱
          <small>{persona?.display_name ?? personaId}</small>
        </div>
        <div className="topbar__spacer" />
        <button type="button" className="btn--ghost" onClick={onOpenWorkbench}>
          打开工作台
        </button>
      </header>
      <main className="inbox-page__main">
        {error ? <p role="alert">{error}</p> : null}
        {loading ? <p>加载收件箱…</p> : null}
        <InboxPane
          items={inbox}
          forbidden={forbidden}
          busyId={busyId}
          onConfirm={(id, opts) => void confirmItem(id, opts)}
          onDismiss={(id) => void dismissItem(id)}
          onBootstrap={() => void bootstrap()}
        />
      </main>
    </section>
  )
}

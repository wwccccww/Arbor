import { useEffect, useState } from 'react'
import type { ArborClient } from '../api/client'
import type { ChatMessage, EventNode, Persona } from '../api/types'
import { ChatPane } from '../components/ChatPane'
import { EventTreePane } from '../components/EventTreePane'
import { ProfilePane } from '../components/ProfilePane'
import { WorkbenchLayout } from '../components/WorkbenchLayout'

function useNarrow() {
  const [narrow, setNarrow] = useState(() => window.matchMedia('(max-width: 900px)').matches)
  useEffect(() => {
    const media = window.matchMedia('(max-width: 900px)')
    const onChange = () => setNarrow(media.matches)
    media.addEventListener('change', onChange)
    return () => media.removeEventListener('change', onChange)
  }, [])
  return narrow
}

export function Workbench({
  client,
  personaId,
  onBack,
}: {
  client: ArborClient
  personaId: string
  onBack: () => void
}) {
  const narrow = useNarrow()
  const [treeOpen, setTreeOpen] = useState(false)
  const [persona, setPersona] = useState<Persona | null>(null)
  const [threadId, setThreadId] = useState<string | null>(null)
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [nodes, setNodes] = useState<EventNode[]>([])
  const [treeForbidden, setTreeForbidden] = useState(false)
  const [highlightedId, setHighlightedId] = useState<string | undefined>()
  const [sending, setSending] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    async function load() {
      try {
        const [loadedPersona, threads, tree] = await Promise.all([
          client.getPersona(personaId),
          client.listThreads(personaId),
          client.getEventTree(personaId),
        ])
        if (cancelled) return
        setPersona(loadedPersona)
        setTreeForbidden(Boolean(tree.forbidden))
        setNodes(tree.nodes)
        const thread = threads[0] ?? (await client.createThread(personaId))
        if (cancelled) return
        setThreadId(thread.id)
        setMessages(await client.listMessages(thread.id))
      } catch (err) {
        if (!cancelled) setError((err as Error).message)
      }
    }
    void load()
    return () => {
      cancelled = true
    }
  }, [client, personaId])

  function jump(eventId?: string) {
    if (!eventId) return
    setHighlightedId(eventId)
    if (narrow) setTreeOpen(true)
    document.getElementById(`event-${eventId}`)?.scrollIntoView({ block: 'nearest' })
  }

  async function send(text: string) {
    if (!threadId) return
    const userMessage: ChatMessage = {
      id: `local-${Date.now()}`,
      role: 'user',
      text,
      citations: [],
    }
    setMessages((current) => [...current, userMessage])
    setSending(true)
    setError(null)
    try {
      const reply = await client.sendMessage(threadId, text)
      setMessages((current) => [...current, reply])
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setSending(false)
    }
  }

  return (
    <div>
      <header className="workbench-bar">
        <button type="button" onClick={onBack}>
          返回
        </button>
        <span>{persona?.display_name ?? '工作台'}</span>
      </header>
      {error ? <p role="alert">{error}</p> : null}
      <WorkbenchLayout
        narrow={narrow}
        treeOpen={treeOpen}
        onToggleTree={() => setTreeOpen((open) => !open)}
        left={persona ? <ProfilePane persona={persona} /> : <p>加载档案…</p>}
        center={
          <ChatPane messages={messages} sending={sending} onSend={(text) => void send(text)} onJump={jump} />
        }
        right={
          <EventTreePane
            nodes={nodes}
            forbidden={treeForbidden}
            highlightedId={highlightedId}
            onSelect={setHighlightedId}
          />
        }
      />
    </div>
  )
}

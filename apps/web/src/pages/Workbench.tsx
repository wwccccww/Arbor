import { useEffect, useState } from 'react'
import type { ArborClient } from '../api/client'
import type { ChatMessage, EventCard, EventNode, InboxItem, MemoryItem, Persona, PersonaGrant, PersonaPatch, TenantMember } from '../api/types'
import { ChatPane } from '../components/ChatPane'
import { EventCardPane } from '../components/EventCardPane'
import { EventTreePane } from '../components/EventTreePane'
import { GrantsPane } from '../components/GrantsPane'
import { ImportPane } from '../components/ImportPane'
import { InboxPane } from '../components/InboxPane'
import { MemoryListPane } from '../components/MemoryListPane'
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
  const [treeView, setTreeView] = useState<'tree' | 'timeline'>('tree')
  const [persona, setPersona] = useState<Persona | null>(null)
  const [threadId, setThreadId] = useState<string | null>(null)
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [messageOffset, setMessageOffset] = useState(0)
  const [messageTotal, setMessageTotal] = useState(0)
  const messagePageSize = 50
  const [nodes, setNodes] = useState<EventNode[]>([])
  const [treeForbidden, setTreeForbidden] = useState(false)
  const [memories, setMemories] = useState<MemoryItem[]>([])
  const [memoriesForbidden, setMemoriesForbidden] = useState(false)
  const [memoryType, setMemoryType] = useState('')
  const [memoryStatus, setMemoryStatus] = useState('active')
  const [memoryTotal, setMemoryTotal] = useState(0)
  const [inbox, setInbox] = useState<InboxItem[]>([])
  const [inboxForbidden, setInboxForbidden] = useState(false)
  const [inboxBusy, setInboxBusy] = useState<string | undefined>()
  const [members, setMembers] = useState<TenantMember[]>([])
  const [grantsForbidden, setGrantsForbidden] = useState(true)
  const [grantsBusy, setGrantsBusy] = useState(false)
  const [profileBusy, setProfileBusy] = useState(false)
  const [highlightedId, setHighlightedId] = useState<string | undefined>()
  const [card, setCard] = useState<EventCard | null>(null)
  const [sending, setSending] = useState(false)
  const [exporting, setExporting] = useState(false)
  const [importing, setImporting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    async function load() {
      try {
        const [loadedPersona, threads, tree, pending, listedMemories] = await Promise.all([
          client.getPersona(personaId),
          client.listThreads(personaId),
          client.getEventTree(personaId, 'tree'),
          client.listInbox(personaId),
          client.listMemories(personaId),
        ])
        if (cancelled) return
        setPersona(loadedPersona)
        setTreeForbidden(Boolean(tree.forbidden))
        setNodes(tree.nodes)
        setMemoriesForbidden(Boolean(listedMemories.forbidden))
        setMemories(listedMemories.items)
        setMemoryTotal(listedMemories.total)
        setInboxForbidden(Boolean(pending.forbidden))
        setInbox(pending.items)
        if (Array.isArray(loadedPersona.grants)) {
          const listed = await client.listMembers()
          if (cancelled) return
          setGrantsForbidden(Boolean(listed.forbidden))
          setMembers(listed.items)
        } else {
          setGrantsForbidden(true)
          setMembers([])
        }
        const thread = threads[0] ?? (await client.createThread(personaId))
        if (cancelled) return
        setThreadId(thread.id)
        const page = await client.listMessages(thread.id, { limit: messagePageSize, offset: 0 })
        if (cancelled) return
        setMessages(page.items)
        setMessageTotal(page.total)
        setMessageOffset(0)
      } catch (err) {
        if (!cancelled) setError((err as Error).message)
      }
    }
    void load()
    return () => {
      cancelled = true
    }
  }, [client, personaId])

  async function openCard(eventId?: string) {
    if (!eventId) return
    setHighlightedId(eventId)
    if (narrow) setTreeOpen(true)
    document.getElementById(`event-${eventId}`)?.scrollIntoView({ block: 'nearest' })
    try {
      setCard(await client.getEventCard(eventId))
    } catch (err) {
      setError((err as Error).message)
    }
  }

  function jump(eventId?: string) {
    void openCard(eventId)
  }

  async function pageMessages(offset: number) {
    if (!threadId) return
    setError(null)
    try {
      const page = await client.listMessages(threadId, { limit: messagePageSize, offset })
      setMessages(page.items)
      setMessageTotal(page.total)
      setMessageOffset(offset)
    } catch (err) {
      setError((err as Error).message)
    }
  }

  async function send(text: string, file?: File) {
    if (!threadId) return
    const userMessage: ChatMessage = {
      id: `local-${Date.now()}`,
      role: 'user',
      text,
      citations: [],
      attachments: file ? [{ filename: file.name }] : [],
    }
    setMessages((current) => [...current, userMessage])
    setSending(true)
    setError(null)
    try {
      const reply = await client.sendMessage(threadId, text, file)
      setMessages((current) => [...current, reply])
      if (reply.inbox_created) {
        const pending = await client.listInbox(personaId)
        setInboxForbidden(Boolean(pending.forbidden))
        setInbox(pending.items)
      }
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setSending(false)
    }
  }

  async function openAttachment(filename: string) {
    if (!threadId) return
    setError(null)
    try {
      const blob = await client.downloadAttachment(threadId, filename)
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = filename
      link.click()
      URL.revokeObjectURL(url)
    } catch (err) {
      setError((err as Error).message)
    }
  }

  async function exportThread() {
    if (!threadId) return
    setExporting(true)
    setError(null)
    try {
      const data = await client.exportThread(threadId)
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = `thread-${threadId}.json`
      link.click()
      URL.revokeObjectURL(url)
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setExporting(false)
    }
  }

  async function loadMemories(type: string, status: string) {
    const listed = await client.listMemories(personaId, {
      type: type || undefined,
      status: status !== 'active' ? status : undefined,
    })
    setMemoriesForbidden(Boolean(listed.forbidden))
    setMemories(listed.items)
    setMemoryTotal(listed.total)
  }

  async function confirmItem(inboxId: string, opts: { markKeyEvent: boolean }) {
    setInboxBusy(inboxId)
    setError(null)
    try {
      await client.confirmInbox(inboxId, opts)
      setInbox((current) => current.filter((item) => item.id !== inboxId))
      await loadMemories(memoryType, memoryStatus)
      if (opts.markKeyEvent) {
        const tree = await client.getEventTree(personaId, treeView)
        setTreeForbidden(Boolean(tree.forbidden))
        setNodes(tree.nodes)
      }
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setInboxBusy(undefined)
    }
  }

  async function dismissItem(inboxId: string) {
    setInboxBusy(inboxId)
    setError(null)
    try {
      await client.dismissInbox(inboxId)
      setInbox((current) => current.filter((item) => item.id !== inboxId))
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setInboxBusy(undefined)
    }
  }

  async function changeMemoryType(type: string) {
    setMemoryType(type)
    try {
      await loadMemories(type, memoryStatus)
    } catch (err) {
      setError((err as Error).message)
    }
  }

  async function changeMemoryStatus(status: string) {
    setMemoryStatus(status)
    try {
      await loadMemories(memoryType, status)
    } catch (err) {
      setError((err as Error).message)
    }
  }

  async function changeView(view: 'tree' | 'timeline') {
    setTreeView(view)
    try {
      const tree = await client.getEventTree(personaId, view)
      setTreeForbidden(Boolean(tree.forbidden))
      setNodes(tree.nodes)
    } catch (err) {
      setError((err as Error).message)
    }
  }

  async function saveProfile(patch: PersonaPatch) {
    setProfileBusy(true)
    setError(null)
    try {
      setPersona(await client.patchPersona(personaId, patch))
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setProfileBusy(false)
    }
  }

  async function saveGrants(grants: PersonaGrant[]) {
    setGrantsBusy(true)
    setError(null)
    try {
      const updated = await client.replaceGrants(personaId, grants)
      setPersona((current) => (current ? { ...current, grants: updated.grants } : current))
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setGrantsBusy(false)
    }
  }

  async function importFile(file: File, hint?: string) {
    setImporting(true)
    setError(null)
    try {
      await client.importFile(personaId, file, hint)
      const pending = await client.listInbox(personaId)
      setInboxForbidden(Boolean(pending.forbidden))
      setInbox(pending.items)
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setImporting(false)
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
        left={
          persona ? (
            <>
              <ProfilePane
                persona={persona}
                editable={Array.isArray(persona.grants)}
                busy={profileBusy}
                onSave={(patch) => void saveProfile(patch)}
              />
              <GrantsPane
                members={members}
                grants={persona.grants ?? []}
                forbidden={grantsForbidden}
                busy={grantsBusy}
                onSave={(next) => void saveGrants(next)}
              />
              <ImportPane
                forbidden={inboxForbidden}
                busy={importing}
                onImport={(file, hint) => void importFile(file, hint)}
              />
              <InboxPane
                items={inbox}
                forbidden={inboxForbidden}
                busyId={inboxBusy}
                onConfirm={(id, opts) => void confirmItem(id, opts)}
                onDismiss={(id) => void dismissItem(id)}
              />
            </>
          ) : (
            <p>加载档案…</p>
          )
        }
        center={
          <ChatPane
            messages={messages}
            sending={sending}
            exporting={exporting}
            offset={messageOffset}
            total={messageTotal}
            pageSize={messagePageSize}
            onSend={(text, file) => void send(text, file)}
            onJump={jump}
            onOpenAttachment={(filename) => void openAttachment(filename)}
            onExport={() => void exportThread()}
            onPage={(next) => void pageMessages(next)}
          />
        }
        right={
          <>
            <EventTreePane
              nodes={nodes}
              forbidden={treeForbidden}
              view={treeView}
              highlightedId={highlightedId}
              onSelect={(eventId) => void openCard(eventId)}
              onChangeView={(view) => void changeView(view)}
            />
            {treeForbidden ? null : <EventCardPane card={card} />}
            <MemoryListPane
              items={memories}
              total={memoryTotal}
              forbidden={memoriesForbidden}
              type={memoryType}
              status={memoryStatus}
              onChangeType={(next) => void changeMemoryType(next)}
              onChangeStatus={(next) => void changeMemoryStatus(next)}
              onSelect={(eventId) => void openCard(eventId)}
            />
          </>
        }
      />
    </div>
  )
}

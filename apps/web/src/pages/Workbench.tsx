import { useEffect, useState } from 'react'
import type { ArborClient } from '../api/client'
import type { ChatMessage, EventCard, EventNode, EventTree, ImportJob, InboxItem, MemoryItem, Persona, PersonaGrant, PersonaPatch, TenantMember, Thread } from '../api/types'
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
  const [keyOnly, setKeyOnly] = useState(true)
  const [persona, setPersona] = useState<Persona | null>(null)
  const [threadId, setThreadId] = useState<string | null>(null)
  const [threads, setThreads] = useState<Thread[]>([])
  const [creatingThread, setCreatingThread] = useState(false)
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [messageOffset, setMessageOffset] = useState(0)
  const [messageTotal, setMessageTotal] = useState(0)
  const messagePageSize = 50
  const [nodes, setNodes] = useState<EventNode[]>([])
  const [treeEdges, setTreeEdges] = useState<EventTree['edges']>([])
  const [treeForbidden, setTreeForbidden] = useState(false)
  const [memories, setMemories] = useState<MemoryItem[]>([])
  const [memoriesForbidden, setMemoriesForbidden] = useState(false)
  const [memoryType, setMemoryType] = useState('')
  const [memoryStatus, setMemoryStatus] = useState('active')
  const [memoryTotal, setMemoryTotal] = useState(0)
  const [memoryOffset, setMemoryOffset] = useState(0)
  const [memoryByEvent, setMemoryByEvent] = useState(false)
  const memoryPageSize = 50
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
  const [importJob, setImportJob] = useState<ImportJob | null>(null)
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
          client.listMemories(personaId, { limit: memoryPageSize, offset: 0 }),
        ])
        if (cancelled) return
        setPersona(loadedPersona)
        setTreeForbidden(Boolean(tree.forbidden))
        setNodes(tree.nodes)
        setTreeEdges(tree.edges)
        setMemoriesForbidden(Boolean(listedMemories.forbidden))
        setMemories(listedMemories.items)
        setMemoryTotal(listedMemories.total)
        setMemoryOffset(0)
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
        setThreads(threads.length ? threads : [thread])
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
    if (highlightedId === eventId && card) {
      setHighlightedId(undefined)
      setCard(null)
      return
    }
    setHighlightedId(eventId)
    if (narrow) setTreeOpen(true)
    document.getElementById(`event-${eventId}`)?.scrollIntoView({ block: 'nearest' })
    try {
      setCard(await client.getEventCard(eventId))
      if (memoryByEvent) {
        await loadMemories(memoryType, memoryStatus, 0, eventId)
      }
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

  async function switchThread(id: string) {
    setError(null)
    try {
      const page = await client.listMessages(id, { limit: messagePageSize, offset: 0 })
      setThreadId(id)
      setMessages(page.items)
      setMessageTotal(page.total)
      setMessageOffset(0)
    } catch (err) {
      setError((err as Error).message)
    }
  }

  async function newThread() {
    setCreatingThread(true)
    setError(null)
    try {
      const created = await client.createThread(personaId)
      setThreads((current) => [...current, created])
      await switchThread(created.id)
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setCreatingThread(false)
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
    const placeholderId = `stream-${Date.now()}`
    const patchLast = (patch: (msg: ChatMessage) => ChatMessage) =>
      setMessages((current) => {
        const next = [...current]
        const idx = next.findIndex((m) => m.id === placeholderId)
        if (idx === -1) return current
        next[idx] = patch(next[idx])
        return next
      })
    // Optimistically render an empty assistant bubble that streams into place.
    setMessages((current) => [
      ...current,
      { id: placeholderId, role: 'assistant', text: '', citations: [] },
    ])
    try {
      if (typeof client.sendMessageStream === 'function') {
        await client.sendMessageStream(
          threadId,
          text,
          {
            onDelta: (chunk) => patchLast((m) => ({ ...m, text: m.text + chunk })),
            onDone: (reply) => {
              setMessages((current) => current.map((m) => (m.id === placeholderId ? reply : m)))
              if (reply.inbox_created) {
                void client
                  .listInbox(personaId)
                  .then((pending) => {
                    setInboxForbidden(Boolean(pending.forbidden))
                    setInbox(pending.items)
                  })
                  .catch(() => undefined)
              }
            },
          },
          file,
        )
      } else {
        const reply = await client.sendMessage(threadId, text, file)
        setMessages((current) => current.map((m) => (m.id === placeholderId ? reply : m)))
        if (reply.inbox_created) {
          const pending = await client.listInbox(personaId)
          setInboxForbidden(Boolean(pending.forbidden))
          setInbox(pending.items)
        }
      }
    } catch (err) {
      // Remove the placeholder on failure so the error is visible, not a ghost bubble.
      setMessages((current) => current.filter((m) => m.id !== placeholderId))
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

  async function loadMemories(type: string, status: string, offset = 0, eventId?: string) {
    const listed = await client.listMemories(personaId, {
      type: type || undefined,
      status: status !== 'active' ? status : undefined,
      event_id: eventId,
      limit: memoryPageSize,
      offset,
    })
    setMemoriesForbidden(Boolean(listed.forbidden))
    setMemories(listed.items)
    setMemoryTotal(listed.total)
    setMemoryOffset(offset)
  }

  async function confirmItem(inboxId: string, opts: { markKeyEvent: boolean }) {
    setInboxBusy(inboxId)
    setError(null)
    try {
      await client.confirmInbox(inboxId, opts)
      setInbox((current) => current.filter((item) => item.id !== inboxId))
      await loadMemories(memoryType, memoryStatus, memoryOffset, memoryByEvent ? highlightedId : undefined)
      if (opts.markKeyEvent) {
        const tree = await client.getEventTree(personaId, treeView, keyOnly)
        setTreeForbidden(Boolean(tree.forbidden))
        setNodes(tree.nodes)
        setTreeEdges(tree.edges)
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
      await loadMemories(type, memoryStatus, 0, memoryByEvent ? highlightedId : undefined)
    } catch (err) {
      setError((err as Error).message)
    }
  }

  async function changeMemoryStatus(status: string) {
    setMemoryStatus(status)
    try {
      await loadMemories(memoryType, status, 0, memoryByEvent ? highlightedId : undefined)
    } catch (err) {
      setError((err as Error).message)
    }
  }

  async function changeMemoryByEvent(next: boolean) {
    setMemoryByEvent(next)
    try {
      await loadMemories(memoryType, memoryStatus, 0, next ? highlightedId : undefined)
    } catch (err) {
      setError((err as Error).message)
    }
  }

  async function pageMemories(offset: number) {
    try {
      await loadMemories(memoryType, memoryStatus, offset, memoryByEvent ? highlightedId : undefined)
    } catch (err) {
      setError((err as Error).message)
    }
  }

  async function changeView(view: 'tree' | 'timeline') {
    setTreeView(view)
    try {
      const tree = await client.getEventTree(personaId, view, keyOnly)
      setTreeForbidden(Boolean(tree.forbidden))
      setNodes(tree.nodes)
      setTreeEdges(tree.edges)
    } catch (err) {
      setError((err as Error).message)
    }
  }

  async function changeKeyOnly(next: boolean) {
    setKeyOnly(next)
    try {
      const tree = await client.getEventTree(personaId, treeView, next)
      setTreeForbidden(Boolean(tree.forbidden))
      setNodes(tree.nodes)
      setTreeEdges(tree.edges)
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
      const created = await client.importFile(personaId, file, hint)
      const job = await client.getImport(created.job_id)
      setImportJob(job)
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
        <button type="button" className="btn--ghost" onClick={onBack}>
          返回
        </button>
        <h1>{persona?.display_name ?? '工作台'}</h1>
        {persona?.skin ? (
          <span className={`badge badge--${persona.skin === 'employee' ? 'employee' : 'companion'}`}>
            {persona.skin === 'employee' ? '数字员工' : '陪伴'}
          </span>
        ) : null}
        <span className="crumb">{persona?.one_liner ?? ''}</span>
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
              <MemoryListPane
                items={memories}
                total={memoryTotal}
                forbidden={memoriesForbidden}
                type={memoryType}
                status={memoryStatus}
                offset={memoryOffset}
                pageSize={memoryPageSize}
                eventId={highlightedId}
                filterByEvent={memoryByEvent}
                onChangeType={(next) => void changeMemoryType(next)}
                onChangeStatus={(next) => void changeMemoryStatus(next)}
                onToggleEventFilter={(next) => void changeMemoryByEvent(next)}
                onPage={(next) => void pageMemories(next)}
                onSelect={(eventId) => void openCard(eventId)}
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
                job={importJob}
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
            creatingThread={creatingThread}
            threads={threads}
            threadId={threadId ?? undefined}
            offset={messageOffset}
            total={messageTotal}
            pageSize={messagePageSize}
            onSend={(text, file) => void send(text, file)}
            onJump={jump}
            onOpenAttachment={(filename) => void openAttachment(filename)}
            onExport={() => void exportThread()}
            onPage={(next) => void pageMessages(next)}
            onSwitchThread={(id) => void switchThread(id)}
            onNewThread={() => void newThread()}
          />
        }
        right={
          <>
            <EventTreePane
              nodes={nodes}
              edges={treeEdges}
              forbidden={treeForbidden}
              view={treeView}
              keyOnly={keyOnly}
              highlightedId={highlightedId}
              onSelect={(eventId) => void openCard(eventId)}
              onChangeView={(view) => void changeView(view)}
              onChangeKeyOnly={(next) => void changeKeyOnly(next)}
            />
            {treeForbidden ? null : <EventCardPane card={card} />}
          </>
        }
      />
    </div>
  )
}

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
import { FeishuCalendarConnect } from '../components/FeishuCalendarConnect'
import { ProfilePane } from '../components/ProfilePane'
import { WorkbenchLayout } from '../components/WorkbenchLayout'
import { loadThreadSelection, saveThreadSelection } from '../threadSelection'
import { useAsyncGuard } from '../useAsyncGuard'

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

const TERMINAL_IMPORT = new Set(['done', 'failed', 'error', 'unknown'])

export function Workbench({
  client,
  personaId,
  workspaceAdmin = false,
  onBack,
}: {
  client: ArborClient
  personaId: string
  workspaceAdmin?: boolean
  onBack: () => void
}) {
  const narrow = useNarrow()
  const loadGuard = useAsyncGuard()
  const threadGuard = useAsyncGuard()
  const treeGuard = useAsyncGuard()
  const [treeOpen, setTreeOpen] = useState(false)
  const [treeView, setTreeView] = useState<'tree' | 'timeline' | 'biography'>('biography')
  const [keyOnly, setKeyOnly] = useState(true)
  const [loading, setLoading] = useState(true)
  const [switchingThread, setSwitchingThread] = useState(false)
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
  const [memoryDeleteBusy, setMemoryDeleteBusy] = useState<string | undefined>()
  const [highlightedId, setHighlightedId] = useState<string | undefined>()
  const [card, setCard] = useState<EventCard | null>(null)
  const [sending, setSending] = useState(false)
  const [exporting, setExporting] = useState(false)
  const [importing, setImporting] = useState(false)
  const [importJob, setImportJob] = useState<ImportJob | null>(null)
  const [chatError, setChatError] = useState<string | null>(null)
  const [sidebarError, setSidebarError] = useState<string | null>(null)
  const [treeError, setTreeError] = useState<string | null>(null)

  useEffect(() => {
    const token = loadGuard.begin()
    setLoading(true)
    setPersona(null)
    setThreadId(null)
    setThreads([])
    setMessages([])
    setChatError(null)
    setSidebarError(null)
    setTreeError(null)
    setCard(null)
    setHighlightedId(undefined)

    async function load() {
      try {
        const [loadedPersona, listedThreads, tree, pending, listedMemories] = await Promise.all([
          client.getPersona(personaId),
          client.listThreads(personaId),
          client.getEventTree(personaId, 'tree'),
          client.listInbox(personaId),
          client.listMemories(personaId, { limit: memoryPageSize, offset: 0 }),
        ])
        if (!loadGuard.isLatest(token)) return
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
        if (workspaceAdmin || Array.isArray(loadedPersona.grants)) {
          try {
            const listed = await client.listMembers()
            if (!loadGuard.isLatest(token)) return
            setGrantsForbidden(Boolean(listed.forbidden))
            setMembers(listed.items)
          } catch {
            if (!loadGuard.isLatest(token)) return
            setGrantsForbidden(true)
            setMembers([])
          }
        } else {
          setGrantsForbidden(true)
          setMembers([])
        }
        const threadList = listedThreads.length ? listedThreads : [await client.createThread(personaId)]
        const savedThreadId = loadThreadSelection(personaId)
        const activeThread =
          (savedThreadId ? threadList.find((item) => item.id === savedThreadId) : undefined) ?? threadList[0]
        if (!loadGuard.isLatest(token)) return
        setThreads(threadList)
        setThreadId(activeThread.id)
        saveThreadSelection(personaId, activeThread.id)
        const page = await client.listMessages(activeThread.id, { limit: messagePageSize, offset: 0 })
        if (!loadGuard.isLatest(token)) return
        setMessages(page.items)
        setMessageTotal(page.total)
        setMessageOffset(0)
      } catch (err) {
        if (!loadGuard.isLatest(token)) return
        setSidebarError((err as Error).message)
      } finally {
        if (loadGuard.isLatest(token)) setLoading(false)
      }
    }
    void load()
  }, [client, personaId, workspaceAdmin])

  useEffect(() => {
    if (!importJob?.id || importJob.forbidden || TERMINAL_IMPORT.has(importJob.status)) return
    const timer = window.setInterval(() => {
      void client
        .getImport(importJob.id)
        .then(async (job) => {
          setImportJob(job)
          if (job.status === 'done') {
            const pending = await client.listInbox(personaId)
            setInboxForbidden(Boolean(pending.forbidden))
            setInbox(pending.items)
          }
        })
        .catch(() => undefined)
    }, 2000)
    return () => window.clearInterval(timer)
  }, [client, importJob?.id, importJob?.forbidden, importJob?.status, personaId])

  async function ensureLatestMessagePage(currentThreadId: string, total: number) {
    const lastOffset = Math.max(0, total - messagePageSize)
    if (messageOffset === lastOffset && messages.length > 0) return messages
    const page = await client.listMessages(currentThreadId, { limit: messagePageSize, offset: lastOffset })
    setMessages(page.items)
    setMessageTotal(page.total)
    setMessageOffset(lastOffset)
    return page.items
  }

  async function openCard(eventId?: string) {
    if (!eventId) return
    if (highlightedId === eventId && card) {
      setHighlightedId(undefined)
      setCard(null)
      return
    }
    setHighlightedId(eventId)
    if (narrow) setTreeOpen(true)
    setTreeError(null)
    let visibleNodes = nodes
    if (!nodes.some((node) => node.id === eventId) && keyOnly) {
      try {
        const token = treeGuard.begin()
        const tree = await client.getEventTree(personaId, treeView, false)
        if (!treeGuard.isLatest(token)) return
        setKeyOnly(false)
        setTreeForbidden(Boolean(tree.forbidden))
        setNodes(tree.nodes)
        setTreeEdges(tree.edges)
        visibleNodes = tree.nodes
      } catch (err) {
        setTreeError((err as Error).message)
      }
    }
    if (visibleNodes.some((node) => node.id === eventId)) {
      window.requestAnimationFrame(() => {
        document.getElementById(`event-${eventId}`)?.scrollIntoView({ block: 'nearest' })
      })
    }
    try {
      const loaded = await client.getEventCard(eventId)
      setCard(loaded)
      if (loaded.forbidden) setTreeError('没有记忆权限，无法打开事件卡。')
      if (memoryByEvent) {
        await loadMemories(memoryType, memoryStatus, 0, eventId)
      }
    } catch (err) {
      setTreeError((err as Error).message)
    }
  }

  function jump(eventId?: string) {
    void openCard(eventId)
  }

  async function pageMessages(offset: number) {
    if (!threadId) return
    setChatError(null)
    try {
      const page = await client.listMessages(threadId, { limit: messagePageSize, offset })
      setMessages(page.items)
      setMessageTotal(page.total)
      setMessageOffset(offset)
    } catch (err) {
      setChatError((err as Error).message)
    }
  }

  async function switchThread(id: string) {
    const token = threadGuard.begin()
    setSwitchingThread(true)
    setChatError(null)
    try {
      const page = await client.listMessages(id, { limit: messagePageSize, offset: 0 })
      if (!threadGuard.isLatest(token)) return
      setThreadId(id)
      saveThreadSelection(personaId, id)
      setMessages(page.items)
      setMessageTotal(page.total)
      setMessageOffset(0)
    } catch (err) {
      if (!threadGuard.isLatest(token)) return
      setChatError((err as Error).message)
    } finally {
      if (threadGuard.isLatest(token)) setSwitchingThread(false)
    }
  }

  async function newThread() {
    setCreatingThread(true)
    setChatError(null)
    try {
      const created = await client.createThread(personaId)
      setThreads((current) => [...current, created])
      await switchThread(created.id)
    } catch (err) {
      setChatError((err as Error).message)
    } finally {
      setCreatingThread(false)
    }
  }

  async function send(text: string, files?: File[]) {
    if (!threadId) {
      setChatError('会话尚未就绪，请稍后再试。')
      return
    }
    setSending(true)
    setChatError(null)
    const userMessageId = `local-${Date.now()}`
    const placeholderId = `stream-${Date.now()}`
    try {
      const baseMessages = await ensureLatestMessagePage(threadId, messageTotal)
      const userMessage: ChatMessage = {
        id: userMessageId,
        role: 'user',
        text,
        citations: [],
        attachments: files?.map((f) => ({ filename: f.name })) ?? [],
      }
      setMessages([...baseMessages, userMessage, { id: placeholderId, role: 'assistant', text: '', citations: [] }])
      const patchLast = (patch: (msg: ChatMessage) => ChatMessage) =>
        setMessages((current) => {
          const next = [...current]
          const idx = next.findIndex((m) => m.id === placeholderId)
          if (idx === -1) return current
          next[idx] = patch(next[idx])
          return next
        })
      if (typeof client.sendMessageStream === 'function') {
        await client.sendMessageStream(
          threadId,
          text,
          {
            onDelta: (chunk) => patchLast((m) => ({ ...m, text: m.text + chunk })),
            onDone: (reply) => {
              setMessages((current) => current.map((m) => (m.id === placeholderId ? reply : m)))
              setMessageTotal((current) => current + 2)
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
          files,
        )
      } else {
        const reply = await client.sendMessage(threadId, text, files)
        setMessages((current) => current.map((m) => (m.id === placeholderId ? reply : m)))
        setMessageTotal((current) => current + 2)
        if (reply.inbox_created) {
          const pending = await client.listInbox(personaId)
          setInboxForbidden(Boolean(pending.forbidden))
          setInbox(pending.items)
        }
      }
    } catch (err) {
      setMessages((current) => current.filter((m) => m.id !== placeholderId && m.id !== userMessageId))
      setChatError((err as Error).message)
    } finally {
      setSending(false)
    }
  }

  async function openAttachment(filename: string) {
    if (!threadId) {
      setChatError('会话尚未就绪，请稍后再试。')
      return
    }
    setChatError(null)
    try {
      const blob = await client.downloadAttachment(threadId, filename)
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = filename
      link.click()
      URL.revokeObjectURL(url)
    } catch (err) {
      setChatError((err as Error).message)
    }
  }

  async function exportThread() {
    if (!threadId) {
      setChatError('会话尚未就绪，请稍后再试。')
      return
    }
    setExporting(true)
    setChatError(null)
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
      setChatError((err as Error).message)
    } finally {
      setExporting(false)
    }
  }

  async function deleteMemory(memoryId: string) {
    setMemoryDeleteBusy(memoryId)
    setSidebarError(null)
    try {
      await client.deleteMemory(personaId, memoryId)
      await loadMemories(memoryType, memoryStatus, memoryOffset, memoryByEvent ? highlightedId : undefined)
    } catch (err) {
      setSidebarError((err as Error).message)
    } finally {
      setMemoryDeleteBusy(undefined)
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
    setSidebarError(null)
    try {
      await client.confirmInbox(inboxId, opts)
      setInbox((current) => current.filter((item) => item.id !== inboxId))
      await loadMemories(memoryType, memoryStatus, memoryOffset, memoryByEvent ? highlightedId : undefined)
      if (opts.markKeyEvent) {
        const token = treeGuard.begin()
        const tree = await client.getEventTree(personaId, treeView, keyOnly)
        if (!treeGuard.isLatest(token)) return
        setTreeForbidden(Boolean(tree.forbidden))
        setNodes(tree.nodes)
        setTreeEdges(tree.edges)
      }
    } catch (err) {
      setSidebarError((err as Error).message)
    } finally {
      setInboxBusy(undefined)
    }
  }

  async function dismissItem(inboxId: string) {
    setInboxBusy(inboxId)
    setSidebarError(null)
    try {
      await client.dismissInbox(inboxId)
      setInbox((current) => current.filter((item) => item.id !== inboxId))
    } catch (err) {
      setSidebarError((err as Error).message)
    } finally {
      setInboxBusy(undefined)
    }
  }

  async function changeMemoryType(type: string) {
    setMemoryType(type)
    setSidebarError(null)
    try {
      await loadMemories(type, memoryStatus, 0, memoryByEvent ? highlightedId : undefined)
    } catch (err) {
      setSidebarError((err as Error).message)
    }
  }

  async function changeMemoryStatus(status: string) {
    setMemoryStatus(status)
    setSidebarError(null)
    try {
      await loadMemories(memoryType, status, 0, memoryByEvent ? highlightedId : undefined)
    } catch (err) {
      setSidebarError((err as Error).message)
    }
  }

  async function changeMemoryByEvent(next: boolean) {
    setMemoryByEvent(next)
    setSidebarError(null)
    try {
      await loadMemories(memoryType, memoryStatus, 0, next ? highlightedId : undefined)
    } catch (err) {
      setSidebarError((err as Error).message)
    }
  }

  async function pageMemories(offset: number) {
    setSidebarError(null)
    try {
      await loadMemories(memoryType, memoryStatus, offset, memoryByEvent ? highlightedId : undefined)
    } catch (err) {
      setSidebarError((err as Error).message)
    }
  }

  async function changeView(view: 'tree' | 'timeline' | 'biography') {
    setTreeView(view)
    setTreeError(null)
    const token = treeGuard.begin()
    try {
      const tree = await client.getEventTree(personaId, view, keyOnly)
      if (!treeGuard.isLatest(token)) return
      setTreeForbidden(Boolean(tree.forbidden))
      setNodes(tree.nodes)
      setTreeEdges(tree.edges)
    } catch (err) {
      if (!treeGuard.isLatest(token)) return
      setTreeError((err as Error).message)
    }
  }

  async function changeKeyOnly(next: boolean) {
    setKeyOnly(next)
    setTreeError(null)
    const token = treeGuard.begin()
    try {
      const tree = await client.getEventTree(personaId, treeView, next)
      if (!treeGuard.isLatest(token)) return
      setTreeForbidden(Boolean(tree.forbidden))
      setNodes(tree.nodes)
      setTreeEdges(tree.edges)
    } catch (err) {
      if (!treeGuard.isLatest(token)) return
      setTreeError((err as Error).message)
    }
  }

  async function saveProfile(patch: PersonaPatch) {
    setProfileBusy(true)
    setSidebarError(null)
    try {
      setPersona(await client.patchPersona(personaId, patch))
    } catch (err) {
      setSidebarError((err as Error).message)
    } finally {
      setProfileBusy(false)
    }
  }

  async function saveGrants(grants: PersonaGrant[]) {
    setGrantsBusy(true)
    setSidebarError(null)
    try {
      const updated = await client.replaceGrants(personaId, grants)
      setPersona((current) => (current ? { ...current, grants: updated.grants } : current))
    } catch (err) {
      setSidebarError((err as Error).message)
    } finally {
      setGrantsBusy(false)
    }
  }

  async function importFile(file: File, hint?: string) {
    setImporting(true)
    setSidebarError(null)
    try {
      const created = await client.importFile(personaId, file, hint)
      const job =
        created.status === 'pending'
          ? await client.pollImport(created.job_id)
          : await client.getImport(created.job_id)
      setImportJob(job)
      const pending = await client.listInbox(personaId)
      setInboxForbidden(Boolean(pending.forbidden))
      setInbox(pending.items)
    } catch (err) {
      setSidebarError((err as Error).message)
    } finally {
      setImporting(false)
    }
  }

  const canEditPersona = workspaceAdmin || Array.isArray(persona?.grants)

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
      {sidebarError ? (
        <p className="workbench-alert workbench-alert--sidebar" role="alert">
          {sidebarError}
        </p>
      ) : null}
      {treeError ? (
        <p className="workbench-alert workbench-alert--tree" role="alert">
          {treeError}
        </p>
      ) : null}
      <WorkbenchLayout
        narrow={narrow}
        treeOpen={treeOpen}
        onToggleTree={() => setTreeOpen((open) => !open)}
        left={
          persona ? (
            <>
              <div data-left-panel="profile">
                <ProfilePane
                  persona={persona}
                  editable={canEditPersona}
                  busy={profileBusy}
                  onSave={(patch) => void saveProfile(patch)}
                />
                <FeishuCalendarConnect client={client} editable={canEditPersona} />
              </div>
              <div data-left-panel="memory">
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
                  onDelete={workspaceAdmin ? (id) => void deleteMemory(id) : undefined}
                  deleteBusyId={memoryDeleteBusy}
                />
              </div>
              <div data-left-panel="tools">
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
              </div>
            </>
          ) : (
            <p>{loading ? '加载档案…' : '无法加载档案'}</p>
          )
        }
        center={
          <ChatPane
            messages={messages}
            sending={sending}
            exporting={exporting}
            creatingThread={creatingThread}
            switchingThread={switchingThread}
            ready={Boolean(threadId) && !loading}
            threads={threads}
            threadId={threadId ?? undefined}
            offset={messageOffset}
            total={messageTotal}
            pageSize={messagePageSize}
            error={chatError}
            onSend={(text, files) => void send(text, files)}
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

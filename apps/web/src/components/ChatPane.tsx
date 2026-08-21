import { useState, type FormEvent } from 'react'
import type { ChatMessage, Thread } from '../api/types'
import { CitationList } from './CitationList'

export function ChatPane({
  messages,
  sending,
  exporting,
  creatingThread,
  threads,
  threadId,
  offset = 0,
  total,
  pageSize = 50,
  onSend,
  onJump,
  onOpenAttachment,
  onExport,
  onPage,
  onSwitchThread,
  onNewThread,
}: {
  messages: ChatMessage[]
  sending?: boolean
  exporting?: boolean
  creatingThread?: boolean
  threads?: Thread[]
  threadId?: string
  offset?: number
  total?: number
  pageSize?: number
  onSend: (text: string, file?: File) => void
  onJump: (eventId?: string) => void
  onOpenAttachment?: (filename: string) => void
  onExport?: () => void
  onPage?: (offset: number) => void
  onSwitchThread?: (threadId: string) => void
  onNewThread?: () => void
}) {
  const [draft, setDraft] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [fileKey, setFileKey] = useState(0)

  function submit(event: FormEvent) {
    event.preventDefault()
    const text = draft.trim()
    if ((!text && !file) || sending) return
    onSend(text, file ?? undefined)
    setDraft('')
    setFile(null)
    setFileKey((current) => current + 1)
  }

  return (
    <section className="chat">
      {onExport || onSwitchThread || onNewThread ? (
        <div className="chat-toolbar">
          {threads && threadId && onSwitchThread ? (
            <label>
              会话
              <select value={threadId} onChange={(event) => onSwitchThread(event.target.value)}>
                {threads.map((thread, index) => (
                  <option key={thread.id} value={thread.id}>
                    会话 {index + 1}
                  </option>
                ))}
              </select>
            </label>
          ) : null}
          {onNewThread ? (
            <button type="button" disabled={Boolean(creatingThread)} onClick={onNewThread}>
              新会话
            </button>
          ) : null}
          {onExport ? (
            <button type="button" disabled={Boolean(exporting)} onClick={onExport}>
              导出会话
            </button>
          ) : null}
        </div>
      ) : null}
      {onPage && typeof total === 'number' && total > pageSize ? (
        <div className="chat-pager">
          <button type="button" disabled={offset <= 0} onClick={() => onPage(Math.max(0, offset - pageSize))}>
            上一页
          </button>
          <span>
            {offset + 1}–{offset + messages.length} / {total}
          </span>
          <button
            type="button"
            disabled={offset + messages.length >= total}
            onClick={() => onPage(offset + pageSize)}
          >
            下一页
          </button>
        </div>
      ) : null}
      <ol className="transcript">
        {messages.map((message) => (
          <li key={message.id} data-role={message.role}>
            <p>{message.text}</p>
            {message.attachments?.length ? (
              <ul aria-label="聊天附件">
                {message.attachments.map((item) => (
                  <li key={item.filename}>
                    <button type="button" onClick={() => onOpenAttachment?.(item.filename)}>
                      {item.filename}
                    </button>
                  </li>
                ))}
              </ul>
            ) : null}
            {message.role === 'assistant' ? (
              <CitationList citations={message.citations} onJump={onJump} />
            ) : null}
          </li>
        ))}
      </ol>
      <form onSubmit={submit}>
        <label>
          发送消息
          <textarea
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            rows={3}
          />
        </label>
        <label>
          选择附件
          <input
            key={fileKey}
            type="file"
            onChange={(event) => setFile(event.target.files?.[0] ?? null)}
          />
        </label>
        <button type="submit" disabled={Boolean(sending) || (!draft.trim() && !file)}>
          发送
        </button>
      </form>
    </section>
  )
}

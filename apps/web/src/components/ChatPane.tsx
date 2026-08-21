import { useState, type FormEvent } from 'react'
import type { ChatMessage } from '../api/types'
import { CitationList } from './CitationList'

export function ChatPane({
  messages,
  sending,
  exporting,
  onSend,
  onJump,
  onOpenAttachment,
  onExport,
}: {
  messages: ChatMessage[]
  sending?: boolean
  exporting?: boolean
  onSend: (text: string, file?: File) => void
  onJump: (eventId?: string) => void
  onOpenAttachment?: (filename: string) => void
  onExport?: () => void
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
      {onExport ? (
        <div className="chat-toolbar">
          <button type="button" disabled={Boolean(exporting)} onClick={onExport}>
            导出会话
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

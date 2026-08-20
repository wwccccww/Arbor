import { useState, type FormEvent } from 'react'
import type { ChatMessage } from '../api/types'
import { CitationList } from './CitationList'

export function ChatPane({
  messages,
  sending,
  onSend,
  onJump,
}: {
  messages: ChatMessage[]
  sending?: boolean
  onSend: (text: string) => void
  onJump: (eventId?: string) => void
}) {
  const [draft, setDraft] = useState('')

  function submit(event: FormEvent) {
    event.preventDefault()
    const text = draft.trim()
    if (!text || sending) return
    onSend(text)
    setDraft('')
  }

  return (
    <section className="chat">
      <ol className="transcript">
        {messages.map((message) => (
          <li key={message.id} data-role={message.role}>
            <p>{message.text}</p>
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
        <button type="submit" disabled={Boolean(sending)}>
          发送
        </button>
      </form>
    </section>
  )
}

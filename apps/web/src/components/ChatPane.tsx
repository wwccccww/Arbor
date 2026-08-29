import { useEffect, useRef, useState, type FormEvent } from 'react'
import type { ChatMessage, Thread } from '../api/types'
import { CitationList } from './CitationList'
import { DecisionTracePanel } from './DecisionTracePanel'
import { RetrievalMetaPanel } from './RetrievalMetaPanel'
import { ToolResultsPanel } from './ToolResultsPanel'

export function ChatPane({
  messages,
  sending,
  exporting,
  creatingThread,
  switchingThread,
  ready = true,
  threads,
  threadId,
  offset = 0,
  total,
  pageSize = 50,
  error,
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
  switchingThread?: boolean
  ready?: boolean
  threads?: Thread[]
  threadId?: string
  offset?: number
  total?: number
  pageSize?: number
  error?: string | null
  onSend: (text: string, files?: File[]) => void
  onJump: (eventId?: string) => void
  onOpenAttachment?: (filename: string) => void
  onExport?: () => void
  onPage?: (offset: number) => void
  onSwitchThread?: (threadId: string) => void
  onNewThread?: () => void
}) {
  const [draft, setDraft] = useState('')
  const [files, setFiles] = useState<File[]>([])
  const [fileKey, setFileKey] = useState(0)
  const [recording, setRecording] = useState(false)
  const recorderRef = useRef<MediaRecorder | null>(null)
  const recordChunksRef = useRef<BlobPart[]>([])
  const transcriptRef = useRef<HTMLOListElement>(null)
  const disabled = !ready || Boolean(sending) || Boolean(switchingThread)

  useEffect(() => {
    const node = transcriptRef.current
    if (!node) return
    node.scrollTop = node.scrollHeight
  }, [messages, sending])

  function submit(event: FormEvent) {
    event.preventDefault()
    const text = draft.trim()
    if ((!text && files.length === 0) || disabled) return
    onSend(text, files.length ? files : undefined)
    setDraft('')
    setFiles([])
    setFileKey((current) => current + 1)
  }

  async function startVoiceRecording() {
    if (disabled || recording) return
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const recorder = new MediaRecorder(stream)
      recordChunksRef.current = []
      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) recordChunksRef.current.push(event.data)
      }
      recorder.onstop = () => {
        const mime = recorder.mimeType || 'audio/webm'
        const blob = new Blob(recordChunksRef.current, { type: mime })
        const ext = mime.includes('webm') ? 'webm' : mime.includes('ogg') ? 'ogg' : 'wav'
        const file = new File([blob], `voice-${Date.now()}.${ext}`, { type: mime })
        setFiles((current) => [...current, file])
        stream.getTracks().forEach((track) => track.stop())
        recorderRef.current = null
        setRecording(false)
      }
      recorder.start()
      recorderRef.current = recorder
      setRecording(true)
    } catch {
      setRecording(false)
    }
  }

  function stopVoiceRecording() {
    const recorder = recorderRef.current
    if (!recorder || recorder.state === 'inactive') return
    recorder.stop()
  }

  return (
    <section className="chat">
      {onExport || onSwitchThread || onNewThread ? (
        <div className="chat-toolbar">
          {threads && threadId && onSwitchThread ? (
            <label>
              会话
              <select
                value={threadId}
                disabled={disabled}
                onChange={(event) => onSwitchThread(event.target.value)}
              >
                {threads.map((thread, index) => (
                  <option key={thread.id} value={thread.id}>
                    会话 {index + 1}
                  </option>
                ))}
              </select>
            </label>
          ) : null}
          {onNewThread ? (
            <button type="button" disabled={disabled || Boolean(creatingThread)} onClick={onNewThread}>
              新会话
            </button>
          ) : null}
          {onExport ? (
            <button type="button" disabled={disabled || Boolean(exporting)} onClick={onExport}>
              导出会话
            </button>
          ) : null}
        </div>
      ) : null}
      {!ready ? <p className="chat-status">正在加载会话…</p> : null}
      {switchingThread ? <p className="chat-status">正在切换会话…</p> : null}
      {error ? (
        <p className="chat-error" role="alert">
          {error}
        </p>
      ) : null}
      {onPage && typeof total === 'number' && total > pageSize ? (
        <div className="chat-pager">
          <button type="button" disabled={offset <= 0 || disabled} onClick={() => onPage(Math.max(0, offset - pageSize))}>
            上一页
          </button>
          <span>
            {offset + 1}–{offset + messages.length} / {total}
          </span>
          <button
            type="button"
            disabled={offset + messages.length >= total || disabled}
            onClick={() => onPage(offset + pageSize)}
          >
            下一页
          </button>
        </div>
      ) : null}
      <ol
        ref={transcriptRef}
        className="transcript"
        aria-live="polite"
        aria-relevant="additions text"
        aria-label="对话记录"
      >
        {messages.map((message) => (
          <li key={message.id} data-role={message.role} aria-label={message.role === 'user' ? '用户' : '助手'}>
            {message.text ? <p>{message.text}</p> : null}
            {message.role === 'assistant' && !message.text ? (
              <p className="chat-streaming" aria-label="正在输入">
                <span className="dot" />
                <span className="dot" />
                <span className="dot" />
              </p>
            ) : null}
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
            {message.role === 'assistant' ? (
              <DecisionTracePanel
                meta={message.retrieval_meta}
                trace={message.decision_trace}
                requestId={message.request_id}
              />
            ) : null}
            {message.role === 'assistant' ? <ToolResultsPanel results={message.tool_results} /> : null}
          </li>
        ))}
      </ol>
      <form onSubmit={submit}>
        <label>
          发送消息
          <textarea
            value={draft}
            disabled={disabled}
            onChange={(event) => setDraft(event.target.value)}
            rows={3}
          />
        </label>
        <label>
          附件（可多选，含图片/语音/文档）
          <input
            key={fileKey}
            type="file"
            multiple
            disabled={disabled}
            accept=".txt,.md,.pdf,.doc,.docx,.ppt,.pptx,.png,.jpg,.jpeg,.webp,.mp3,.wav,.m4a,.webm,.ogg"
            onChange={(event) => setFiles(Array.from(event.target.files ?? []))}
          />
        </label>
        <div className="chat-voice">
          <button
            type="button"
            disabled={disabled || recording}
            onClick={() => void startVoiceRecording()}
          >
            开始录音
          </button>
          <button type="button" disabled={disabled || !recording} onClick={() => stopVoiceRecording()}>
            结束录音
          </button>
          {recording ? <span className="form-hint">录音中…结束后会加入附件列表</span> : null}
          {files.length ? <span className="form-hint">待发送附件：{files.map((f) => f.name).join('、')}</span> : null}
        </div>
        <button type="submit" disabled={disabled || (!draft.trim() && files.length === 0)}>
          发送
        </button>
      </form>
    </section>
  )
}

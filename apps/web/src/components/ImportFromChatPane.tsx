import { useState, type FormEvent } from 'react'
import type { Persona } from '../api/types'

export function ImportFromChatPane({
  personas,
  busy,
  onImport,
}: {
  personas: Persona[]
  busy?: boolean
  onImport: (personaId: string, file: File) => void
}) {
  const [personaId, setPersonaId] = useState(personas[0]?.id ?? '')
  const [file, setFile] = useState<File | null>(null)

  function handleSubmit(event: FormEvent) {
    event.preventDefault()
    if (!personaId || !file) return
    onImport(personaId, file)
    setFile(null)
  }

  if (personas.length === 0) {
    return (
      <div className="import-chat-pane">
        <h3>从聊天记录导入</h3>
        <p className="muted">先创建一个人设，再把导出的聊天文件导入为初稿记忆与事件节点。</p>
      </div>
    )
  }

  return (
    <form className="import-chat-pane" onSubmit={handleSubmit}>
      <h3>从聊天记录导入</h3>
      <p className="muted">
        上传微信 / Telegram 等导出的文本或 JSON，系统会抽取档案线索、写入 Inbox，并自动生成第一批事件节点。
      </p>
      <label className="field">
        <span>导入到人设</span>
        <select value={personaId} onChange={(event) => setPersonaId(event.target.value)} disabled={busy}>
          {personas.map((persona) => (
            <option key={persona.id} value={persona.id}>
              {persona.display_name}
            </option>
          ))}
        </select>
      </label>
      <label className="field">
        <span>聊天导出文件</span>
        <input
          type="file"
          accept=".txt,.json,.md,.log"
          disabled={busy}
          onChange={(event) => setFile(event.target.files?.[0] ?? null)}
        />
      </label>
      <button type="submit" className="btn" disabled={busy || !personaId || !file}>
        {busy ? '导入中…' : '导入并生成初稿'}
      </button>
    </form>
  )
}

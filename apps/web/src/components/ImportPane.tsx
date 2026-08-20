import { useState, type FormEvent } from 'react'

export function ImportPane({
  forbidden,
  busy,
  onImport,
}: {
  forbidden?: boolean
  busy?: boolean
  onImport: (file: File, hint?: string) => void
}) {
  const [file, setFile] = useState<File | null>(null)
  const [hint, setHint] = useState('')

  if (forbidden) return null

  function submit(event: FormEvent) {
    event.preventDefault()
    if (!file || busy) return
    onImport(file, hint.trim() || undefined)
  }

  return (
    <section>
      <h3>导入</h3>
      <p>文本会进收件箱，不直写记忆。</p>
      <form onSubmit={submit}>
        <label>
          导入文件
          <input
            type="file"
            onChange={(event) => setFile(event.target.files?.[0] ?? null)}
          />
        </label>
        <label>
          备注
          <input value={hint} onChange={(event) => setHint(event.target.value)} />
        </label>
        <button type="submit" disabled={!file || Boolean(busy)}>
          导入
        </button>
      </form>
    </section>
  )
}

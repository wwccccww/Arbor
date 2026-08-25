import { useState, type FormEvent } from 'react'
import type { ImportJob } from '../api/types'

export function ImportPane({
  forbidden,
  busy,
  job,
  onImport,
}: {
  forbidden?: boolean
  busy?: boolean
  job?: ImportJob | null
  onImport: (file: File, hint?: string) => void
}) {
  const [file, setFile] = useState<File | null>(null)
  const [hint, setHint] = useState('')
  const [fileKey, setFileKey] = useState(0)

  if (forbidden) return null

  function submit(event: FormEvent) {
    event.preventDefault()
    if (!file || busy) return
    onImport(file, hint.trim() || undefined)
    setFile(null)
    setHint('')
    setFileKey((current) => current + 1)
  }

  return (
    <section>
      <h3>导入</h3>
      <p>文本会进收件箱，不直写记忆。</p>
      <form onSubmit={submit}>
        <label>
          导入文件
          <input
            key={fileKey}
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
      {job && !job.forbidden ? (
        <p>
          {job.filename ?? '导入'} · {job.status}
          {typeof job.inbox_created === 'number' ? ` · ${job.inbox_created} 条进收件箱` : ''}
          {job.status === 'failed' && job.error ? ` · ${job.error}` : ''}
        </p>
      ) : null}
    </section>
  )
}

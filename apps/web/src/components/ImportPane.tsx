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
          {job.parser ? ` · ${job.parser}` : ''}
          {typeof job.chunks_parsed === 'number' && job.chunks_parsed > 0
            ? ` · ${job.chunks_parsed} 块`
            : ''}
          {typeof job.inbox_created === 'number' ? ` · ${job.inbox_created} 条进收件箱` : ''}
          {typeof job.chunks_parsed === 'number' && job.chunks_parsed === 0 && job.status === 'completed'
            ? ' · 未解析出内容（检查依赖或文件格式）'
            : ''}
          {job.parser === 'stub' ? ' · 解析器未就绪' : ''}
          {job.status === 'failed' && job.error ? ` · ${job.error}` : ''}
        </p>
      ) : null}
    </section>
  )
}

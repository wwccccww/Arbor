import { useState } from 'react'
import type { InboxItem } from '../api/types'

export function InboxPane({
  items,
  forbidden,
  busyId,
  onConfirm,
  onDismiss,
  onBootstrap,
}: {
  items: InboxItem[]
  forbidden?: boolean
  busyId?: string
  onConfirm: (inboxId: string, opts: { markKeyEvent: boolean }) => void
  onDismiss: (inboxId: string) => void
  onBootstrap?: () => void
}) {
  const [markKey, setMarkKey] = useState<Record<string, boolean>>({})
  const bootstrapBusy = busyId === 'bootstrap'

  if (forbidden) {
    return (
      <section>
        <h3>收件箱</h3>
        <p>没有写入权限，收件箱为空。</p>
      </section>
    )
  }

  return (
    <section>
      <h3>收件箱</h3>
      {items.length === 0 ? (
        <p>没有待确认的记忆</p>
      ) : (
        <>
          {onBootstrap ? (
            <p className="inbox-bulk">
              <button type="button" disabled={bootstrapBusy} onClick={() => onBootstrap()}>
                一键写入记忆并建树
              </button>
              <span className="form-hint">自动确认 {items.length} 条，事件类进传记目录。</span>
            </p>
          ) : null}
          <ul className="inbox-list">
            {items.map((item) => {
              const text = item.payload?.text || item.id
              const isConflict = item.kind === 'conflict' || Boolean(item.conflicts_with)
              const disabled = busyId === item.id || bootstrapBusy
              return (
                <li key={item.id} className={isConflict ? 'inbox-conflict' : undefined}>
                  {isConflict ? <span className="badge badge--fail">冲突</span> : null}
                  {item.kind === 'event' ? <span className="badge">事件</span> : null}
                  <p>{text}</p>
                  {item.conflict_memory_text ? (
                    <blockquote className="inbox-conflict-quote">
                      <strong>已有记忆</strong>
                      <p>{item.conflict_memory_text}</p>
                    </blockquote>
                  ) : item.conflicts_with ? (
                    <p className="form-hint">与已有记忆冲突（ID {item.conflicts_with}）</p>
                  ) : null}
                  {isConflict ? (
                    <p className="form-hint">「记下来」会用新条替代旧记忆；「忽略」保留旧记忆。</p>
                  ) : null}
                  <label>
                    <input
                      type="checkbox"
                      checked={Boolean(markKey[item.id])}
                      onChange={(event) =>
                        setMarkKey((current) => ({ ...current, [item.id]: event.target.checked }))
                      }
                    />
                    标成关键事件
                  </label>
                  <div className="inbox-actions">
                    <button
                      type="button"
                      disabled={disabled}
                      onClick={() => onConfirm(item.id, { markKeyEvent: Boolean(markKey[item.id]) })}
                    >
                      记下来
                    </button>
                    <button type="button" disabled={disabled} onClick={() => onDismiss(item.id)}>
                      忽略
                    </button>
                  </div>
                </li>
              )
            })}
          </ul>
        </>
      )}
    </section>
  )
}

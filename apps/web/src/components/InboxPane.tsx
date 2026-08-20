import { useState } from 'react'
import type { InboxItem } from '../api/types'

export function InboxPane({
  items,
  forbidden,
  busyId,
  onConfirm,
  onDismiss,
}: {
  items: InboxItem[]
  forbidden?: boolean
  busyId?: string
  onConfirm: (inboxId: string, opts: { markKeyEvent: boolean }) => void
  onDismiss: (inboxId: string) => void
}) {
  const [markKey, setMarkKey] = useState<Record<string, boolean>>({})

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
        <ul className="inbox-list">
          {items.map((item) => {
            const text = item.payload?.text || item.id
            const disabled = busyId === item.id
            return (
              <li key={item.id}>
                <p>{text}</p>
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
                  <button type="button" disabled={disabled} onClick={() => onConfirm(item.id, { markKeyEvent: Boolean(markKey[item.id]) })}>
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
      )}
    </section>
  )
}

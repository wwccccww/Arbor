import type { MemoryItem } from '../api/types'

const MEMORY_TYPES = [
  { id: '', label: '全部' },
  { id: 'fact', label: '事实' },
  { id: 'episode_summary', label: '摘要' },
  { id: 'file_chunk', label: '文件块' },
  { id: 'image_caption', label: '图片说明' },
  { id: 'transcript', label: '转写' },
]

export function MemoryListPane({
  items,
  total,
  forbidden,
  type = '',
  onChangeType,
  onSelect,
}: {
  items: MemoryItem[]
  total?: number
  forbidden?: boolean
  type?: string
  onChangeType?: (type: string) => void
  onSelect?: (eventId: string) => void
}) {
  if (forbidden) {
    return (
      <section>
        <h3>记忆</h3>
        <p>没有记忆权限，列表为空。</p>
      </section>
    )
  }

  return (
    <section>
      <h3>记忆</h3>
      {onChangeType ? (
        <label>
          类型
          <select value={type} onChange={(event) => onChangeType(event.target.value)}>
            {MEMORY_TYPES.map((item) => (
              <option key={item.id || 'all'} value={item.id}>
                {item.label}
              </option>
            ))}
          </select>
        </label>
      ) : null}
      {typeof total === 'number' ? <p>{total} 条</p> : null}
      {items.length === 0 ? (
        <p>暂无记忆</p>
      ) : (
        <ul className="memory-list">
          {items.map((item) => (
            <li key={item.id}>
              {item.event_id ? (
                <button type="button" onClick={() => onSelect?.(item.event_id!)}>
                  <span className="eyebrow">{item.type}</span>
                  {item.text}
                </button>
              ) : (
                <>
                  <span className="eyebrow">{item.type}</span>
                  <p>{item.text}</p>
                </>
              )}
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}

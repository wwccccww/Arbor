import type { MemoryItem } from '../api/types'

const MEMORY_TYPES = [
  { id: '', label: '全部' },
  { id: 'fact', label: '事实' },
  { id: 'episode_summary', label: '摘要' },
  { id: 'file_chunk', label: '文件块' },
  { id: 'image_caption', label: '图片说明' },
  { id: 'transcript', label: '转写' },
]

const MEMORY_STATUSES = [
  { id: 'active', label: '现行' },
  { id: 'superseded', label: '已替代' },
  { id: 'deleted', label: '已删除' },
]

export function MemoryListPane({
  items,
  total,
  forbidden,
  type = '',
  status = 'active',
  offset = 0,
  pageSize = 50,
  eventId,
  filterByEvent = false,
  onChangeType,
  onChangeStatus,
  onToggleEventFilter,
  onPage,
  onSelect,
}: {
  items: MemoryItem[]
  total?: number
  forbidden?: boolean
  type?: string
  status?: string
  offset?: number
  pageSize?: number
  eventId?: string
  filterByEvent?: boolean
  onChangeType?: (type: string) => void
  onChangeStatus?: (status: string) => void
  onToggleEventFilter?: (next: boolean) => void
  onPage?: (offset: number) => void
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
      {onChangeStatus ? (
        <label>
          状态
          <select value={status} onChange={(event) => onChangeStatus(event.target.value)}>
            {MEMORY_STATUSES.map((item) => (
              <option key={item.id} value={item.id}>
                {item.label}
              </option>
            ))}
          </select>
        </label>
      ) : null}
      {onToggleEventFilter ? (
        <label>
          仅当前事件
          <input
            type="checkbox"
            checked={filterByEvent}
            disabled={!eventId}
            onChange={(event) => onToggleEventFilter(event.target.checked)}
          />
        </label>
      ) : null}
      {typeof total === 'number' ? <p>{total} 条</p> : null}
      {onPage && typeof total === 'number' && total > pageSize ? (
        <div className="memory-pager">
          <button type="button" disabled={offset <= 0} onClick={() => onPage(Math.max(0, offset - pageSize))}>
            上一页
          </button>
          <span>
            {offset + 1}–{offset + items.length} / {total}
          </span>
          <button
            type="button"
            disabled={offset + items.length >= total}
            onClick={() => onPage(offset + pageSize)}
          >
            下一页
          </button>
        </div>
      ) : null}
      {items.length === 0 ? (
        <p>暂无记忆</p>
      ) : (
        <ul className="memory-list">
          {items.map((item) => (
            <li key={item.id}>
              {item.event_id ? (
                <button type="button" onClick={() => onSelect?.(item.event_id!)}>
                  <span className="eyebrow">
                    {item.type}
                    {item.status && item.status !== 'active' ? ` · ${item.status}` : ''}
                  </span>
                  {item.text}
                </button>
              ) : (
                <>
                  <span className="eyebrow">
                    {item.type}
                    {item.status && item.status !== 'active' ? ` · ${item.status}` : ''}
                  </span>
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

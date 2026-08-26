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
  onDelete,
  deleteBusyId,
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
  onDelete?: (memoryId: string) => void
  deleteBusyId?: string
}) {
  if (forbidden) {
    return (
      <section>
        <h3>记忆</h3>
        <p className="empty-state">没有记忆权限，列表为空。</p>
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
          <input
            type="checkbox"
            checked={filterByEvent}
            disabled={!eventId}
            onChange={(event) => onToggleEventFilter(event.target.checked)}
          />
          仅当前事件
        </label>
      ) : null}
      {typeof total === 'number' ? <p className="form-hint">{total} 条</p> : null}
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
        <p className="empty-state">暂无记忆</p>
      ) : (
        <ul className="memory-list">
          {items.map((item) => {
            const statusLabel = item.status && item.status !== 'active' ? ` · ${item.status}` : ''
            const meta = `${item.type ?? ''}${statusLabel}`
            return (
              <li key={item.id}>
                <div className="memory-list__tag">
                  <span className="eyebrow">{meta}</span>
                  {onDelete ? (
                    <button
                      type="button"
                      className="memory-list__delete"
                      aria-label={`删除记忆 ${item.id}`}
                      disabled={deleteBusyId === item.id}
                      onClick={() => onDelete(item.id)}
                    >
                      删除
                    </button>
                  ) : null}
                </div>
                {item.event_id ? (
                  <button type="button" onClick={() => onSelect?.(item.event_id!)}>
                    {item.text}
                  </button>
                ) : (
                  <p>{item.text}</p>
                )}
              </li>
            )
          })}
        </ul>
      )}
    </section>
  )
}

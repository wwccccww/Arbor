import type { Citation } from '../api/types'

export function CitationList({
  citations,
  onJump,
}: {
  citations: Citation[]
  onJump: (eventId?: string) => void
}) {
  if (!citations.length) return null
  return (
    <ul aria-label="依据">
      {citations.map((item, index) => {
        const label = item.preview || (item.memory_id ? '查看依据' : '查看依据')
        if (!item.preview && !item.event_id && !item.memory_id) return null
        return (
          <li key={item.memory_id ?? item.event_id ?? String(index)}>
            {item.event_id ? (
              <button type="button" onClick={() => onJump(item.event_id)} title={label}>
                {label}
              </button>
            ) : (
              <span className="citation-text" title={label}>
                {label}
              </span>
            )}
          </li>
        )
      })}
    </ul>
  )
}

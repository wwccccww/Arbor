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
      {citations.map((item, index) => (
        <li key={item.memory_id ?? item.event_id ?? String(index)}>
          <button type="button" onClick={() => onJump(item.event_id)}>
            {item.preview || item.memory_id || '记忆'}
          </button>
        </li>
      ))}
    </ul>
  )
}

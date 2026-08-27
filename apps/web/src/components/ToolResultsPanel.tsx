import type { ToolResult } from '../api/types'

const TOOL_LABELS: Record<string, string> = {
  calendar: '日历',
  ticket: '工单',
}

export function ToolResultsPanel({ results }: { results?: ToolResult[] }) {
  if (!results?.length) return null
  return (
    <details className="tool-results" open>
      <summary>工具结果（{results.length}）</summary>
      <ul>
        {results.map((item, index) => (
          <li key={`${item.tool ?? 'tool'}-${index}`}>
            <span className="badge">{TOOL_LABELS[item.tool ?? ''] ?? item.tool ?? '工具'}</span>
            {item.ticket_id ? <span>工单 {item.ticket_id}</span> : null}
            {item.title ? <span>{item.title}</span> : null}
            {item.summary ? <span>{item.summary}</span> : null}
            {item.note ? <p className="form-hint">{item.note}</p> : null}
            {item.events?.length ? (
              <ul>
                {item.events.map((event) => (
                  <li key={`${event.title}-${event.start}`}>
                    {event.title}
                    {event.start ? ` · ${event.start}` : ''}
                  </li>
                ))}
              </ul>
            ) : null}
          </li>
        ))}
      </ul>
    </details>
  )
}

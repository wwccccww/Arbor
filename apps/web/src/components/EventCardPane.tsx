import type { EventCard } from '../api/types'

const TYPE_LABELS: Record<string, string> = {
  milestone: '里程碑',
  promise: '承诺',
  conflict: '冲突',
  daily: '日常',
  work: '工作',
}

export function EventCardPane({ card }: { card?: EventCard | null }) {
  if (!card) {
    return <p className="empty-state">点选事件节点查看卡片。</p>
  }
  if (card.forbidden) {
    return <p className="empty-state">没有记忆权限，无法打开事件卡。</p>
  }
  return (
    <article className="event-card">
      <h3>{card.title}</h3>
      <div className="event-card__legend">
        {card.type ? <span className={`badge badge--${card.type === 'conflict' ? 'fail' : 'companion'}`}>{TYPE_LABELS[card.type] ?? card.type}</span> : null}
        {card.happened_at ? <span className="badge">{card.happened_at}</span> : null}
      </div>
      {card.summary ? <p>{card.summary}</p> : null}
      <h4>相关记忆</h4>
      {card.memories.length ? (
        <ul>
          {card.memories.map((item) => (
            <li key={item.id}>{item.text}</li>
          ))}
        </ul>
      ) : (
        <p className="empty-state">没有相关记忆</p>
      )}
      <h4>附件</h4>
      {card.attachments.length ? (
        <ul>
          {card.attachments.map((item) => (
            <li key={item.id}>
              <span className="eyebrow">{item.type}</span>
              {item.text}
            </li>
          ))}
        </ul>
      ) : (
        <p className="empty-state">没有附件</p>
      )}
    </article>
  )
}

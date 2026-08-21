import type { EventCard } from '../api/types'

export function EventCardPane({ card }: { card?: EventCard | null }) {
  if (!card) {
    return <p>点选事件节点查看卡片。</p>
  }
  if (card.forbidden) {
    return <p>没有记忆权限，无法打开事件卡。</p>
  }
  return (
    <article className="event-card">
      <h3>{card.title}</h3>
      {card.happened_at ? <p className="eyebrow">{card.happened_at}</p> : null}
      {card.summary ? <p>{card.summary}</p> : null}
      <h4>相关记忆</h4>
      {card.memories.length ? (
        <ul>
          {card.memories.map((item) => (
            <li key={item.id}>{item.text}</li>
          ))}
        </ul>
      ) : (
        <p>没有相关记忆</p>
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
        <p>没有附件</p>
      )}
    </article>
  )
}

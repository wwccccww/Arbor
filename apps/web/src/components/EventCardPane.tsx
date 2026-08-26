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
    return (
      <p className="empty-state" role="alert">
        没有记忆权限，无法打开事件卡。
      </p>
    )
  }
  return (
    <article className="event-card">
      <h3>{card.title}</h3>
      <div className="event-card__legend">
        {card.type ? (
          <span className={`badge badge--${card.type === 'conflict' ? 'fail' : 'companion'}`}>
            {TYPE_LABELS[card.type] ?? card.type}
          </span>
        ) : null}
        {card.happened_at ? <span className="badge">{card.happened_at}</span> : null}
        {typeof card.confidence === 'number' ? (
          <span className="badge">置信度 {card.confidence.toFixed(2)}</span>
        ) : null}
      </div>
      {card.summary ? <p>{card.summary}</p> : null}
      {card.participants?.length ? (
        <>
          <h4>人物</h4>
          <ul>
            {card.participants.map((name) => (
              <li key={name}>{name}</li>
            ))}
          </ul>
        </>
      ) : null}
      {card.causal_in?.length || card.causal_out?.length ? (
        <>
          <h4>因果</h4>
          {card.causal_in?.length ? (
            <p className="form-hint">
              起因：
              {card.causal_in.map((item) => item.title).join('、')}
            </p>
          ) : null}
          {card.causal_out?.length ? (
            <p className="form-hint">
              导致：
              {card.causal_out.map((item) => item.title).join('、')}
            </p>
          ) : null}
        </>
      ) : null}
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
      {card.verbatim?.length ? (
        <>
          <h4>原话 / 摘要</h4>
          <ul>
            {card.verbatim.map((item) => (
              <li key={item.id}>{item.text}</li>
            ))}
          </ul>
        </>
      ) : null}
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

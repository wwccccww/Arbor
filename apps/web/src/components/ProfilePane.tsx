import type { Persona } from '../api/types'

export function ProfilePane({ persona }: { persona: Persona }) {
  return (
    <section>
      <p className="eyebrow">{persona.skin === 'employee' ? '数字员工' : '陪伴'}</p>
      <h2>{persona.display_name}</h2>
      {persona.one_liner ? <p>{persona.one_liner}</p> : null}
      {persona.taboos ? (
        <div>
          <h3>禁忌</h3>
          <ul>
            {persona.taboos.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </div>
      ) : null}
      {persona.relationships ? (
        <div>
          <h3>关系</h3>
          <ul>
            {persona.relationships.map((item) => (
              <li key={`${item.name}-${item.kind}`}>
                {item.name} · {item.kind}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </section>
  )
}

import { useEffect, useState, type FormEvent } from 'react'
import type { Persona } from '../api/types'

export type ProfilePatch = {
  display_name: string
  one_liner: string
  taboos: string[]
}

function taboosText(taboos?: string[]) {
  return (taboos ?? []).join('\n')
}

function parseTaboos(raw: string) {
  return raw
    .split('\n')
    .map((item) => item.trim())
    .filter(Boolean)
}

export function ProfilePane({
  persona,
  editable,
  busy,
  onSave,
}: {
  persona: Persona
  editable?: boolean
  busy?: boolean
  onSave?: (patch: ProfilePatch) => void
}) {
  const [displayName, setDisplayName] = useState(persona.display_name)
  const [oneLiner, setOneLiner] = useState(persona.one_liner ?? '')
  const [taboos, setTaboos] = useState(taboosText(persona.taboos))

  useEffect(() => {
    setDisplayName(persona.display_name)
    setOneLiner(persona.one_liner ?? '')
    setTaboos(taboosText(persona.taboos))
  }, [persona])

  function submit(event: FormEvent) {
    event.preventDefault()
    const name = displayName.trim()
    if (!name || busy || !onSave) return
    onSave({
      display_name: name,
      one_liner: oneLiner,
      taboos: parseTaboos(taboos),
    })
  }

  return (
    <section>
      <p className="eyebrow">{persona.skin === 'employee' ? '数字员工' : '陪伴'}</p>
      <h2>{persona.display_name}</h2>
      {editable ? (
        <form onSubmit={submit}>
          <label>
            显示名
            <input
              value={displayName}
              disabled={Boolean(busy)}
              onChange={(event) => setDisplayName(event.target.value)}
            />
          </label>
          <label>
            一句话
            <textarea
              value={oneLiner}
              rows={2}
              disabled={Boolean(busy)}
              onChange={(event) => setOneLiner(event.target.value)}
            />
          </label>
          <label>
            禁忌
            <textarea
              value={taboos}
              rows={3}
              disabled={Boolean(busy)}
              onChange={(event) => setTaboos(event.target.value)}
            />
          </label>
          <button type="submit" disabled={Boolean(busy) || !displayName.trim()}>
            保存档案
          </button>
        </form>
      ) : (
        <>
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
        </>
      )}
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

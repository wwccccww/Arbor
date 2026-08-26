import { useEffect, useState, type FormEvent } from 'react'
import type { Persona, PersonaPatch } from '../api/types'

function linesText(items?: string[]) {
  return (items ?? []).join('\n')
}

function parseLines(raw: string) {
  return raw
    .split('\n')
    .map((item) => item.trim())
    .filter(Boolean)
}

function relationshipsText(items?: { name: string; kind: string }[]) {
  return (items ?? []).map((item) => `${item.name} · ${item.kind}`).join('\n')
}

function parseRelationships(raw: string) {
  return raw
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => {
      const [name, ...rest] = line.split('·').map((part) => part.trim())
      return { name, kind: rest.join(' · ') }
    })
    .filter((item) => item.name)
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
  onSave?: (patch: PersonaPatch) => void
}) {
  const [skin, setSkin] = useState<'companion' | 'employee'>(
    persona.skin === 'employee' ? 'employee' : 'companion',
  )
  const [displayName, setDisplayName] = useState(persona.display_name)
  const [oneLiner, setOneLiner] = useState(persona.one_liner ?? '')
  const [taboos, setTaboos] = useState(linesText(persona.taboos))
  const [traits, setTraits] = useState(linesText(persona.personality?.traits))
  const [relationships, setRelationships] = useState(relationshipsText(persona.relationships))
  const [allowedTools, setAllowedTools] = useState(linesText(persona.tool_policy?.allowed_tools))
  const [toolNotes, setToolNotes] = useState(persona.tool_policy?.notes ?? '')

  useEffect(() => {
    setSkin(persona.skin === 'employee' ? 'employee' : 'companion')
    setDisplayName(persona.display_name)
    setOneLiner(persona.one_liner ?? '')
    setTaboos(linesText(persona.taboos))
    setTraits(linesText(persona.personality?.traits))
    setRelationships(relationshipsText(persona.relationships))
    setAllowedTools(linesText(persona.tool_policy?.allowed_tools))
    setToolNotes(persona.tool_policy?.notes ?? '')
  }, [persona])

  function submit(event: FormEvent) {
    event.preventDefault()
    const name = displayName.trim()
    if (!name || busy || !onSave) return
    onSave({
      skin,
      display_name: name,
      one_liner: oneLiner,
      taboos: parseLines(taboos),
      personality: { traits: parseLines(traits) },
      relationships: parseRelationships(relationships),
      tool_policy: {
        allowed_tools: parseLines(allowedTools),
        notes: toolNotes.trim(),
      },
    })
  }

  return (
    <section>
      <p className="eyebrow">{persona.skin === 'employee' ? '数字员工' : '陪伴'}</p>
      <h2>{persona.display_name}</h2>
      {editable ? (
        <form onSubmit={submit}>
          <label>
            类型
            <select
              value={skin}
              disabled={Boolean(busy)}
              onChange={(event) => setSkin(event.target.value as 'companion' | 'employee')}
            >
              <option value="companion">陪伴</option>
              <option value="employee">数字员工</option>
            </select>
          </label>
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
            性格
            <textarea
              value={traits}
              rows={3}
              disabled={Boolean(busy)}
              onChange={(event) => setTraits(event.target.value)}
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
          <label>
            关系
            <textarea
              value={relationships}
              rows={3}
              disabled={Boolean(busy)}
              onChange={(event) => setRelationships(event.target.value)}
            />
          </label>
          <label>
            工具权限（每行一个，如 calendar、ticket）
            <textarea
              value={allowedTools}
              rows={2}
              disabled={Boolean(busy)}
              onChange={(event) => setAllowedTools(event.target.value)}
            />
          </label>
          <label>
            工具说明
            <textarea
              value={toolNotes}
              rows={2}
              disabled={Boolean(busy)}
              onChange={(event) => setToolNotes(event.target.value)}
            />
          </label>
          <button type="submit" disabled={Boolean(busy) || !displayName.trim()}>
            保存档案
          </button>
        </form>
      ) : (
        <>
          {persona.one_liner ? <p>{persona.one_liner}</p> : null}
          {persona.personality?.traits?.length ? (
            <div>
              <h3>性格</h3>
              <ul>
                {persona.personality.traits.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </div>
          ) : null}
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
        </>
      )}
    </section>
  )
}

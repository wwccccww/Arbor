import { useState, type FormEvent } from 'react'
import type { PersonaDraft } from '../api/types'

export function CreatePersonaPane({
  forbidden,
  busy,
  onCreate,
}: {
  forbidden?: boolean
  busy?: boolean
  onCreate: (draft: PersonaDraft) => void
}) {
  const [skin, setSkin] = useState<PersonaDraft['skin']>('companion')
  const [displayName, setDisplayName] = useState('')
  const [oneLiner, setOneLiner] = useState('')

  if (forbidden) return null

  function submit(event: FormEvent) {
    event.preventDefault()
    const name = displayName.trim()
    if (!name || busy) return
    onCreate({
      skin,
      display_name: name,
      one_liner: oneLiner.trim() || undefined,
    })
  }

  return (
    <section className="create-persona">
      <h2>创建人设</h2>
      <p>新建后进入工作台。需要工作空间管理员。</p>
      <form onSubmit={submit}>
        <label>
          类型
          <select value={skin} disabled={Boolean(busy)} onChange={(event) => setSkin(event.target.value as PersonaDraft['skin'])}>
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
          <input
            value={oneLiner}
            disabled={Boolean(busy)}
            onChange={(event) => setOneLiner(event.target.value)}
          />
        </label>
        <button type="submit" disabled={Boolean(busy) || !displayName.trim()}>
          创建
        </button>
      </form>
    </section>
  )
}

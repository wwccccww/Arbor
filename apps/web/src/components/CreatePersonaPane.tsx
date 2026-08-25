import { useState, type FormEvent } from 'react'
import type { PersonaDraft } from '../api/types'

const TEMPLATES: Array<{
  id: string
  label: string
  skin: PersonaDraft['skin']
  one_liner: string
}> = [
  { id: '', label: '空白档案', skin: 'companion', one_liner: '' },
  { id: 'companion_partner', label: '伴侣', skin: 'companion', one_liner: '温柔陪伴，记得你的喜好与约定' },
  { id: 'companion_mentor', label: '导师', skin: 'companion', one_liner: '耐心引导，帮你拆解问题与复盘' },
  { id: 'employee_support', label: '客服', skin: 'employee', one_liner: '按手册处理售后与退货' },
  { id: 'employee_interviewer', label: '面试官', skin: 'employee', one_liner: '结构化提问，追问细节与动机' },
]

export function CreatePersonaPane({
  forbidden,
  busy,
  onCreate,
}: {
  forbidden?: boolean
  busy?: boolean
  onCreate: (draft: PersonaDraft) => void
}) {
  const [templateId, setTemplateId] = useState('')
  const [skin, setSkin] = useState<PersonaDraft['skin']>('companion')
  const [displayName, setDisplayName] = useState('')
  const [oneLiner, setOneLiner] = useState('')

  if (forbidden) return null

  function applyTemplate(id: string) {
    setTemplateId(id)
    const tpl = TEMPLATES.find((item) => item.id === id)
    if (!tpl) return
    setSkin(tpl.skin)
    setOneLiner(tpl.one_liner)
  }

  function submit(event: FormEvent) {
    event.preventDefault()
    const name = displayName.trim()
    if (!name || busy) return
    onCreate({
      skin,
      display_name: name,
      one_liner: oneLiner.trim() || undefined,
      template: templateId || undefined,
    })
  }

  return (
    <section className="create-persona">
      <h2>创建人设</h2>
      <p>可从模板起步，或空白填写。新建后进入工作台。</p>
      <form onSubmit={submit}>
        <label>
          模板
          <select
            value={templateId}
            disabled={Boolean(busy)}
            onChange={(event) => applyTemplate(event.target.value)}
          >
            {TEMPLATES.map((tpl) => (
              <option key={tpl.id || 'blank'} value={tpl.id}>
                {tpl.label}
              </option>
            ))}
          </select>
        </label>
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
